from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.schemas import CourseMapResponse, KnowledgePointRead, KnowledgeSearchHit, KnowledgeSearchRequest
from app.models.user import User
from app.services.knowledge_ingestion_service import (
    KnowledgeImportJobRead,
    KnowledgeIngestionError,
    get_import_job,
    import_knowledge_upload,
    list_import_jobs,
    rebuild_missing_embeddings,
    search_knowledge_enhanced,
)
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


@router.post("/knowledge/search/enhanced")
def knowledge_search_enhanced(request: KnowledgeSearchRequest, db: Session = Depends(get_db)) -> list[dict]:
    return search_knowledge_enhanced(db, request.query, request.limit)


@router.post("/knowledge/import", response_model=KnowledgeImportJobRead)
async def knowledge_import(
    file: UploadFile = File(...),
    course_code: str = Form(default="IMPORTED-COURSEWARE"),
    course_title: str = Form(default="导入课程课件知识库"),
    use_ocr: bool = Form(default=False),
    rebuild_course: bool = Form(default=False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> KnowledgeImportJobRead:
    try:
        return await import_knowledge_upload(
            db,
            user,
            file,
            course_code=course_code,
            course_title=course_title,
            use_ocr=use_ocr,
            rebuild_course=rebuild_course,
        )
    except KnowledgeIngestionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/knowledge/import-jobs", response_model=list[KnowledgeImportJobRead])
def knowledge_import_jobs(
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[KnowledgeImportJobRead]:
    return list_import_jobs(db, user, limit)


@router.get("/knowledge/import-jobs/{job_id}", response_model=KnowledgeImportJobRead)
def knowledge_import_job(
    job_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> KnowledgeImportJobRead:
    try:
        return get_import_job(db, user, job_id)
    except KnowledgeIngestionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/knowledge/embeddings/rebuild")
def knowledge_embeddings_rebuild(
    limit: int = 200,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return {"rebuilt": rebuild_missing_embeddings(db, limit)}
