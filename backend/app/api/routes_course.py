from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas import CourseMapResponse, KnowledgePointRead, KnowledgeSearchHit, KnowledgeSearchRequest
from app.services.knowledge_service import get_course_map_from_db, list_knowledge_points, search_knowledge

router = APIRouter(prefix="/course", tags=["course"])


@router.get("/map", response_model=CourseMapResponse)
def course_map(db: Session = Depends(get_db)) -> CourseMapResponse:
    return get_course_map_from_db(db)


@router.get("/knowledge-points", response_model=list[KnowledgePointRead])
def knowledge_points(db: Session = Depends(get_db)) -> list[KnowledgePointRead]:
    return list_knowledge_points(db)


@router.post("/knowledge/search", response_model=list[KnowledgeSearchHit])
def knowledge_search(request: KnowledgeSearchRequest, db: Session = Depends(get_db)) -> list[KnowledgeSearchHit]:
    return search_knowledge(db, request.query, request.limit)
