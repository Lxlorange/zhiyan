from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.learning import Course, CourseChapter, DocumentChunk, KnowledgeDocument, KnowledgePoint
from app.schemas import CourseMapResponse, KnowledgePointRead, KnowledgeSearchHit


def get_course_map_from_db(db: Session) -> CourseMapResponse:
    courses = list(db.scalars(select(Course).order_by(Course.id)).all())
    chapters = list(
        db.scalars(
            select(CourseChapter).order_by(CourseChapter.course_id, CourseChapter.order_index, CourseChapter.id)
        ).all()
    )
    points = list(
        db.scalars(
            select(KnowledgePoint).order_by(KnowledgePoint.chapter_id, KnowledgePoint.id)
        ).all()
    )

    course_title = " / ".join(course.title for course in courses[:3]) if courses else "未导入课程资料"
    if len(courses) > 3:
        course_title += f" 等 {len(courses)} 门课程"

    return CourseMapResponse(
        course=course_title,
        chapters=[chapter.title for chapter in chapters],
        knowledge_points=[point.name for point in points],
    )


def list_knowledge_points(db: Session) -> list[KnowledgePointRead]:
    rows = db.execute(
        select(KnowledgePoint, CourseChapter)
        .join(CourseChapter, KnowledgePoint.chapter_id == CourseChapter.id)
        .order_by(CourseChapter.course_id, CourseChapter.order_index, KnowledgePoint.id)
    ).all()
    return [
        KnowledgePointRead(
            id=point.id,
            name=point.name,
            description=point.description,
            chapter=chapter.title,
            prerequisites=list(point.prerequisites or []),
            tags=list(point.tags or []),
            difficulty=point.difficulty,
        )
        for point, chapter in rows
    ]


def search_knowledge(db: Session, query: str, limit: int = 6) -> list[KnowledgeSearchHit]:
    terms = _split_terms(query)
    if not terms:
        return []

    filters = []
    for term in terms:
        pattern = f"%{term}%"
        filters.extend(
            [
                DocumentChunk.content.ilike(pattern),
                DocumentChunk.section_title.ilike(pattern),
                KnowledgePoint.name.ilike(pattern),
                KnowledgePoint.description.ilike(pattern),
                KnowledgeDocument.title.ilike(pattern),
                KnowledgeDocument.summary.ilike(pattern),
                KnowledgeDocument.source_uri.ilike(pattern),
            ]
        )

    rows = db.execute(
        select(DocumentChunk, KnowledgeDocument, KnowledgePoint)
        .join(KnowledgeDocument, DocumentChunk.document_id == KnowledgeDocument.id)
        .join(KnowledgePoint, DocumentChunk.knowledge_point_id == KnowledgePoint.id, isouter=True)
        .where(or_(*filters))
        .order_by(DocumentChunk.id.desc())
        .limit(limit)
    ).all()

    return [
        KnowledgeSearchHit(
            chunk_id=chunk.id,
            document_title=document.title,
            document_type=document.doc_type,
            knowledge_point=point.name if point else "",
            content=chunk.content,
            source_uri=document.source_uri,
            keywords=list(chunk.keywords or []),
            page_no=chunk.page_no,
            slide_no=chunk.slide_no,
            section_title=chunk.section_title,
            distance=None,
            keyword_hit=1,
        )
        for chunk, document, point in rows
    ]


def _split_terms(query: str) -> list[str]:
    normalized = query.replace("，", " ").replace("。", " ").replace("；", " ").replace("/", " ").replace("\n", " ")
    return [term.strip() for term in normalized.split() if term.strip()]
