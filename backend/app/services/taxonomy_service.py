from __future__ import annotations

import json
import re
from collections import Counter, defaultdict, deque
from typing import Any, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.learning import (
    Course,
    CourseChapter,
    DocumentChunk,
    KnowledgeDocument,
    KnowledgeImportJob,
    KnowledgePoint,
    LearningProject,
    StudentProfileRecord,
)
from app.models.user import User
from app.schemas import KnowledgeLinkEdge, KnowledgeLinkGraphResponse, KnowledgeLinkNode
from app.services.knowledge_ingestion_service import _job_id_from_document_path
from app.services.platform_knowledge_service import PLATFORM_COURSE_CODE, ensure_platform_knowledge_points


GRAPH_ATTRIBUTION = "知识漏斗由当前用户上传知识库、项目知识点、平台功能介绍与学习画像动态聚合生成。"



def build_knowledge_link_graph(
    db: Session,
    user: User,
    *,
    project_id: Optional[int] = None,
    query: str = "",
    limit: int = 80,
) -> KnowledgeLinkGraphResponse:
    limit = max(40, min(limit, 220))
    projects = _load_projects(db, user, project_id=project_id)
    owned_course_codes = _load_owned_course_codes(db, user)
    owned_document_ids = _owned_document_ids(db, user, owned_course_codes)
    database_points = _load_database_points(db, owned_document_ids, query=query, limit=limit)
    platform_points = _load_platform_points(db, query=query)
    database_points = [*database_points, *platform_points]
    database_points = _compact_database_points(database_points, limit=limit)
    documents = _load_documents(db, owned_document_ids, query=query, limit=max(24, limit // 3))
    profile_data = _load_profile_data(db, user)

    nodes: dict[str, KnowledgeLinkNode] = {}
    project_nodes = _add_project_nodes(nodes, projects)
    document_nodes = _add_document_nodes(nodes, documents)
    kb_nodes = _add_knowledge_base_nodes(nodes, database_points)
    platform_nodes = [node for node in kb_nodes if node.layer == "platform"]

    edges: list[KnowledgeLinkEdge] = []
    edges.extend(_link_documents_to_points(document_nodes, kb_nodes))
    edges.extend(_link_projects_to_points(project_nodes, kb_nodes, document_nodes))
    edges.extend(_link_database_prerequisites(kb_nodes))
    edges.extend(_link_document_sequence_edges(db, owned_document_ids, kb_nodes))
    edges = _enforce_dag_edges(nodes, edges)
    _annotate_graph_topology(nodes, edges)

    path_suggestions = _build_path_suggestions(projects, database_points, profile_data)
    _annotate_path_membership(nodes, path_suggestions)

    deduped_edges = _dedupe_edges(edges)
    return KnowledgeLinkGraphResponse(
        nodes=list(nodes.values()),
        edges=deduped_edges,
        path_suggestions=path_suggestions,
        attribution=GRAPH_ATTRIBUTION,
        meta=_build_graph_meta(nodes, deduped_edges, path_suggestions, database_points, documents, profile_data),
    )


def _load_projects(db: Session, user: User, *, project_id: Optional[int]) -> list[LearningProject]:
    statement = select(LearningProject).where(LearningProject.user_id == user.id)
    if project_id is not None:
        statement = statement.where(LearningProject.id == project_id)
    projects = list(
        db.scalars(
            statement.order_by(LearningProject.updated_at.desc(), LearningProject.id.desc()).limit(24)
        ).all()
    )
    if project_id is not None and not projects:
        raise ValueError("learning project not found")
    return projects


def _load_owned_course_codes(db: Session, user: User) -> set[str]:
    codes = db.scalars(
        select(KnowledgeImportJob.course_code).where(KnowledgeImportJob.user_id == user.id)
    ).all()
    return {str(code) for code in codes if code}


def _owned_document_ids(db: Session, user: User, course_codes: set[str]) -> set[int]:
    if not course_codes:
        return set()
    documents = db.scalars(select(KnowledgeDocument).where(KnowledgeDocument.course_code.in_(course_codes))).all()
    result: set[int] = set()
    jobs_by_id = {
        job.id: job.user_id
        for job in db.scalars(select(KnowledgeImportJob).where(KnowledgeImportJob.user_id == user.id)).all()
    }
    for document in documents:
        job_id = _job_id_from_document_path(document.file_path)
        if job_id is not None and jobs_by_id.get(job_id) == user.id:
            result.add(document.id)
    return result


def _load_database_points(
    db: Session,
    document_ids: set[int],
    *,
    query: str,
    limit: int,
) -> list[dict[str, Any]]:
    if not document_ids:
        return []

    base_statement = (
        select(
            KnowledgePoint.id.label("point_id"),
            KnowledgePoint.name.label("name"),
            KnowledgePoint.description.label("description"),
            KnowledgePoint.prerequisites.label("prerequisites"),
            KnowledgePoint.tags.label("tags"),
            KnowledgePoint.difficulty.label("difficulty"),
            CourseChapter.id.label("chapter_id"),
            CourseChapter.title.label("chapter"),
            Course.title.label("course_title"),
            KnowledgeDocument.course_code.label("course_code"),
            func.count(DocumentChunk.id).label("chunk_count"),
            func.count(func.distinct(KnowledgeDocument.id)).label("document_count"),
            func.array_agg(func.distinct(KnowledgeDocument.title)).label("document_titles"),
            func.array_agg(func.distinct(KnowledgeDocument.doc_type)).label("document_types"),
            func.array_agg(func.distinct(DocumentChunk.section_title)).label("section_titles"),
            func.array_agg(KnowledgeDocument.parse_meta).label("document_parse_meta"),
        )
        .join(CourseChapter, KnowledgePoint.chapter_id == CourseChapter.id)
        .join(Course, Course.id == CourseChapter.course_id)
        .join(DocumentChunk, DocumentChunk.knowledge_point_id == KnowledgePoint.id)
        .join(KnowledgeDocument, KnowledgeDocument.id == DocumentChunk.document_id)
        .where(KnowledgeDocument.id.in_(document_ids))
        .group_by(
            KnowledgePoint.id,
            KnowledgePoint.name,
            KnowledgePoint.description,
            KnowledgePoint.prerequisites,
            KnowledgePoint.tags,
            KnowledgePoint.difficulty,
            CourseChapter.id,
            CourseChapter.title,
            Course.title,
            KnowledgeDocument.course_code,
        )
    )

    if query.strip():
        like = f"%{query.strip()}%"
        filtered = base_statement.where(
            KnowledgePoint.name.ilike(like)
            | KnowledgePoint.description.ilike(like)
            | CourseChapter.title.ilike(like)
            | Course.title.ilike(like)
            | KnowledgeDocument.title.ilike(like)
            | DocumentChunk.content.ilike(like)
        )
        rows = db.execute(
            filtered.order_by(func.count(DocumentChunk.id).desc(), KnowledgePoint.id).limit(limit)
        ).all()
        if rows:
            return [_clean_point_row(dict(row._mapping)) for row in rows]

    rows = db.execute(
        base_statement.order_by(func.count(DocumentChunk.id).desc(), KnowledgePoint.id).limit(limit)
    ).all()
    return [_clean_point_row(dict(row._mapping)) for row in rows]


def _load_documents(db: Session, document_ids: set[int], *, query: str, limit: int) -> list[dict[str, Any]]:
    if not document_ids:
        return []
    statement = (
        select(
            KnowledgeDocument.id.label("document_id"),
            KnowledgeDocument.title.label("title"),
            KnowledgeDocument.doc_type.label("doc_type"),
            KnowledgeDocument.summary.label("summary"),
            KnowledgeDocument.source_uri.label("source_uri"),
            KnowledgeDocument.course_code.label("course_code"),
            func.count(DocumentChunk.id).label("chunk_count"),
            func.count(func.distinct(DocumentChunk.knowledge_point_id)).label("point_count"),
        )
        .outerjoin(DocumentChunk, DocumentChunk.document_id == KnowledgeDocument.id)
        .where(KnowledgeDocument.id.in_(document_ids))
        .group_by(KnowledgeDocument.id)
    )
    if query.strip():
        like = f"%{query.strip()}%"
        statement = statement.where(
            KnowledgeDocument.title.ilike(like)
            | KnowledgeDocument.summary.ilike(like)
            | KnowledgeDocument.file_name.ilike(like)
            | DocumentChunk.content.ilike(like)
        )
    rows = db.execute(statement.order_by(KnowledgeDocument.created_at.desc()).limit(limit)).all()
    return [dict(row._mapping) for row in rows]


def _load_platform_points(db: Session, *, query: str) -> list[dict[str, Any]]:
    points = ensure_platform_knowledge_points(db, commit=False)
    query_value = query.strip().lower()
    rows: list[dict[str, Any]] = []
    for point in points:
        searchable = " ".join([point.name, point.description, " ".join(map(str, point.tags or []))]).lower()
        if query_value and query_value not in searchable:
            continue
        rows.append(
            _clean_point_row(
                {
                    "point_id": point.id,
                    "name": point.name,
                    "description": point.description,
                    "prerequisites": point.prerequisites,
                    "tags": point.tags,
                    "difficulty": point.difficulty,
                    "chapter_id": point.chapter_id,
                    "chapter": PLATFORM_COURSE_CODE,
                    "course_title": "平台功能介绍",
                    "course_code": PLATFORM_COURSE_CODE,
                    "chunk_count": 1,
                    "document_count": 0,
                    "document_titles": [],
                    "document_types": [],
                    "section_titles": [],
                    "document_parse_meta": [],
                    "source_kind": "platform",
                }
            )
        )
    return rows


def _load_profile_data(db: Session, user: User) -> dict[str, Any]:
    record = db.scalar(
        select(StudentProfileRecord)
        .where(StudentProfileRecord.user_id == user.id)
        .order_by(desc(StudentProfileRecord.updated_at))
    )
    return dict(record.profile_data or {}) if record else {}


def _clean_point_row(row: dict[str, Any]) -> dict[str, Any]:
    for key in ["document_titles", "document_types", "section_titles"]:
        row[key] = [str(item) for item in (row.get(key) or []) if item]
    row["document_parse_meta"] = [item for item in (row.get("document_parse_meta") or []) if isinstance(item, dict)]
    row["course_title"] = str(row.get("course_title") or row.get("chapter") or "知识库")
    row["course_code"] = str(row.get("course_code") or "")
    raw_tags = [str(item).strip() for item in row.get("tags") or [] if str(item).strip()]
    row["tags"] = raw_tags
    taxonomy = _taxonomy_meta_from_row(row)
    tags = [tag for tag in raw_tags if not _is_internal_tag(tag)]
    row["tags"] = tags
    row["taxonomy"] = taxonomy
    row["topic_type"] = taxonomy.get("type", "")
    row["assessment_prompt"] = taxonomy.get("assessment_prompt", "")
    row["source_kind"] = str(row.get("source_kind") or ("platform" if "platform_feature" in raw_tags else "rag"))
    return row


def _taxonomy_meta_from_row(row: dict[str, Any]) -> dict[str, Any]:
    tags = {str(item) for item in row.get("tags") or []}
    section_titles = [str(item) for item in row.get("section_titles") or [] if item]
    topic_meta = _topic_meta_from_parse_meta(row)
    type_tags = {"CONCEPTUAL", "PROCEDURAL", "REPRESENTATIONAL", "LANGUAGE", "META"}
    topic_type = str(topic_meta.get("type") or next((tag.upper() for tag in tags if tag.upper() in type_tags), ""))
    is_topic = "taxonomy_topic" in tags
    is_platform = "platform_feature" in tags
    return {
        "is_topic": is_topic,
        "type": topic_type,
        "subject": str(topic_meta.get("subject") or ""),
        "domain": str(topic_meta.get("domain") or ""),
        "evidence": [str(item) for item in topic_meta.get("evidence") or [] if item][:4],
        "assessment_prompt": str(topic_meta.get("assessment_prompt") or ""),
        "assessmentPrompt": str(topic_meta.get("assessmentPrompt") or topic_meta.get("assessment_prompt") or ""),
        "standards": [str(item) for item in topic_meta.get("standards") or [] if item][:6],
        "source_sections": section_titles[:6],
        "cleaning_policy": "platform-seed" if is_platform else "topic-first" if is_topic else "legacy-compacted",
    }


def _topic_meta_from_parse_meta(row: dict[str, Any]) -> dict[str, Any]:
    point_key = _taxonomy_topic_key(str(row.get("name") or ""))
    if not point_key:
        return {}
    seen_meta: set[str] = set()
    for meta in row.get("document_parse_meta") or []:
        meta_key = json.dumps(meta, ensure_ascii=False, sort_keys=True)
        if meta_key in seen_meta:
            continue
        seen_meta.add(meta_key)
        for topic in meta.get("taxonomy_topics") or []:
            if not isinstance(topic, dict):
                continue
            if _taxonomy_topic_key(str(topic.get("name") or "")) == point_key:
                return topic
    return {}


def _taxonomy_topic_key(value: str) -> str:
    return re.sub(r"[\s\-_:：/\\（）()【】\[\]·•]+", "", _normalize_label(value))


def _compact_database_points(rows: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    platform_rows = [row for row in rows if row.get("source_kind") == "platform"]
    taxonomy_rows = [row for row in rows if row.get("source_kind") != "platform" and row.get("taxonomy", {}).get("is_topic")]
    legacy_rows = [row for row in rows if row.get("source_kind") != "platform" and not row.get("taxonomy", {}).get("is_topic")]
    compacted_legacy = _compact_legacy_rows(legacy_rows) if legacy_rows else []
    result = [*platform_rows, *taxonomy_rows, *compacted_legacy]
    result.sort(
        key=lambda row: (
            0 if row.get("source_kind") == "platform" else 1,
            0 if row.get("taxonomy", {}).get("is_topic") else 1,
            -int(row.get("document_count") or 0),
            -int(row.get("chunk_count") or 0),
            str(row.get("name") or ""),
        )
    )
    return result[:limit]


def _compact_legacy_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[_legacy_topic_group_key(row)].append(row)
    compacted: list[dict[str, Any]] = []
    for key, group_rows in groups.items():
        ranked = sorted(group_rows, key=lambda row: (-int(row.get("chunk_count") or 0), len(str(row.get("name") or ""))))
        base = dict(ranked[0])
        if len(group_rows) == 1:
            compacted.append(base)
            continue
        names = [str(row.get("name") or "") for row in ranked if row.get("name")]
        descriptions = [str(row.get("description") or "") for row in ranked if row.get("description")]
        document_titles = _unique_flatten(row.get("document_titles") for row in group_rows)
        section_titles = _unique_flatten(row.get("section_titles") for row in group_rows)
        tags = _unique_flatten(row.get("tags") for row in group_rows)
        base["point_id"] = f"legacy:{abs(hash(key))}"
        base["name"] = _compact_legacy_topic_name(names, document_titles, base)
        base["description"] = _compact_text("；".join(descriptions), limit=360) or _compact_text("；".join(names), limit=240)
        base["chunk_count"] = sum(int(row.get("chunk_count") or 0) for row in group_rows)
        base["document_count"] = len({title for title in document_titles if title}) or int(base.get("document_count") or 1)
        base["document_titles"] = document_titles[:8]
        base["section_titles"] = section_titles[:10]
        base["tags"] = [*tags, "legacy_compacted"][:12]
        base["prerequisites"] = []
        base["taxonomy"] = {
            "is_topic": False,
            "type": "",
            "source_sections": section_titles[:6],
            "cleaning_policy": "legacy-compacted",
            "compacted_from": len(group_rows),
        }
        compacted.append(base)
    return compacted


def _legacy_topic_group_key(row: dict[str, Any]) -> str:
    titles = [str(item) for item in row.get("document_titles") or [] if item]
    course = str(row.get("course_code") or row.get("course_title") or "")
    chapter = str(row.get("chapter") or "")
    text = " ".join([str(row.get("name") or ""), str(row.get("description") or ""), chapter])
    tokens = _token_set(text)
    stable_terms = sorted(set(token for token in tokens if len(token) >= 2))[:3]
    doc_key = titles[0] if titles else course
    return "|".join([course, doc_key, chapter, "-".join(stable_terms)])


def _compact_legacy_topic_name(names: list[str], document_titles: list[str], row: dict[str, Any]) -> str:
    usable = [
        _normalize_label(name)
        for name in names
        if name and not re.fullmatch(r"(slide|page|section)?\s*\d+", name.strip(), flags=re.IGNORECASE)
    ]
    if usable:
        common = Counter(usable).most_common(1)[0][0]
        return _compact_text(common, limit=48)
    if document_titles:
        return _compact_text(document_titles[0], limit=42) + "核心知识"
    return _compact_text(str(row.get("chapter") or row.get("course_title") or "资料核心知识"), limit=48)


def _unique_flatten(values: Any) -> list[str]:
    result: list[str] = []
    for value in values:
        items = value if isinstance(value, list) else [value]
        for item in items:
            text = str(item or "").strip()
            if text and text not in result:
                result.append(text)
    return result


def _point_category(row: dict[str, Any]) -> str:
    course_title = str(row.get("course_title") or "").strip()
    if course_title and course_title not in {"个人知识库", "导入课件资料", "知识库"}:
        return course_title
    tags = [str(item).strip() for item in row.get("tags") or [] if str(item).strip()]
    for tag in tags:
        if not _is_internal_tag(tag) and tag not in {"知识库", "个人知识库"}:
            return tag
    chapter = str(row.get("chapter") or "").strip()
    if chapter and chapter != "导入课件资料":
        return chapter
    titles = [str(item).strip() for item in row.get("document_titles") or [] if str(item).strip()]
    if titles:
        return titles[0][:80]
    return "知识点"


def _is_internal_tag(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    if not normalized:
        return True
    if normalized in {
        "imported",
        "taxonomy_topic",
        "legacy_compacted",
        "courseware",
        "platform_feature",
        "conceptual_mastery",
        "procedural_mastery",
        "representational_mastery",
        "language_mastery",
        "meta_mastery",
    }:
        return True
    return normalized.endswith("_mastery") or normalized.startswith("taxonomy_")


def _add_project_nodes(nodes: dict[str, KnowledgeLinkNode], projects: list[LearningProject]) -> list[KnowledgeLinkNode]:
    result: list[KnowledgeLinkNode] = []
    for project in projects:
        label = project.title or project.research_direction or "学习项目"
        node = KnowledgeLinkNode(
            id=f"project:{project.id}",
            label=label,
            layer="project",
            category=project.goal_type or project.subject or "learning_project",
            description=_compact_text(
                project.learning_goal
                or project.foundation_summary
                or project.expected_output
                or project.research_direction,
                limit=180,
            ),
            weight=max(4, len(_project_terms(project)) + 2),
            meta={
                "project_id": project.id,
                "direction_id": project.direction_id,
                "status": project.status,
                "subject": project.subject,
                "goal_type": project.goal_type,
                "progress": project.progress,
                "daily_minutes": project.daily_minutes,
                "related_knowledge_points": list(project.related_knowledge_points or []),
                "related_documents": list(project.related_documents or []),
                "weak_points": list(project.current_weak_points or []),
                "personalization_strategy": list(project.personalization_strategy or []),
                "source_kind": "project",
            },
        )
        nodes[node.id] = node
        result.append(node)
    return result


def _add_document_nodes(nodes: dict[str, KnowledgeLinkNode], rows: list[dict[str, Any]]) -> list[KnowledgeLinkNode]:
    result: list[KnowledgeLinkNode] = []
    for row in rows:
        node = KnowledgeLinkNode(
            id=f"doc:{row['document_id']}",
            label=str(row.get("title") or "知识库文档"),
            layer="document",
            category=str(row.get("doc_type") or "document"),
            description=str(row.get("summary") or ""),
            weight=max(2, int(row.get("chunk_count") or 1)),
            meta={
                "document_id": row.get("document_id"),
                "source_uri": row.get("source_uri", ""),
                "course_code": row.get("course_code", ""),
                "chunk_count": int(row.get("chunk_count") or 0),
                "point_count": int(row.get("point_count") or 0),
                "source_kind": "document",
            },
        )
        nodes[node.id] = node
        result.append(node)
    return result


def _add_knowledge_base_nodes(nodes: dict[str, KnowledgeLinkNode], rows: list[dict[str, Any]]) -> list[KnowledgeLinkNode]:
    result: list[KnowledgeLinkNode] = []
    for row in rows:
        point_name = str(row["name"])
        category = _point_category(row)
        source_kind = str(row.get("source_kind") or "rag")
        layer = "platform" if source_kind == "platform" else "knowledge_base"
        node_id = _node_id_for_row(row)
        node = KnowledgeLinkNode(
            id=node_id,
            label=point_name,
            layer=layer,
            category=category,
            description=str(row.get("description") or ""),
            weight=max(1, int(row.get("chunk_count") or 1)),
            meta={
                "point_id": row.get("point_id"),
                "chapter_id": row.get("chapter_id"),
                "chapter": row.get("chapter", ""),
                "course_title": row.get("course_title", ""),
                "course_code": row.get("course_code", ""),
                "category": category,
                "chunk_count": int(row.get("chunk_count") or 0),
                "document_count": int(row.get("document_count") or 0),
                "document_titles": row.get("document_titles") or [],
                "document_types": row.get("document_types") or [],
                "section_titles": [item for item in (row.get("section_titles") or []) if item][:8],
                "tags": list(row.get("tags") or []),
                "prerequisites": list(row.get("prerequisites") or []),
                "difficulty": row.get("difficulty", "medium"),
                "evidence": _evidence_for_point(row),
                "taxonomy": row.get("taxonomy") or {},
                "topic_type": row.get("topic_type", ""),
                "assessment_prompt": row.get("assessment_prompt", ""),
                "assessmentPrompt": (row.get("taxonomy") or {}).get("assessmentPrompt", ""),
                "standards": (row.get("taxonomy") or {}).get("standards", []),
                "source_kind": source_kind,
            },
        )
        nodes[node.id] = node
        result.append(node)
    return result


def _node_id_for_row(row: dict[str, Any]) -> str:
    prefix = "platform" if row.get("source_kind") == "platform" else "kb"
    return f"{prefix}:{row.get('point_id')}"


def _link_documents_to_points(
    document_nodes: list[KnowledgeLinkNode],
    kb_nodes: list[KnowledgeLinkNode],
) -> list[KnowledgeLinkEdge]:
    by_title = {node.label: node for node in document_nodes}
    edges: list[KnowledgeLinkEdge] = []
    for point in kb_nodes:
        if point.layer == "platform":
            continue
        for title in point.meta.get("document_titles", []) or []:
            document = by_title.get(str(title))
            if not document:
                continue
            edges.append(
                KnowledgeLinkEdge(
                    source=document.id,
                    target=point.id,
                    relation="evidence",
                    strength="medium",
                    reason="该知识点由文档片段提供证据",
                )
            )
    return edges


def _link_projects_to_points(
    project_nodes: list[KnowledgeLinkNode],
    kb_nodes: list[KnowledgeLinkNode],
    document_nodes: list[KnowledgeLinkNode],
) -> list[KnowledgeLinkEdge]:
    edges: list[KnowledgeLinkEdge] = []
    for project in project_nodes:
        project_terms = _token_set(
            project.label,
            project.description,
            project.category,
            " ".join(map(str, project.meta.get("related_knowledge_points", []))),
            " ".join(map(str, project.meta.get("related_documents", []))),
            " ".join(map(str, project.meta.get("weak_points", []))),
        )
        for kb_node in kb_nodes:
            if _node_related(project_terms, _node_terms(kb_node)):
                edges.append(
                    KnowledgeLinkEdge(
                        source=project.id,
                        target=kb_node.id,
                        relation="focuses",
                        strength="strong",
                        reason="项目目标或薄弱点命中知识库知识点",
                    )
                )
        for document in document_nodes:
            if _node_related(project_terms, _node_terms(document)):
                edges.append(
                    KnowledgeLinkEdge(
                        source=project.id,
                        target=document.id,
                        relation="evidence",
                        strength="medium",
                        reason="项目目标命中上传资料",
                    )
                )
    return edges


def _link_database_prerequisites(kb_nodes: list[KnowledgeLinkNode]) -> list[KnowledgeLinkEdge]:
    by_label = {_normalize_label(node.label): node for node in kb_nodes}
    edges: list[KnowledgeLinkEdge] = []
    for node in kb_nodes:
        for prereq in node.meta.get("prerequisites", []) or []:
            source = by_label.get(_normalize_label(str(prereq)))
            if source:
                edges.append(
                    KnowledgeLinkEdge(
                        source=source.id,
                        target=node.id,
                        relation="prerequisite",
                        strength="hard",
                        reason="知识库解析出的先修关系",
                    )
                )
    return edges


def _link_document_sequence_edges(
    db: Session,
    document_ids: set[int],
    kb_nodes: list[KnowledgeLinkNode],
) -> list[KnowledgeLinkEdge]:
    by_id = {str(node.meta.get("point_id")): node for node in kb_nodes if node.meta.get("source_kind") != "platform"}
    if not document_ids or not by_id:
        return []
    chunks = db.execute(
        select(
            DocumentChunk.document_id,
            DocumentChunk.knowledge_point_id,
            DocumentChunk.chunk_index,
            DocumentChunk.section_title,
        )
        .where(DocumentChunk.document_id.in_(document_ids), DocumentChunk.knowledge_point_id.is_not(None))
        .order_by(DocumentChunk.document_id, DocumentChunk.chunk_index)
    ).all()
    points_by_doc: dict[int, list[str]] = defaultdict(list)
    for document_id, point_id, _chunk_index, _section_title in chunks:
        point_key = str(point_id)
        if point_key in by_id:
            points_by_doc[int(document_id)].append(point_key)

    pair_counts: Counter[tuple[str, str]] = Counter()
    for point_ids in points_by_doc.values():
        compact = []
        for point_id in point_ids:
            if not compact or compact[-1] != point_id:
                compact.append(point_id)
        for left, right in zip(compact, compact[1:]):
            if left != right:
                pair_counts[(left, right)] += 1

    edges: list[KnowledgeLinkEdge] = []
    for (left, right), count in pair_counts.most_common(220):
        left_node = by_id.get(left)
        right_node = by_id.get(right)
        if not left_node or not right_node:
            continue
        edges.append(
            KnowledgeLinkEdge(
                source=left_node.id,
                target=right_node.id,
                relation="prerequisite",
                strength="hard" if count >= 2 else "soft",
                reason=f"按上传资料中的出现顺序推断：前者应先理解，再进入后者（出现 {count} 次）。",
            )
        )
    return edges


def _enforce_dag_edges(
    nodes: dict[str, KnowledgeLinkNode],
    edges: list[KnowledgeLinkEdge],
) -> list[KnowledgeLinkEdge]:
    seen: set[tuple[str, str, str]] = set()
    graph: dict[str, set[str]] = defaultdict(set)
    result: list[KnowledgeLinkEdge] = []
    priority = {"prerequisite": 0, "evidence": 1, "focuses": 2}
    for edge in sorted(edges, key=lambda item: priority.get(item.relation, 9)):
        if edge.source == edge.target:
            continue
        if edge.source not in nodes or edge.target not in nodes:
            continue
        key = (edge.source, edge.target, edge.relation)
        if key in seen:
            continue
        if edge.relation == "prerequisite" and _has_path(graph, edge.target, edge.source):
            continue
        seen.add(key)
        result.append(edge)
        if edge.relation == "prerequisite":
            graph[edge.source].add(edge.target)
    prerequisite_edges = [edge for edge in result if edge.relation == "prerequisite"]
    evidence_edges = [edge for edge in result if edge.relation == "evidence"]
    focus_edges = [edge for edge in result if edge.relation == "focuses"]
    return [*prerequisite_edges[:420], *focus_edges[:90], *evidence_edges[:140]][:620]


def _has_path(graph: dict[str, set[str]], start: str, target: str) -> bool:
    stack = [start]
    visited: set[str] = set()
    while stack:
        current = stack.pop()
        if current == target:
            return True
        if current in visited:
            continue
        visited.add(current)
        stack.extend(graph.get(current, set()) - visited)
    return False


def _annotate_graph_topology(nodes: dict[str, KnowledgeLinkNode], edges: list[KnowledgeLinkEdge]) -> None:
    prerequisite_edges = [edge for edge in edges if edge.relation == "prerequisite"]
    incoming: dict[str, int] = {node_id: 0 for node_id in nodes}
    outgoing: dict[str, int] = {node_id: 0 for node_id in nodes}
    prereq_degree: dict[str, int] = {node_id: 0 for node_id in nodes}
    children: dict[str, list[str]] = defaultdict(list)
    for edge in edges:
        outgoing[edge.source] = outgoing.get(edge.source, 0) + 1
        incoming[edge.target] = incoming.get(edge.target, 0) + 1
        if edge.relation == "prerequisite":
            children[edge.source].append(edge.target)
            prereq_degree[edge.source] = prereq_degree.get(edge.source, 0) + 1
            prereq_degree[edge.target] = prereq_degree.get(edge.target, 0) + 1

    prereq_incoming: dict[str, int] = {node_id: 0 for node_id in nodes}
    for edge in prerequisite_edges:
        prereq_incoming[edge.target] += 1

    queue = deque([node_id for node_id, count in prereq_incoming.items() if count == 0])
    levels: dict[str, int] = {node_id: 0 for node_id in queue}
    while queue:
        node_id = queue.popleft()
        for child in children.get(node_id, []):
            levels[child] = max(levels.get(child, 0), levels.get(node_id, 0) + 1)
            prereq_incoming[child] -= 1
            if prereq_incoming[child] <= 0:
                queue.append(child)

    for node_id, node in nodes.items():
        degree = incoming.get(node_id, 0) + outgoing.get(node_id, 0)
        node.meta["in_degree"] = incoming.get(node_id, 0)
        node.meta["out_degree"] = outgoing.get(node_id, 0)
        node.meta["degree"] = degree
        node.meta["prerequisite_degree"] = prereq_degree.get(node_id, 0)
        node.meta["dag_level"] = levels.get(node_id, 0)
        node.meta["is_isolated"] = prereq_degree.get(node_id, 0) == 0 and node.layer == "knowledge_base"


def _build_path_suggestions(
    projects: list[LearningProject],
    rows: list[dict[str, Any]],
    profile_data: dict[str, Any],
) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    for project in projects:
        ranked = _rank_rows_for_project(rows, project, profile_data)
        steps = [
            {
                "id": _node_id_for_row(row),
                "label": str(row.get("name") or ""),
                "layer": "platform" if row.get("source_kind") == "platform" else "knowledge_base",
                "reason": _kb_path_reason(row, project, profile_data),
                "phase": _phase_for_difficulty(str(row.get("difficulty") or "")),
                "estimated_minutes": _estimated_minutes(row, project, profile_data),
                "evidence": _evidence_for_point(row),
            }
            for row in ranked[:18]
        ]
        suggestions.append(
            {
                "project_id": project.id,
                "project_title": project.title,
                "strategy": _personalized_strategy(project, profile_data),
                "dynamic_signals": _dynamic_signals(project, profile_data),
                "steps": _number_path_steps(_dedupe_path_steps(steps)),
            }
        )

    if not suggestions and rows:
        ranked = _rank_rows_for_database(rows, profile_data)
        suggestions.append(
            {
                "project_id": None,
                "project_title": "全部知识库",
                "strategy": "按上传资料证据量、先修关系、难度和学习画像动态排序，优先学习证据充分且更基础的知识点。",
                "dynamic_signals": _dynamic_signals(None, profile_data),
                "steps": _number_path_steps(
                    [
                        {
                            "id": _node_id_for_row(row),
                            "label": str(row.get("name") or ""),
                            "layer": "platform" if row.get("source_kind") == "platform" else "knowledge_base",
                            "reason": _generic_kb_path_reason(row, profile_data),
                            "phase": _phase_for_difficulty(str(row.get("difficulty") or "")),
                            "estimated_minutes": _estimated_minutes(row, None, profile_data),
                            "evidence": _evidence_for_point(row),
                        }
                        for row in ranked[:18]
                    ]
                ),
            }
        )

    return suggestions


def _rank_rows_for_project(
    rows: list[dict[str, Any]],
    project: LearningProject,
    profile_data: dict[str, Any],
) -> list[dict[str, Any]]:
    project_terms = _token_set(
        *_project_terms(project),
        " ".join(map(str, project.current_weak_points or [])),
        " ".join(map(str, project.personalization_strategy or [])),
        " ".join(_profile_terms(profile_data)),
    )
    scored: list[tuple[float, str, dict[str, Any]]] = []
    for row in rows:
        row_terms = _token_set(
            str(row.get("name") or ""),
            str(row.get("description") or ""),
            str(row.get("chapter") or ""),
            " ".join(row.get("document_titles") or []),
            " ".join(map(str, row.get("tags") or [])),
        )
        overlap = len(set(project_terms) & set(row_terms))
        score = overlap * 5 + int(row.get("chunk_count") or 0) * 0.35 + int(row.get("document_count") or 0)
        score += _difficulty_rank(str(row.get("difficulty") or "medium")) * 0.4
        scored.append((score, str(row.get("name") or ""), row))
    scored.sort(key=lambda item: (-item[0], _difficulty_rank(str(item[2].get("difficulty") or "")), item[1]))
    return [row for _score, _name, row in scored]


def _rank_rows_for_database(rows: list[dict[str, Any]], profile_data: dict[str, Any]) -> list[dict[str, Any]]:
    profile_terms = _token_set(" ".join(_profile_terms(profile_data)))
    scored: list[tuple[float, str, dict[str, Any]]] = []
    for row in rows:
        row_terms = _token_set(str(row.get("name") or ""), str(row.get("description") or ""), str(row.get("chapter") or ""))
        score = int(row.get("chunk_count") or 0) * 0.6 + int(row.get("document_count") or 0) * 1.2
        score += len(set(profile_terms) & set(row_terms)) * 4
        score += (3 - _difficulty_rank(str(row.get("difficulty") or "medium"))) * 0.7
        scored.append((score, str(row.get("name") or ""), row))
    scored.sort(key=lambda item: (-item[0], _difficulty_rank(str(item[2].get("difficulty") or "")), item[1]))
    return [row for _score, _name, row in scored]


def _annotate_path_membership(nodes: dict[str, KnowledgeLinkNode], suggestions: list[dict[str, Any]]) -> None:
    for suggestion_index, suggestion in enumerate(suggestions):
        for step in suggestion.get("steps", []):
            node = nodes.get(str(step.get("id") or ""))
            if not node:
                continue
            path_meta = dict(node.meta.get("path") or {})
            path_meta.update(
                {
                    "suggestion_index": suggestion_index,
                    "project_id": suggestion.get("project_id"),
                    "order": step.get("order"),
                    "phase": step.get("phase"),
                    "reason": step.get("reason"),
                    "estimated_minutes": step.get("estimated_minutes"),
                }
            )
            node.meta["path"] = path_meta


def _build_graph_meta(
    nodes: dict[str, KnowledgeLinkNode],
    edges: list[KnowledgeLinkEdge],
    suggestions: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    documents: list[dict[str, Any]],
    profile_data: dict[str, Any],
) -> dict[str, Any]:
    chapters: dict[str, int] = {}
    documents_by_type: dict[str, int] = {}
    for node in nodes.values():
        if node.layer == "knowledge_base":
            chapter = str(node.meta.get("chapter") or "未分组")
            chapters[chapter] = chapters.get(chapter, 0) + 1
        if node.layer == "document":
            doc_type = str(node.category or "document")
            documents_by_type[doc_type] = documents_by_type.get(doc_type, 0) + 1
    topic_rows = [row for row in rows if row.get("taxonomy", {}).get("is_topic")]
    compacted_rows = [row for row in rows if row.get("taxonomy", {}).get("cleaning_policy") == "legacy-compacted"]
    return {
        "graph_source": "user_knowledge_base",
        "knowledge_point_count": len(rows),
        "taxonomy_topic_count": len(topic_rows),
        "legacy_compacted_count": len(compacted_rows),
        "document_count": len(documents),
        "platform_feature_count": len([node for node in nodes.values() if node.layer == "platform"]),
        "document_types": documents_by_type,
        "chapter_subjects": chapters,
        "taxonomy_selected_topics": len(topic_rows),
        "taxonomy_total_topics": len(rows),
        "taxonomy_subjects": dict(Counter(str(row.get("course_title") or "知识库") for row in rows)),
        "edge_count": len(edges),
        "dag_edge_count": len([edge for edge in edges if edge.relation == "prerequisite"]),
        "isolated_count": len([node for node in nodes.values() if node.meta.get("is_isolated")]),
        "path_count": len(suggestions),
        "profile_signals": _dynamic_signals(None, profile_data),
    }


def _project_terms(project: LearningProject) -> list[str]:
    values = [
        project.title,
        project.research_direction,
        project.subject,
        project.goal_type,
        project.related_course,
        project.learning_goal,
        project.foundation_summary,
        project.expected_output,
        *list(project.related_knowledge_points or []),
        *list(project.related_documents or []),
    ]
    return _unique_terms(values, limit=36)


def _profile_terms(profile_data: dict[str, Any]) -> list[str]:
    values: list[str] = []
    for key in [
        "knowledge_base",
        "learning_goal",
        "weak_points",
        "resource_preference",
        "learning_pace",
        "interest_direction",
        "current_research_direction",
        "mastery",
        "output_goal",
    ]:
        value = profile_data.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif isinstance(value, dict):
            values.extend(str(item) for item in value.values())
        elif value:
            values.append(str(value))
    return values


def _node_terms(node: KnowledgeLinkNode) -> list[str]:
    return _token_set(
        node.label,
        node.description,
        node.category,
        " ".join(map(str, node.meta.get("tags", []))),
        " ".join(map(str, node.meta.get("prerequisites", []))),
        " ".join(map(str, node.meta.get("document_titles", []))),
    )


def _unique_terms(values: list[str], *, limit: int) -> list[str]:
    result: list[str] = []
    for value in values:
        text = " ".join(str(value or "").split())
        if text and text not in result:
            result.append(text)
    return result[:limit]


def _token_set(*values: str) -> list[str]:
    text = " ".join(str(value or "") for value in values).lower()
    ascii_tokens = [part for part in text.replace("_", " ").replace("-", " ").split() if len(part) >= 2]
    cjk_tokens = [
        text[index : index + 2]
        for index in range(max(0, len(text) - 1))
        if any("\u4e00" <= char <= "\u9fff" for char in text[index : index + 2])
    ]
    cjk_tokens.extend([char for char in text if "\u4e00" <= char <= "\u9fff"])
    return ascii_tokens + cjk_tokens


def _node_related(left_tokens: list[str], right_tokens: list[str]) -> bool:
    return bool(set(left_tokens) & set(right_tokens))


def _compact_text(value: str, *, limit: int = 84) -> str:
    return " ".join(str(value or "").split())[:limit]


def _evidence_for_point(row: dict[str, Any]) -> list[str]:
    evidence: list[str] = []
    titles = [str(item) for item in row.get("document_titles") or [] if item]
    sections = [str(item) for item in row.get("section_titles") or [] if item]
    taxonomy = row.get("taxonomy") or {}
    if taxonomy.get("cleaning_policy"):
        policy = taxonomy.get("cleaning_policy")
        evidence.append(f"清洗策略：{policy}")
    if titles:
        evidence.append("资料来源：" + "、".join(titles[:3]))
    if sections:
        evidence.append("证据位置：" + "、".join(sections[:3]))
    if row.get("description"):
        evidence.append(str(row.get("description"))[:160])
    return evidence[:3]


def _dedupe_path_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []
    for step in steps:
        node_id = str(step.get("id") or "")
        if not node_id or node_id in seen:
            continue
        seen.add(node_id)
        result.append(step)
    return result


def _number_path_steps(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**step, "order": index + 1} for index, step in enumerate(steps)]


def _dedupe_edges(edges: list[KnowledgeLinkEdge]) -> list[KnowledgeLinkEdge]:
    seen: set[tuple[str, str, str]] = set()
    result: list[KnowledgeLinkEdge] = []
    for edge in edges:
        key = (edge.source, edge.target, edge.relation)
        if key in seen:
            continue
        seen.add(key)
        result.append(edge)
    return result[:620]


def _kb_path_reason(row: dict[str, Any], project: LearningProject, profile_data: dict[str, Any]) -> str:
    parts = ["知识库已有可回看证据"]
    chunk_count = int(row.get("chunk_count") or 0)
    document_count = int(row.get("document_count") or 0)
    if row.get("taxonomy", {}).get("is_topic"):
        parts.append("已归并为核心知识点")
    if chunk_count:
        parts.append(f"覆盖 {chunk_count} 个片段")
    if document_count:
        parts.append(f"来自 {document_count} 份资料")
    weak_terms = _token_set(
        " ".join(map(str, project.current_weak_points or [])),
        " ".join(map(str, profile_data.get("weak_points") or [])),
    )
    row_terms = _token_set(str(row.get("name") or ""), str(row.get("description") or ""), str(row.get("chapter") or ""))
    if set(weak_terms) & set(row_terms):
        parts.append("命中薄弱点")
    return "；".join(parts) + "。"


def _generic_kb_path_reason(row: dict[str, Any], profile_data: dict[str, Any]) -> str:
    parts = ["按上传资料中的证据量和难度排序"]
    if row.get("taxonomy", {}).get("is_topic"):
        parts.append("该节点是清洗归并后的核心知识点")
    elif row.get("taxonomy", {}).get("cleaning_policy") == "legacy-compacted":
        parts.append("旧导入资料已在图谱层降噪归并")
    if row.get("document_count"):
        document_count = int(row.get("document_count") or 0)
        parts.append(f"覆盖 {document_count} 份资料")
    profile_terms = _token_set(" ".join(_profile_terms(profile_data)))
    row_terms = _token_set(str(row.get("name") or ""), str(row.get("description") or ""))
    if set(profile_terms) & set(row_terms):
        parts.append("与学习画像相关")
    return "；".join(parts) + "。"


def _phase_for_difficulty(difficulty: str) -> str:
    normalized = difficulty.lower()
    if normalized in {"easy", "基础", "low"}:
        return "基础建构"
    if normalized in {"hard", "困难", "high"}:
        return "迁移应用"
    return "概念连接"


def _difficulty_rank(difficulty: str) -> int:
    normalized = difficulty.lower()
    if normalized in {"easy", "基础", "low"}:
        return 0
    if normalized in {"hard", "困难", "high"}:
        return 2
    return 1


def _estimated_minutes(item: Any, project: Optional[LearningProject], profile_data: dict[str, Any]) -> int:
    base = 35
    if isinstance(item, dict) and str(item.get("difficulty") or "").lower() in {"hard", "困难", "high"}:
        base += 15
    if isinstance(item, dict) and int(item.get("chunk_count") or 0) >= 6:
        base += 10
    pace = str(profile_data.get("learning_pace") or "").lower()
    if any(flag in pace for flag in ["slow", "慢", "稳"]):
        base += 10
    if any(flag in pace for flag in ["fast", "快"]):
        base -= 5
    if project and project.daily_minutes:
        return max(20, min(int(project.daily_minutes), base))
    return max(20, base)


def _personalized_strategy(project: LearningProject, profile_data: dict[str, Any]) -> str:
    signals = _dynamic_signals(project, profile_data)
    if not signals:
        return "按项目目标、上传资料证据量、先修关系和知识点难度动态排序。"
    return "结合 " + "、".join(signals[:4]) + "，优先安排有资料证据支撑且能补齐基础依赖的知识点。"


def _dynamic_signals(project: Optional[LearningProject], profile_data: dict[str, Any]) -> list[str]:
    signals: list[str] = []
    if project:
        if project.current_weak_points:
            signals.append("项目薄弱点")
        if project.progress:
            signals.append(f"项目进度 {project.progress}%")
        if project.daily_minutes:
            signals.append(f"每日 {project.daily_minutes} 分钟")
        if project.personalization_strategy:
            signals.append("项目个性化策略")
    for label, key in [
        ("画像薄弱点", "weak_points"),
        ("学习节奏", "learning_pace"),
        ("资源偏好", "resource_preference"),
        ("兴趣方向", "interest_direction"),
    ]:
        if profile_data.get(key):
            signals.append(label)
    return signals


def _normalize_label(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").replace("-", " ").split())

