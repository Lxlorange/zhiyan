from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas import (
    ClassroomPptGenerateRequest,
    ClassroomPracticeSubmitRequest,
    ClassroomQuizSubmitRequest,
    ClassroomReflectionSubmitRequest,
    ClassroomSessionRead,
    ClassroomSlidesCompleteRequest,
)
from app.services.classroom_service import (
    complete_slides,
    generate_classroom_ppt,
    get_or_create_classroom_session,
    submit_practice,
    submit_quiz,
    submit_reflection,
)
from app.services.llm_client import LLMConfigurationError, LLMResponseError

router = APIRouter(tags=["classroom"])


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, LLMConfigurationError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, LLMResponseError):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router.post("/syllabus-items/{item_id}/classroom", response_model=ClassroomSessionRead)
def classroom_session_create_or_get(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassroomSessionRead:
    try:
        return ClassroomSessionRead.model_validate(get_or_create_classroom_session(db, user, item_id))
    except (KeyError, ValueError, LLMConfigurationError, LLMResponseError) as exc:
        raise _handle_error(exc) from exc


@router.post("/classroom-sessions/{session_id}/ppt", response_model=ClassroomSessionRead)
def classroom_ppt_generate(
    session_id: int,
    request: ClassroomPptGenerateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassroomSessionRead:
    try:
        return ClassroomSessionRead.model_validate(generate_classroom_ppt(db, user, session_id, request.instruction))
    except (KeyError, ValueError, LLMConfigurationError, LLMResponseError) as exc:
        raise _handle_error(exc) from exc


@router.get("/classroom-resources/{resource_id}/download")
def classroom_resource_download(
    resource_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    from app.models.learning import ClassroomResource

    resource = db.get(ClassroomResource, resource_id)
    if resource is None or resource.user_id != user.id:
        raise HTTPException(status_code=404, detail="classroom resource not found")
    path = Path(resource.file_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="classroom resource file not found")
    return FileResponse(path, filename=f"{resource.title}.pptx")


@router.post("/classroom-sessions/{session_id}/quiz", response_model=ClassroomSessionRead)
def classroom_quiz_submit(
    session_id: int,
    request: ClassroomQuizSubmitRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassroomSessionRead:
    try:
        return ClassroomSessionRead.model_validate(submit_quiz(db, user, session_id, request))
    except (KeyError, ValueError, LLMConfigurationError, LLMResponseError) as exc:
        raise _handle_error(exc) from exc


@router.post("/classroom-sessions/{session_id}/slides/complete", response_model=ClassroomSessionRead)
def classroom_slides_complete(
    session_id: int,
    request: ClassroomSlidesCompleteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassroomSessionRead:
    try:
        return ClassroomSessionRead.model_validate(complete_slides(db, user, session_id, request))
    except (KeyError, ValueError, LLMConfigurationError, LLMResponseError) as exc:
        raise _handle_error(exc) from exc


@router.post("/classroom-sessions/{session_id}/practice", response_model=ClassroomSessionRead)
def classroom_practice_submit(
    session_id: int,
    request: ClassroomPracticeSubmitRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassroomSessionRead:
    try:
        return ClassroomSessionRead.model_validate(submit_practice(db, user, session_id, request))
    except (KeyError, ValueError, LLMConfigurationError, LLMResponseError) as exc:
        raise _handle_error(exc) from exc


@router.post("/classroom-sessions/{session_id}/reflection", response_model=ClassroomSessionRead)
def classroom_reflection_submit(
    session_id: int,
    request: ClassroomReflectionSubmitRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ClassroomSessionRead:
    try:
        return ClassroomSessionRead.model_validate(submit_reflection(db, user, session_id, request))
    except (KeyError, ValueError, LLMConfigurationError, LLMResponseError) as exc:
        raise _handle_error(exc) from exc
