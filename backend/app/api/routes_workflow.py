from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas import (
    AssessmentRequest,
    AssessmentResponse,
    ProfileRequest,
    SessionSummary,
    StudentProfile,
    TutorRequest,
    TutorResponse,
    WorkflowState,
)
from app.services.ai_workflow import (
    assess_answers,
    attach_tutor_response,
    create_profile as build_student_profile,
    get_state,
    list_sessions,
    start_workflow,
    tutor_answer,
)
from app.services.persistence_service import (
    get_persisted_workflow_state,
    list_persisted_sessions,
    persist_assessment_result,
    persist_workflow_state,
)
from app.services.llm_client import LLMConfigurationError, LLMResponseError

router = APIRouter(tags=["workflow"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/sessions", response_model=list[SessionSummary])
def sessions(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[SessionSummary]:
    persisted = list_persisted_sessions(db, user)
    return persisted or list_sessions()


@router.post("/profiles", response_model=StudentProfile)
def create_student_profile(request: ProfileRequest, _: User = Depends(get_current_user)) -> StudentProfile:
    try:
        return build_student_profile(request.message)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/workflow/start", response_model=WorkflowState)
def workflow_start(
    request: ProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowState:
    try:
        state = start_workflow(request)
        persist_workflow_state(db, user, state)
        return state
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/workflow/{session_id}", response_model=WorkflowState)
def workflow_state(
    session_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowState:
    try:
        return get_state(session_id)
    except KeyError as exc:
        persisted = get_persisted_workflow_state(db, user, session_id)
        if persisted is not None:
            return persisted
        raise HTTPException(status_code=404, detail="session not found") from exc


@router.post("/demo-workflow", response_model=WorkflowState)
def demo_workflow(
    request: ProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkflowState:
    try:
        state = start_workflow(request)
        persist_workflow_state(db, user, state)
        return state
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/tutor", response_model=TutorResponse)
def tutor(request: TutorRequest, _: User = Depends(get_current_user)) -> TutorResponse:
    try:
        if request.session_id:
            try:
                state = attach_tutor_response(request.session_id, request)
                if state.tutor is None:
                    raise HTTPException(status_code=500, detail="tutor response missing")
                return state.tutor
            except KeyError as exc:
                raise HTTPException(status_code=404, detail="session not found") from exc
        return tutor_answer(request)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/assessments", response_model=AssessmentResponse)
def assessment(
    request: AssessmentRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AssessmentResponse:
    try:
        response = assess_answers(request.session_id, request.answers)
        persist_assessment_result(db, user, get_state(request.session_id), response, request.answers)
        return response
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
