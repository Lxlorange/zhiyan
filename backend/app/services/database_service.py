from __future__ import annotations

from collections import Counter
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.learning import (
    ClassroomResource,
    ClassroomSubmission,
    DocumentChunk,
    KnowledgeDocument,
    KnowledgePoint,
    LearningProject,
    LiteraturePaper,
)
from app.models.user import User
from app.schemas import (
    DatabaseAskRequest,
    DatabaseAskResponse,
    DatabaseCitation,
    DatabaseGraphEdge,
    DatabaseGraphNode,
    DatabaseGraphResponse,
    DatabaseNodeDetailResponse,
)
from app.services.knowledge_ingestion_service import KnowledgeIngestionError, search_knowledge_enhanced
from app.services.knowledge_service import search_knowledge
from app.services.llm_client import LLMConfigurationError, LLMResponseError, qwen_chat_json


class _RagAnswerLLM(BaseModel):
    answer: str
    related_points: list[str] = Field(default_factory=list)
    follow_up_questions: list[str] = Field(default_factory=list)
    confidence: str = "medium"


def ask_database(db: Session, user: User, request: DatabaseAskRequest) -> DatabaseAskResponse:
    query = _scoped_query(db, user, request)
    hits = _retrieve_hits(db, query, request.limit)
    citations = [_citation_from_hit(hit) for hit in hits]
    citations.extend(_project_sources(db, user, request.project_id, request.question))
    citations = _dedupe_citations(citations)[: request.limit]

    if not citations:
        return DatabaseAskResponse(
            answer="当前数据库没有检索到可引用的资料。请先上传课程资料、论文、笔记，或进入学习项目生成课堂资源后再提问。",
            citations=[],
            related_points=[],
            follow_up_questions=["是否先上传一份课程资料？", "是否切换到全部项目范围重新检索？"],
            confidence="low",
            used_llm=False,
        )

    result = _generate_llm_answer(user, request.question, citations)
    return DatabaseAskResponse(
        answer=result.answer,
        citations=citations,
        related_points=result.related_points or _related_points(citations),
        follow_up_questions=result.follow_up_questions,
        confidence=result.confidence or "medium",
        used_llm=True,
    )


def build_database_graph(db: Session, user: User, project_id: Optional[int] = None, scope: str = "all") -> DatabaseGraphResponse:
    rows = db.execute(
        select(KnowledgePoint, DocumentChunk)
        .join(DocumentChunk, DocumentChunk.knowledge_point_id == KnowledgePoint.id)
        .join(KnowledgeDocument, KnowledgeDocument.id == DocumentChunk.document_id)
    ).all()
    point_counts: Counter[str] = Counter()
    descriptions: dict[str, str] = {}
    for point, _chunk in rows:
        point_counts[point.name] += 1
        descriptions[point.name] = point.description

    if project_id:
        project = _get_user_project(db, user, project_id)
        allowed = {str(point) for point in project.related_knowledge_points or []}
        if scope == "project":
            point_counts = Counter({name: count for name, count in point_counts.items() if name in allowed})
        for point in allowed:
            point_counts[point] += 2
            descriptions.setdefault(point, f"来自学习项目：{project.title}")

    nodes = [
        DatabaseGraphNode(
            id=f"kp:{name}",
            name=name,
            category="knowledge_point",
            description=descriptions.get(name, ""),
            count=count,
        )
        for name, count in point_counts.most_common(36)
    ]

    edges: list[DatabaseGraphEdge] = []
    for index, node in enumerate(nodes):
        if index + 1 < len(nodes):
            edges.append(DatabaseGraphEdge(source=node.id, target=nodes[index + 1].id, relation="co-occur"))
        for other in nodes[index + 1 : index + 4]:
            if _looks_related(node.name, other.name):
                edges.append(DatabaseGraphEdge(source=node.id, target=other.id, relation="related"))
    return DatabaseGraphResponse(nodes=nodes, edges=edges)


def get_database_node_detail(db: Session, user: User, name: str, project_id: Optional[int] = None) -> DatabaseNodeDetailResponse:
    query = _scoped_query(db, user, DatabaseAskRequest(question=name, project_id=project_id, knowledge_points=[name], limit=8))
    hits = _retrieve_hits(db, query, 8)
    citations = [_citation_from_hit(hit) for hit in hits]
    point = db.scalar(select(KnowledgePoint).where(KnowledgePoint.name == name))
    return DatabaseNodeDetailResponse(
        name=name,
        description=point.description if point else "",
        citations=citations,
        related_points=_related_points(citations),
        suggested_questions=[],
    )


def get_document_review(db: Session, user: User, document_id: int) -> dict[str, Any]:
    document = db.get(KnowledgeDocument, document_id)
    if document is None:
        raise ValueError("document not found")
    chunks = db.scalars(
        select(DocumentChunk).where(DocumentChunk.document_id == document.id).order_by(DocumentChunk.chunk_index)
    ).all()
    return {
        "id": document.id,
        "title": document.title,
        "document_type": document.doc_type,
        "source_uri": document.source_uri,
        "summary": document.summary,
        "chunks": [
            {
                "id": chunk.id,
                "index": chunk.chunk_index,
                "content": chunk.content,
                "page_no": chunk.page_no,
                "slide_no": chunk.slide_no,
                "section_title": chunk.section_title,
                "keywords": chunk.keywords,
            }
            for chunk in chunks
        ],
    }


def get_chunk_review(db: Session, user: User, chunk_id: int) -> dict[str, Any]:
    chunk = db.get(DocumentChunk, chunk_id)
    if chunk is None:
        raise ValueError("chunk not found")
    document = db.get(KnowledgeDocument, chunk.document_id)
    point = db.get(KnowledgePoint, chunk.knowledge_point_id) if chunk.knowledge_point_id else None
    return {
        "id": chunk.id,
        "document_id": chunk.document_id,
        "document_title": document.title if document else "知识库片段",
        "document_type": document.doc_type if document else "",
        "source_uri": document.source_uri if document else "",
        "knowledge_point": point.name if point else "",
        "content": chunk.content,
        "page_no": chunk.page_no,
        "slide_no": chunk.slide_no,
        "section_title": chunk.section_title,
        "keywords": chunk.keywords,
    }


def _scoped_query(db: Session, user: User, request: DatabaseAskRequest) -> str:
    parts = [request.question, " ".join(request.knowledge_points)]
    if request.project_id:
        project = _get_user_project(db, user, request.project_id)
        parts.extend(
            [
                project.title,
                project.research_direction,
                project.learning_goal,
                " ".join(project.related_knowledge_points or []),
                " ".join(project.related_documents or []),
            ]
        )
    return "\n".join(part for part in parts if part)


def _get_user_project(db: Session, user: User, project_id: int) -> LearningProject:
    project = db.get(LearningProject, project_id)
    if project is None or project.user_id != user.id:
        raise ValueError("learning project not found")
    return project


def _retrieve_hits(db: Session, query: str, limit: int) -> list[dict[str, Any]]:
    return search_knowledge_enhanced(db, query, limit=limit)


def _project_sources(db: Session, user: User, project_id: Optional[int], query: str) -> list[DatabaseCitation]:
    if not project_id:
        return []
    resources = db.scalars(
        select(ClassroomResource)
        .where(ClassroomResource.user_id == user.id, ClassroomResource.project_id == project_id)
        .order_by(ClassroomResource.created_at.desc())
        .limit(6)
    ).all()
    submissions = db.scalars(
        select(ClassroomSubmission)
        .where(ClassroomSubmission.user_id == user.id, ClassroomSubmission.project_id == project_id)
        .order_by(ClassroomSubmission.created_at.desc())
        .limit(4)
    ).all()
    papers = db.scalars(
        select(LiteraturePaper)
        .where(LiteraturePaper.user_id == user.id, LiteraturePaper.project_id == project_id)
        .order_by(LiteraturePaper.updated_at.desc())
        .limit(4)
    ).all()

    citations: list[DatabaseCitation] = []
    for resource in resources:
        content = _compact(resource.content_data) or resource.source or resource.title
        citations.append(
            DatabaseCitation(
                id=f"classroom-resource:{resource.id}",
                source_type="classroom_resource",
                title=resource.title,
                document_type=resource.resource_type,
                content=content[:1200],
                source_uri=resource.file_path,
                review_url=f"/api/classroom-resources/{resource.id}/view",
            )
        )
    for submission in submissions:
        citations.append(
            DatabaseCitation(
                id=f"classroom-submission:{submission.id}",
                source_type="classroom_submission",
                title=f"{submission.submission_type} 反馈",
                document_type="submission",
                content=(submission.feedback or _compact(submission.content))[:1200],
                source_uri=f"project:{submission.project_id}",
            )
        )
    for paper in papers:
        citations.append(
            DatabaseCitation(
                id=f"literature:{paper.id}",
                source_type="literature",
                title=paper.title,
                document_type="literature",
                content=(paper.abstract or paper.notes or paper.citation_text)[:1200],
                source_uri=paper.source_uri,
            )
        )
    return citations


def _citation_from_hit(hit: dict[str, Any]) -> DatabaseCitation:
    chunk_id = hit.get("chunk_id")
    return DatabaseCitation(
        id=f"chunk:{chunk_id}" if chunk_id else f"hit:{hit.get('document_title', '')}:{hit.get('section_title', '')}",
        source_type="knowledge_chunk",
        title=str(hit.get("document_title") or "知识库片段"),
        document_type=str(hit.get("document_type") or ""),
        knowledge_point=str(hit.get("knowledge_point") or ""),
        content=str(hit.get("content") or "")[:1600],
        source_uri=str(hit.get("source_uri") or ""),
        page_no=hit.get("page_no"),
        slide_no=hit.get("slide_no"),
        section_title=str(hit.get("section_title") or ""),
        score=hit.get("distance"),
        review_url=f"/api/database/chunks/{chunk_id}/review" if chunk_id else "",
    )


def _generate_llm_answer(user: User, question: str, citations: list[DatabaseCitation]) -> _RagAnswerLLM:
    context = "\n\n".join(
        f"[{index}] {item.title} / {item.knowledge_point} / {item.section_title}\nsource={item.source_uri}\n{item.content}"
        for index, item in enumerate(citations, start=1)
    )
    prompt = f"""
请基于给定资料回答学生问题。只输出 JSON，不要 Markdown。

学生问题：{question}

可引用资料：
{context}

要求：
1. answer 必须直接回答问题，并在关键结论后用 [1]、[2] 这样的编号标出依据。
2. 只能基于可引用资料回答；资料不足时明确说明缺口。
3. related_points 返回 2-6 个相关知识点。
4. follow_up_questions 返回 3 个适合继续复习的问题。
5. confidence 只能是 high、medium、low。
"""
    return qwen_chat_json(
        "你是高校个性化学习平台的 RAG 问答 Agent，必须保证回答可回溯到资料来源。",
        prompt,
        _RagAnswerLLM,
        user=user,
    )


def _related_points(citations: list[DatabaseCitation]) -> list[str]:
    values = [item.knowledge_point for item in citations if item.knowledge_point]
    return [name for name, _count in Counter(values).most_common(6)]


def _dedupe_citations(citations: list[DatabaseCitation]) -> list[DatabaseCitation]:
    seen: set[str] = set()
    result: list[DatabaseCitation] = []
    for item in citations:
        key = item.id or f"{item.title}:{item.content[:24]}"
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _compact(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        parts = []
        for key, item in value.items():
            if isinstance(item, (str, int, float)):
                parts.append(f"{key}: {item}")
            elif isinstance(item, list):
                parts.append(f"{key}: " + "；".join(str(x) for x in item[:6]))
        return "\n".join(parts)
    if isinstance(value, list):
        return "；".join(str(item) for item in value[:12])
    return str(value)


def _looks_related(left: str, right: str) -> bool:
    return bool(set(left) & set(right)) or left in right or right in left
