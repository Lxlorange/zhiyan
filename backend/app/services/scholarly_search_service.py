from __future__ import annotations

import json
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional


class ScholarlySearchError(RuntimeError):
    pass


class ScholarlySourceUnavailable(ScholarlySearchError):
    pass


@dataclass
class ScholarlySearchHit:
    title: str
    url: str
    source: str
    reason: str


GENERAL_SEARCH_SITES = [
    "docs.python.org",
    "pypi.org",
    "fastapi.tiangolo.com",
    "realpython.com",
    "testdriven.io",
    "fullstackpython.com",
    "github.com",
    "developer.mozilla.org",
    "stackoverflow.com",
    "interviewbit.com",
    "geeksforgeeks.org",
    "freecodecamp.org",
    "roadmap.sh",
]

STOPWORDS = {
    "with",
    "from",
    "that",
    "this",
    "using",
    "based",
    "study",
    "research",
    "project",
    "learning",
    "course",
    "guide",
    "docs",
    "tutorial",
    "introduction",
    "overview",
    "beginner",
    "beginner's",
    "beginners",
}


def resolve_scholarly_resource(query: str, topic: str = "") -> Optional[ScholarlySearchHit]:
    cleaned = _clean_query(query)
    if len(cleaned) < 3:
        return None
    errors: list[str] = []
    for searcher in (_search_openalex, _search_semantic_scholar, _search_arxiv, _search_crossref):
        try:
            hit = searcher(cleaned, topic)
        except ScholarlySourceUnavailable as exc:
            errors.append(str(exc))
            continue
        if hit is not None:
            return hit
    if errors:
        raise ScholarlySourceUnavailable("; ".join(errors))
    return None


def resolve_web_resource(query: str, topic: str = "") -> Optional[ScholarlySearchHit]:
    cleaned = _clean_query(query)
    if len(cleaned) < 3:
        return None
    if _prefer_general_web(cleaned, topic):
        try:
            hit = _search_duckduckgo(cleaned, topic)
        except ScholarlySourceUnavailable:
            hit = None
        if hit is not None:
            return hit
        return None
    if not _prefer_scholarly(cleaned, topic):
        try:
            return _search_duckduckgo(cleaned, topic)
        except ScholarlySourceUnavailable:
            return None
    try:
        hit = resolve_scholarly_resource(cleaned, topic)
    except ScholarlySourceUnavailable:
        hit = None
    if hit is not None:
        return hit
    try:
        return _search_duckduckgo(cleaned, topic)
    except ScholarlySourceUnavailable:
        return None


def verify_candidate_resource_url(
    title: str,
    url: str,
    topic: str = "",
    source: str = "",
    reason: str = "",
) -> Optional[ScholarlySearchHit]:
    normalized_url = _normalize_candidate_url(url)
    if not _is_public_http_url(normalized_url):
        return None

    page_title = _reachable_page_title(normalized_url)
    if page_title is None:
        return None

    display_title = _text(title) or page_title or normalized_url
    evidence = " ".join(
        part
        for part in [
            display_title,
            page_title,
            source,
            reason,
            _host(normalized_url),
            urllib.parse.urlparse(normalized_url).path.replace("/", " "),
        ]
        if part
    )
    if topic and not _is_relevant_web_hit(topic, evidence, reason, topic):
        return None

    return ScholarlySearchHit(
        title=display_title,
        url=normalized_url,
        source=source or f"{_host(normalized_url)} · Verified",
        reason=reason or "LLM candidate URL verified by server",
    )


def _search_openalex(query: str, topic: str = "") -> Optional[ScholarlySearchHit]:
    params = urllib.parse.urlencode(
        {
            "search": query,
            "per-page": "5",
            "select": "id,doi,title,display_name,publication_year,authorships,primary_location,open_access",
        }
    )
    data = _get_json(f"https://api.openalex.org/works?{params}")
    for item in data.get("results", []):
        title = _text(item.get("display_name") or item.get("title"))
        if not title or not _is_relevant_hit(query, title, topic):
            continue
        url = _openalex_url(item)
        if not _is_public_http_url(url):
            continue
        source = "OpenAlex"
        year = item.get("publication_year")
        authors = _authors(item)
        if year:
            source += f" · {year}"
        if authors:
            source += f" · {authors}"
        return ScholarlySearchHit(title=title, url=url, source=source, reason=f"OpenAlex result for: {query}")
    return None


def _search_semantic_scholar(query: str, topic: str = "") -> Optional[ScholarlySearchHit]:
    params = urllib.parse.urlencode(
        {
            "query": query,
            "limit": "5",
            "fields": "title,url,year,authors,abstract,externalIds",
        }
    )
    data = _get_json(f"https://api.semanticscholar.org/graph/v1/paper/search?{params}")
    for item in data.get("data", []):
        title = _text(item.get("title"))
        abstract = _text(item.get("abstract"))
        if not title or not _is_relevant_hit(query, f"{title} {abstract}", topic):
            continue
        external_ids = item.get("externalIds") or {}
        doi = _text(external_ids.get("DOI"))
        url = f"https://doi.org/{doi}" if doi else _text(item.get("url"))
        if not _is_public_http_url(url):
            continue
        source = "Semantic Scholar"
        year = item.get("year")
        if year:
            source += f" · {year}"
        author_names = [
            _text(author.get("name"))
            for author in (item.get("authors") or [])[:2]
            if isinstance(author, dict) and _text(author.get("name"))
        ]
        if author_names:
            source += f" · {', '.join(author_names)}"
        return ScholarlySearchHit(title=title, url=url, source=source, reason=f"Semantic Scholar result for: {query}")
    return None


def _search_arxiv(query: str, topic: str = "") -> Optional[ScholarlySearchHit]:
    params = urllib.parse.urlencode({"search_query": f"all:{query}", "start": "0", "max_results": "5"})
    xml = _get_text(f"https://export.arxiv.org/api/query?{params}")
    for entry in re.findall(r"<entry>(.*?)</entry>", xml, flags=re.S):
        title_match = re.search(r"<title>(.*?)</title>", entry, flags=re.S)
        summary_match = re.search(r"<summary>(.*?)</summary>", entry, flags=re.S)
        id_match = re.search(r"<id>(.*?)</id>", entry, flags=re.S)
        if not title_match or not id_match:
            continue
        title = _strip_html(title_match.group(1))
        summary = _strip_html(summary_match.group(1)) if summary_match else ""
        if not _is_relevant_hit(query, f"{title} {summary}", topic):
            continue
        url = _text(id_match.group(1))
        if not _is_public_http_url(url):
            continue
        return ScholarlySearchHit(title=title, url=url, source="arXiv", reason=f"arXiv result for: {query}")
    return None


def _search_crossref(query: str, topic: str = "") -> Optional[ScholarlySearchHit]:
    params = urllib.parse.urlencode({"query.bibliographic": query, "rows": "5"})
    data = _get_json(f"https://api.crossref.org/works?{params}")
    for item in data.get("message", {}).get("items", []):
        title_values = item.get("title") or []
        title = _text(title_values[0] if title_values else "")
        if not title or not _is_relevant_hit(query, title, topic):
            continue
        doi = _text(item.get("DOI"))
        url = f"https://doi.org/{doi}" if doi else _text(item.get("URL"))
        if not _is_public_http_url(url):
            continue
        source = "Crossref"
        year = _crossref_year(item)
        if year:
            source += f" · {year}"
        return ScholarlySearchHit(title=title, url=url, source=source, reason=f"Crossref result for: {query}")
    return None


def _search_duckduckgo(query: str, topic: str = "") -> Optional[ScholarlySearchHit]:
    for search_query in _general_search_queries(query, topic):
        params = urllib.parse.urlencode({"q": search_query, "kl": "wt-wt"})
        html = _get_text(f"https://duckduckgo.com/html/?{params}")
        for item in _parse_duckduckgo_results(html):
            title = _text(item.get("title"))
            url = _normalize_duckduckgo_url(_text(item.get("url")))
            snippet = _text(item.get("snippet"))
            if not title or not _is_public_http_url(url):
                continue
            if not _is_relevant_web_hit(query, title, snippet, topic):
                continue
            return ScholarlySearchHit(
                title=title,
                url=url,
                source=f"{_host(url)} · Web",
                reason=f"Web result for: {search_query}",
            )
    return None


def _general_search_queries(query: str, topic: str = "") -> list[str]:
    base = _general_query_base(query, topic)
    if not base:
        return []
    queries = [base]
    lower = base.lower()
    if any(keyword in lower for keyword in _general_web_terms()):
        queries.extend(
            [
                f"{base} official documentation",
                f"{base} tutorial",
                f"{base} course",
                f"{base} beginner guide",
            ]
        )
    if any(keyword in lower for keyword in ("interview", "\u9762\u8bd5")):
        queries.extend([f"{base} interview questions", f"{base} \u9762\u8bd5\u9898"])
    queries.extend(f"{base} site:{site}" for site in GENERAL_SEARCH_SITES[:8])
    seen: set[str] = set()
    result: list[str] = []
    for item in queries:
        cleaned = _clean_query(item)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result[:10]


def _parse_duckduckgo_results(html: str) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    blocks = re.findall(r'<div class="result(?: results_links_deep web-result)?".*?</div>\s*</div>', html, flags=re.S)
    if not blocks:
        blocks = re.findall(r'<a rel="nofollow" class="result__a".*?</a>.*?(?:<a class="result__snippet".*?</a>|</div>)', html, flags=re.S)
    for block in blocks:
        link_match = re.search(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', block, flags=re.S)
        if not link_match:
            continue
        snippet_match = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', block, flags=re.S)
        results.append(
            {
                "url": _html_unescape(link_match.group(1)),
                "title": _strip_html(link_match.group(2)),
                "snippet": _strip_html(snippet_match.group(1)) if snippet_match else "",
            }
        )
    return results


def _get_json(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "zhiyan-xinglian-learning-platform/0.1 (mailto:dev@example.com)",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode("utf-8"))
    except (TimeoutError, socket.timeout) as exc:
        raise ScholarlySourceUnavailable(f"resource search timeout: {url}") from exc
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise ScholarlySourceUnavailable(f"resource search HTTP {exc.code}: {detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise ScholarlySourceUnavailable(f"resource search connection error: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ScholarlySearchError("resource search returned invalid JSON") from exc


def _get_text(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "User-Agent": "Mozilla/5.0 (compatible; zhiyan-xinglian-learning-platform/0.1)",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return response.read().decode("utf-8", errors="ignore")
    except (TimeoutError, socket.timeout) as exc:
        raise ScholarlySourceUnavailable(f"resource search timeout: {url}") from exc
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise ScholarlySourceUnavailable(f"resource search HTTP {exc.code}: {detail[:300]}") from exc
    except urllib.error.URLError as exc:
        raise ScholarlySourceUnavailable(f"resource search connection error: {exc.reason}") from exc


def _reachable_page_title(url: str) -> Optional[str]:
    try:
        request = urllib.request.Request(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
                "User-Agent": "Mozilla/5.0 (compatible; zhiyan-xinglian-learning-platform/0.1)",
            },
            method="HEAD",
        )
        with urllib.request.urlopen(request, timeout=8) as response:
            if response.status >= 400:
                return None
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type:
                return ""
    except urllib.error.HTTPError as exc:
        if exc.code not in {403, 405}:
            return None
    except (TimeoutError, socket.timeout, urllib.error.URLError):
        return None

    try:
        html = _get_text(url)[:200000]
    except ScholarlySearchError:
        return ""
    title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    if not title_match:
        return ""
    return _strip_html(title_match.group(1))


def _prefer_general_web(query: str, topic: str = "") -> bool:
    text = f"{query} {topic}".lower()
    return any(term in text for term in _general_web_terms())


def _prefer_scholarly(query: str, topic: str = "") -> bool:
    text = f"{query} {topic}".lower()
    return any(
        term in text
        for term in (
            "paper",
            "papers",
            "survey",
            "review",
            "literature",
            "doi",
            "arxiv",
            "research",
            "experiment",
            "benchmark",
            "dataset",
            "citation",
            "\u8bba\u6587",
            "\u6587\u732e",
            "\u7efc\u8ff0",
            "\u79d1\u7814",
            "\u5b9e\u9a8c",
            "\u5f15\u7528",
            "\u6570\u636e\u96c6",
        )
    )


def _general_web_terms() -> tuple[str, ...]:
    return (
        "python",
        "\u540e\u7aef",
        "backend",
        "server",
        "api",
        "fastapi",
        "django",
        "flask",
        "\u9762\u8bd5",
        "interview",
        "\u8bfe\u7a0b",
        "course",
        "tutorial",
        "docs",
        "documentation",
        "guide",
        "beginner",
        "roadmap",
        "\u5165\u95e8",
        "\u5b66\u4e60",
    )


def _openalex_url(item: dict[str, Any]) -> str:
    doi = _text(item.get("doi"))
    if doi:
        return doi
    primary = item.get("primary_location") or {}
    landing_page = _text(primary.get("landing_page_url"))
    if landing_page:
        return landing_page
    open_access = item.get("open_access") or {}
    oa_url = _text(open_access.get("oa_url"))
    if oa_url:
        return oa_url
    return _text(item.get("id"))


def _authors(item: dict[str, Any]) -> str:
    names: list[str] = []
    for authorship in item.get("authorships") or []:
        author = authorship.get("author") or {}
        name = _text(author.get("display_name"))
        if name:
            names.append(name)
        if len(names) >= 2:
            break
    return ", ".join(names)


def _crossref_year(item: dict[str, Any]) -> str:
    parts = (((item.get("published-print") or item.get("published-online") or item.get("issued") or {}).get("date-parts")) or [])
    if parts and parts[0]:
        return str(parts[0][0])
    return ""


def _clean_query(value: str) -> str:
    text = re.sub(r"https?://\S+", " ", value)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:240]


def _general_query_base(query: str, topic: str = "") -> str:
    combined = " ".join(part for part in [topic, query] if part).strip()
    lower = combined.lower()
    technology_terms = [
        "python",
        "fastapi",
        "django",
        "flask",
        "javascript",
        "typescript",
        "vue",
        "react",
        "java",
        "spring",
        "linux",
        "docker",
        "kubernetes",
        "sql",
        "postgresql",
        "mysql",
        "machine learning",
        "deep learning",
    ]
    selected = [term for term in technology_terms if term in lower]
    if selected:
        intent_terms = []
        if any(term in lower for term in ("backend", "\u540e\u7aef")):
            intent_terms.append("backend")
        if any(term in lower for term in ("interview", "\u9762\u8bd5")):
            intent_terms.append("interview")
        if any(term in lower for term in ("course", "tutorial", "\u8bfe\u7a0b", "\u5165\u95e8", "\u5b66")):
            intent_terms.append("course tutorial")
        return " ".join([selected[0], *intent_terms]).strip()
    return combined


def _is_relevant_hit(query: str, title: str, topic: str = "") -> bool:
    query_tokens = _query_tokens(query)
    title_tokens = _query_tokens(title)
    if not query_tokens or not title_tokens:
        return False
    if query_tokens & title_tokens:
        return True
    topic_text = topic.lower()
    title_text = title.lower()
    technical_terms = [
        "u-net",
        "unet",
        "semantic segmentation",
        "image segmentation",
        "segmentation",
        "\u8bed\u4e49\u5206\u5272",
        "\u56fe\u50cf\u5206\u5272",
    ]
    required_terms = [term for term in technical_terms if term in topic_text or term in query.lower()]
    return bool(required_terms and any(term in title_text for term in required_terms))


def _is_relevant_web_hit(query: str, title: str, snippet: str = "", topic: str = "") -> bool:
    target_tokens = _query_tokens(f"{query} {topic}")
    hit_tokens = _query_tokens(f"{title} {snippet}")
    if not target_tokens or not hit_tokens:
        return False
    if target_tokens & hit_tokens:
        return True
    target_text = f"{query} {topic}".lower()
    hit_text = f"{title} {snippet}".lower()
    synonym_groups = [
        {"python", "py"},
        {"\u540e\u7aef", "backend", "server", "api", "fastapi", "django", "flask"},
        {"\u9762\u8bd5", "interview", "questions"},
        {"\u8bed\u4e49\u5206\u5272", "semantic", "segmentation", "u-net", "unet"},
        {"\u8bfe\u7a0b", "course", "tutorial", "guide", "docs", "documentation"},
    ]
    matched_groups = [group for group in synonym_groups if any(term in target_text for term in group)]
    if not matched_groups:
        return False
    return all(any(term in hit_text for term in group) for group in matched_groups[:3])


def _query_tokens(value: str) -> set[str]:
    text = value.lower()
    ascii_tokens = {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9\-]{2,}", text)
        if token not in STOPWORDS
    }
    cjk_tokens: set[str] = set()
    for phrase in re.findall(r"[\u4e00-\u9fff]{2,}", text):
        if len(phrase) <= 8:
            cjk_tokens.add(phrase)
        cjk_tokens.update(phrase[index : index + 2] for index in range(max(0, len(phrase) - 1)))
        cjk_tokens.update(phrase[index : index + 4] for index in range(max(0, len(phrase) - 3)))
    return ascii_tokens | cjk_tokens


def _normalize_duckduckgo_url(url: str) -> str:
    if url.startswith("//"):
        url = f"https:{url}"
    parsed = urllib.parse.urlparse(url)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        query = urllib.parse.parse_qs(parsed.query)
        uddg = query.get("uddg", [""])[0]
        if uddg:
            return urllib.parse.unquote(uddg)
    return url


def _normalize_candidate_url(url: str) -> str:
    value = _text(url)
    match = re.search(r"https?://[^\s\"'<>，。；、]+", value)
    if match:
        value = match.group(0)
    return _normalize_duckduckgo_url(value.rstrip(").,，。；;"))


def _is_public_http_url(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    host = parsed.hostname or ""
    return host not in {"localhost", "127.0.0.1", "0.0.0.0"}


def _host(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).netloc
    except Exception:
        return "Web"


def _strip_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value)
    return _html_unescape(re.sub(r"\s+", " ", text).strip())


def _html_unescape(value: str) -> str:
    return (
        value.replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#x27;", "'")
        .replace("&#39;", "'")
    )


def _text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()
