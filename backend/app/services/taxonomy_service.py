from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.learning import (
    CourseChapter,
    DocumentChunk,
    KnowledgeDocument,
    KnowledgePoint,
    LearningProject,
    StudentProfileRecord,
)
from app.models.user import User
from app.schemas import KnowledgeLinkEdge, KnowledgeLinkGraphResponse, KnowledgeLinkNode


TAXONOMY_ATTRIBUTION = (
    "Marble Skill Taxonomy (v1) / withmarbleapp os-taxonomy / "
    "licensed under ODbL 1.0 (database) and CC BY-SA 4.0 (content)."
)
DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "os_taxonomy"


def build_knowledge_link_graph(
    db: Session,
    user: User,
    *,
    project_id: Optional[int] = None,
    query: str = "",
    limit: int = 80,
) -> KnowledgeLinkGraphResponse:
    limit = max(40, min(limit, 220))
    taxonomy = _load_taxonomy()
    projects = _load_projects(db, user, project_id=project_id)
    database_points = _load_database_points(db, query=query, limit=limit)
    profile_data = _load_profile_data(db, user)

    nodes: dict[str, KnowledgeLinkNode] = {}
    project_nodes = _add_project_nodes(nodes, projects)
    kb_nodes = _add_knowledge_base_nodes(nodes, database_points)

    focus_terms = _collect_focus_terms(projects, database_points, query, profile_data)
    taxonomy_ids = _select_taxonomy_topics(taxonomy, focus_terms, limit=limit)
    tax_nodes = _add_taxonomy_nodes(nodes, taxonomy, taxonomy_ids)

    edges: list[KnowledgeLinkEdge] = []
    edges.extend(_link_project_edges(project_nodes, kb_nodes, tax_nodes))
    edges.extend(_link_database_prerequisites(kb_nodes))
    edges.extend(_link_dependency_edges(taxonomy, tax_nodes))

    path_suggestions = _build_path_suggestions(
        projects,
        database_points,
        taxonomy,
        taxonomy_ids,
        profile_data,
    )
    _annotate_path_membership(nodes, path_suggestions)

    return KnowledgeLinkGraphResponse(
        nodes=list(nodes.values()),
        edges=_dedupe_edges(edges),
        path_suggestions=path_suggestions,
        attribution=TAXONOMY_ATTRIBUTION,
        meta=_build_graph_meta(taxonomy, nodes, edges, path_suggestions, profile_data),
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


def _load_database_points(db: Session, *, query: str, limit: int) -> list[dict[str, Any]]:
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
            KnowledgeDocument.title.label("course_title"),
            func.count(DocumentChunk.id).label("chunk_count"),
            func.count(func.distinct(KnowledgeDocument.id)).label("document_count"),
        )
        .join(CourseChapter, KnowledgePoint.chapter_id == CourseChapter.id)
        .join(KnowledgeDocument, KnowledgeDocument.course_id == CourseChapter.course_id)
        .join(DocumentChunk, DocumentChunk.knowledge_point_id == KnowledgePoint.id, isouter=True)
        .group_by(
            KnowledgePoint.id,
            KnowledgePoint.name,
            KnowledgePoint.description,
            KnowledgePoint.prerequisites,
            KnowledgePoint.tags,
            KnowledgePoint.difficulty,
            CourseChapter.id,
            CourseChapter.title,
            KnowledgeDocument.title,
        )
    )

    if query.strip():
        like = f"%{query.strip()}%"
        filtered = base_statement.where(
            KnowledgePoint.name.ilike(like)
            | KnowledgePoint.description.ilike(like)
            | CourseChapter.title.ilike(like)
            | KnowledgeDocument.title.ilike(like)
            | DocumentChunk.content.ilike(like)
        )
        rows = db.execute(filtered.order_by(CourseChapter.order_index, KnowledgePoint.id).limit(limit)).all()
        if rows:
            return [dict(row._mapping) for row in rows]

    rows = db.execute(base_statement.order_by(CourseChapter.order_index, KnowledgePoint.id).limit(limit)).all()
    return [dict(row._mapping) for row in rows]


def _load_profile_data(db: Session, user: User) -> dict[str, Any]:
    record = db.scalar(
        select(StudentProfileRecord)
        .where(StudentProfileRecord.user_id == user.id)
        .order_by(desc(StudentProfileRecord.updated_at))
    )
    return dict(record.profile_data or {}) if record else {}


@lru_cache(maxsize=1)
def _load_taxonomy() -> dict[str, Any]:
    topics_payload = json.loads((DATA_DIR / "topics.json").read_text(encoding="utf-8"))
    dependencies_payload = json.loads((DATA_DIR / "dependencies.json").read_text(encoding="utf-8"))
    clusters_payload = json.loads((DATA_DIR / "clusters.json").read_text(encoding="utf-8"))
    topics = topics_payload.get("topics", [])
    clusters = clusters_payload.get("clusters", [])
    return {
        "topics": topics,
        "topics_by_id": {topic["id"]: topic for topic in topics},
        "dependencies": dependencies_payload.get("dependencies", []),
        "clusters": clusters,
        "clusters_by_key": {
            _cluster_key(cluster.get("subject"), cluster.get("domain"), cluster.get("ageRangeStart")): cluster
            for cluster in clusters
        },
    }


def _add_project_nodes(nodes: dict[str, KnowledgeLinkNode], projects: list[LearningProject]) -> list[KnowledgeLinkNode]:
    result: list[KnowledgeLinkNode] = []
    for project in projects:
        label = project.title or project.research_direction or "Learning project"
        node = KnowledgeLinkNode(
            id=f"project:{project.id}",
            label=label,
            layer="project",
            category=project.goal_type or project.subject or "learning_project",
            description=_compact_text(
                project.learning_goal
                or project.foundation_summary
                or project.expected_output
                or project.research_direction
            ),
            weight=max(4, len(_project_terms(project)) + 2),
            meta={
                "project_id": project.id,
                "direction_id": project.direction_id,
                "status": project.status,
                "subject": project.subject,
                "goal_type": project.goal_type,
                "related_knowledge_points": list(project.related_knowledge_points or []),
                "related_documents": list(project.related_documents or []),
                "research_training": project.research_training or {},
            },
        )
        nodes[node.id] = node
        result.append(node)
    return result


def _add_knowledge_base_nodes(nodes: dict[str, KnowledgeLinkNode], rows: list[dict[str, Any]]) -> list[KnowledgeLinkNode]:
    result: list[KnowledgeLinkNode] = []
    for row in rows:
        point_name = str(row["name"])
        node = KnowledgeLinkNode(
            id=f"kb:{row['point_id']}",
            label=point_name,
            layer="knowledge_base",
            category=str(row.get("chapter") or row.get("course_title") or "knowledge_base"),
            description=str(row.get("description") or ""),
            weight=max(1, int(row.get("chunk_count") or 1)),
            meta={
                "point_id": row.get("point_id"),
                "chapter_id": row.get("chapter_id"),
                "chapter": row.get("chapter", ""),
                "course_title": row.get("course_title", ""),
                "chunk_count": int(row.get("chunk_count") or 0),
                "document_count": int(row.get("document_count") or 0),
                "tags": list(row.get("tags") or []),
                "prerequisites": list(row.get("prerequisites") or []),
                "difficulty": row.get("difficulty", "medium"),
            },
        )
        nodes[node.id] = node
        result.append(node)
    return result


def _add_taxonomy_nodes(nodes: dict[str, KnowledgeLinkNode], taxonomy: dict[str, Any], ids: list[str]) -> list[KnowledgeLinkNode]:
    result: list[KnowledgeLinkNode] = []
    for topic_id in ids:
        topic = taxonomy["topics_by_id"].get(topic_id)
        if not topic:
            continue
        node = KnowledgeLinkNode(
            id=f"tax:{topic_id}",
            label=topic["name"],
            layer="taxonomy",
            category=f"{topic.get('subject', '')} / {topic.get('domain', '')}".strip(" /"),
            description=str(topic.get("description") or ""),
            weight=max(1, int(round(float(topic.get("centrality") or 0) * 100))),
            meta={
                "topic_id": topic_id,
                "subject": topic.get("subject", ""),
                "domain": topic.get("domain", ""),
                "type": topic.get("type", ""),
                "age_range": [topic.get("ageRangeStart"), topic.get("ageRangeEnd")],
                "centrality": topic.get("centrality"),
                "assessment_prompt": _clean_assessment_prompt(topic.get("assessmentPrompt")),
                "cluster_summary": _cluster_summary(taxonomy, topic),
                "evidence": list(topic.get("evidence", [])[:3]),
                "standards": list(topic.get("standards", [])[:4]),
            },
        )
        nodes[node.id] = node
        result.append(node)
    return result


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
    return _unique_terms(values, limit=24)


def _collect_focus_terms(
    projects: list[LearningProject],
    rows: list[dict[str, Any]],
    query: str,
    profile_data: dict[str, Any],
) -> list[str]:
    values: list[str] = [query]
    for project in projects:
        values.extend(_project_terms(project))
        values.extend(
            [
                *list(project.current_weak_points or []),
                *list(project.personalization_strategy or []),
                *list(project.today_recommendations or []),
                project.next_step,
            ]
        )
    for row in rows:
        values.extend(
            [
                str(row.get("name") or ""),
                str(row.get("chapter") or ""),
                str(row.get("description") or ""),
                str(row.get("course_title") or ""),
                " ".join(map(str, row.get("tags") or [])),
            ]
        )
    values.extend(_profile_terms(profile_data))
    return _unique_terms(values, limit=60)


def _select_taxonomy_topics(taxonomy: dict[str, Any], terms: list[str], *, limit: int) -> list[str]:
    scored: list[tuple[float, str]] = []
    unique_terms = _unique_terms(terms, limit=60)
    for topic in taxonomy["topics"]:
        haystack = " ".join(
            [
                str(topic.get("name", "")),
                str(topic.get("description", "")),
                str(topic.get("subject", "")),
                str(topic.get("domain", "")),
                " ".join(topic.get("evidence", [])[:3]),
            ]
        ).lower()
        score = float(topic.get("centrality") or 0)
        for term in unique_terms:
            normalized = term.lower()
            if not normalized:
                continue
            if normalized in haystack:
                score += 4.0
            score += len(set(_tokens(normalized)) & set(_tokens(haystack))) * 0.9
        if score > 0:
            scored.append((score, topic["id"]))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [topic_id for _score, topic_id in scored[:limit]]


def _link_project_edges(
    project_nodes: list[KnowledgeLinkNode],
    kb_nodes: list[KnowledgeLinkNode],
    tax_nodes: list[KnowledgeLinkNode],
) -> list[KnowledgeLinkEdge]:
    edges: list[KnowledgeLinkEdge] = []
    for project in project_nodes:
        project_terms = _token_set(
            project.label,
            project.description,
            project.category,
            " ".join(map(str, project.meta.get("related_knowledge_points", []))),
            " ".join(map(str, project.meta.get("related_documents", []))),
        )
        for kb_node in kb_nodes:
            if _node_related(
                project_terms,
                _token_set(
                    kb_node.label,
                    kb_node.description,
                    kb_node.category,
                    " ".join(map(str, kb_node.meta.get("tags", []))),
                    " ".join(map(str, kb_node.meta.get("prerequisites", []))),
                ),
            ):
                edges.append(
                    KnowledgeLinkEdge(
                        source=project.id,
                        target=kb_node.id,
                        relation="uses",
                        reason="project knowledge aligns with database knowledge",
                    )
                )
        for tax_node in tax_nodes:
            if _node_related(project_terms, _token_set(tax_node.label, tax_node.description, tax_node.category)):
                edges.append(
                    KnowledgeLinkEdge(
                        source=project.id,
                        target=tax_node.id,
                        relation="aligns",
                        reason="project goals align with taxonomy structure",
                    )
                )
    for kb_node in kb_nodes:
        kb_terms = _token_set(
            kb_node.label,
            kb_node.description,
            kb_node.category,
            " ".join(map(str, kb_node.meta.get("tags", []))),
            " ".join(map(str, kb_node.meta.get("prerequisites", []))),
        )
        for tax_node in tax_nodes:
            if _node_related(kb_terms, _token_set(tax_node.label, tax_node.description, tax_node.category)):
                edges.append(
                    KnowledgeLinkEdge(
                        source=kb_node.id,
                        target=tax_node.id,
                        relation="maps_to",
                        reason="database knowledge maps into taxonomy hierarchy",
                    )
                )
    return edges


def _link_dependency_edges(taxonomy: dict[str, Any], tax_nodes: list[KnowledgeLinkNode]) -> list[KnowledgeLinkEdge]:
    allowed = {node.meta.get("topic_id") for node in tax_nodes}
    edges: list[KnowledgeLinkEdge] = []
    for dependency in taxonomy["dependencies"]:
        topic_id = dependency.get("topicId")
        prereq_id = dependency.get("prerequisiteId")
        if topic_id in allowed and prereq_id in allowed:
            edges.append(
                KnowledgeLinkEdge(
                    source=f"tax:{prereq_id}",
                    target=f"tax:{topic_id}",
                    relation="prerequisite",
                    strength=str(dependency.get("strength") or ""),
                    reason=str(dependency.get("reason") or ""),
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
                        reason="knowledge base prerequisite",
                    )
                )
    return edges


def _build_path_suggestions(
    projects: list[LearningProject],
    rows: list[dict[str, Any]],
    taxonomy: dict[str, Any],
    taxonomy_ids: list[str],
    profile_data: dict[str, Any],
) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    for project in projects:
        project_terms = _unique_terms(
            [
                *_project_terms(project),
                *list(project.current_weak_points or []),
                *list(project.personalization_strategy or []),
                *list(project.today_recommendations or []),
                *_profile_terms(profile_data),
            ],
            limit=90,
        )
        steps: list[dict[str, Any]] = []
        ranked_topic_ids = _sort_topics_for_learning_path(taxonomy, taxonomy_ids)
        for topic_id in ranked_topic_ids:
            topic = taxonomy["topics_by_id"].get(topic_id)
            if not topic:
                continue
            if _node_related(
                project_terms,
                _token_set(topic.get("name", ""), topic.get("description", ""), topic.get("subject", ""), topic.get("domain", "")),
            ):
                steps.append(
                    {
                        "id": f"tax:{topic_id}",
                        "label": topic["name"],
                        "layer": "taxonomy",
                        "reason": _path_reason(topic, project, profile_data),
                        "phase": _phase_for_topic(topic),
                        "estimated_minutes": _estimated_minutes(topic, project, profile_data),
                        "evidence": list(topic.get("evidence", [])[:2]),
                    }
                )
        for row in rows:
            if _node_related(
                project_terms,
                _token_set(str(row.get("name") or ""), str(row.get("description") or ""), str(row.get("chapter") or "")),
            ):
                steps.append(
                    {
                        "id": f"kb:{row.get('point_id')}",
                        "label": str(row.get("name") or ""),
                        "layer": "knowledge_base",
                        "reason": _kb_path_reason(row, project, profile_data),
                        "phase": _phase_for_difficulty(str(row.get("difficulty") or "")),
                        "estimated_minutes": _estimated_minutes(row, project, profile_data),
                        "evidence": [str(row.get("description") or "")[:120]],
                    }
                )
        deduped_steps = _dedupe_path_steps(steps)[:18]
        suggestions.append(
            {
                "project_id": project.id,
                "project_title": project.title,
                "strategy": _personalized_strategy(project, profile_data),
                "dynamic_signals": _dynamic_signals(project, profile_data),
                "steps": _number_path_steps(deduped_steps),
            }
        )

    if not suggestions:
        generic_steps = [
            {
                "id": f"tax:{topic_id}",
                "label": taxonomy["topics_by_id"][topic_id]["name"],
                "layer": "taxonomy",
                "reason": "按 os-taxonomy 的前置依赖和中心度排序，先补基础节点。",
                "phase": _phase_for_topic(taxonomy["topics_by_id"][topic_id]),
                "estimated_minutes": 35,
                "evidence": list(taxonomy["topics_by_id"][topic_id].get("evidence", [])[:2]),
            }
            for topic_id in _sort_topics_for_learning_path(taxonomy, taxonomy_ids)[:12]
            if topic_id in taxonomy["topics_by_id"]
        ]
        if generic_steps:
            suggestions.append(
                {
                    "project_id": None,
                    "project_title": "全部知识库",
                    "strategy": "先完成基础 taxonomy 节点，再进入资料库中证据更充分的知识点。",
                    "dynamic_signals": _dynamic_signals(None, profile_data),
                    "steps": _number_path_steps(generic_steps),
                }
            )
    return suggestions


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
    cjk_tokens = [char for char in text if "\u4e00" <= char <= "\u9fff"]
    return ascii_tokens + cjk_tokens


def _node_related(left_tokens: list[str], right_tokens: list[str]) -> bool:
    return bool(set(left_tokens) & set(right_tokens))


def _tokens(text: str) -> list[str]:
    return [part for part in text.replace("_", " ").replace("-", " ").split() if part]


def _compact_text(value: str, *, limit: int = 84) -> str:
    return " ".join(str(value or "").split())[:limit]


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


def _sort_topics_for_learning_path(taxonomy: dict[str, Any], topic_ids: list[str]) -> list[str]:
    incoming_count: dict[str, int] = {}
    for dependency in taxonomy["dependencies"]:
        incoming_count[dependency.get("topicId", "")] = incoming_count.get(dependency.get("topicId", ""), 0) + 1

    def key(topic_id: str) -> tuple[int, int, float, str]:
        topic = taxonomy["topics_by_id"].get(topic_id, {})
        start = topic.get("ageRangeStart")
        centrality = float(topic.get("centrality") or 0)
        return (
            int(start if start is not None else 99),
            incoming_count.get(topic_id, 0),
            -centrality,
            str(topic.get("name") or ""),
        )

    return sorted(topic_ids, key=key)


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
    taxonomy: dict[str, Any],
    nodes: dict[str, KnowledgeLinkNode],
    edges: list[KnowledgeLinkEdge],
    suggestions: list[dict[str, Any]],
    profile_data: dict[str, Any],
) -> dict[str, Any]:
    selected_taxonomy = [node for node in nodes.values() if node.layer == "taxonomy"]
    subjects: dict[str, int] = {}
    age_ranges: list[int] = []
    for node in selected_taxonomy:
        subject = str(node.meta.get("subject") or "Unspecified")
        subjects[subject] = subjects.get(subject, 0) + 1
        start = node.meta.get("age_range", [None])[0]
        if isinstance(start, int):
            age_ranges.append(start)
    return {
        "taxonomy_version": "v1",
        "taxonomy_total_topics": len(taxonomy["topics"]),
        "taxonomy_total_dependencies": len(taxonomy["dependencies"]),
        "taxonomy_selected_topics": len(selected_taxonomy),
        "taxonomy_subjects": subjects,
        "age_range": [min(age_ranges), max(age_ranges)] if age_ranges else [],
        "cluster_count": len(taxonomy["clusters"]),
        "edge_count": len(edges),
        "path_count": len(suggestions),
        "profile_signals": _dynamic_signals(None, profile_data),
    }


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


def _path_reason(topic: dict[str, Any], project: LearningProject, profile_data: dict[str, Any]) -> str:
    parts = ["前置依赖图显示它应先掌握"]
    weak_terms = _token_set(
        " ".join(map(str, project.current_weak_points or [])),
        " ".join(map(str, profile_data.get("weak_points") or [])),
    )
    topic_terms = _token_set(topic.get("name", ""), topic.get("description", ""), topic.get("domain", ""))
    if set(weak_terms) & set(topic_terms):
        parts.append("同时命中学生薄弱点")
    if topic.get("centrality"):
        parts.append(f"中心度 {float(topic.get('centrality') or 0):.2f}")
    return "，".join(parts) + "。"


def _kb_path_reason(row: dict[str, Any], project: LearningProject, profile_data: dict[str, Any]) -> str:
    parts = ["资料库已有可回看证据"]
    chunk_count = int(row.get("chunk_count") or 0)
    if chunk_count:
        parts.append(f"{chunk_count} 个片段")
    weak_terms = _token_set(
        " ".join(map(str, project.current_weak_points or [])),
        " ".join(map(str, profile_data.get("weak_points") or [])),
    )
    row_terms = _token_set(str(row.get("name") or ""), str(row.get("description") or ""), str(row.get("chapter") or ""))
    if set(weak_terms) & set(row_terms):
        parts.append("适合优先补弱")
    return "，".join(parts) + "。"


def _phase_for_topic(topic: dict[str, Any]) -> str:
    start = topic.get("ageRangeStart")
    if isinstance(start, int) and start <= 6:
        return "基础建构"
    if isinstance(start, int) and start <= 8:
        return "概念连接"
    return "迁移应用"


def _phase_for_difficulty(difficulty: str) -> str:
    normalized = difficulty.lower()
    if normalized in {"easy", "基础", "low"}:
        return "基础建构"
    if normalized in {"hard", "困难", "high"}:
        return "迁移应用"
    return "概念连接"


def _estimated_minutes(item: Any, project: Optional[LearningProject], profile_data: dict[str, Any]) -> int:
    base = 35
    if isinstance(item, dict):
        item_type = str(item.get("type") or item.get("difficulty") or "").lower()
        if item_type in {"procedural", "hard", "困难"}:
            base += 15
        if item_type in {"representational", "meta"}:
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
        return "按 taxonomy 前置关系、资料库证据和项目知识点相关性动态排序。"
    return "结合 " + "、".join(signals[:4]) + "，优先安排基础依赖和已上传资料可支撑的节点。"


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


def _cluster_key(subject: Any, domain: Any, age_start: Any) -> str:
    return f"{subject or ''}::{domain or ''}::{age_start or ''}".lower()


def _cluster_summary(taxonomy: dict[str, Any], topic: dict[str, Any]) -> str:
    cluster = taxonomy["clusters_by_key"].get(
        _cluster_key(topic.get("subject"), topic.get("domain"), topic.get("ageRangeStart"))
    )
    return str((cluster or {}).get("summary") or "")


def _clean_assessment_prompt(value: Any) -> str:
    return str(value or "").replace("{{name}}", "学生")


def _normalize_label(value: str) -> str:
    return " ".join(value.lower().replace("_", " ").replace("-", " ").split())
