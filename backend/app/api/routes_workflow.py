from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
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
from app.services.learning_workflow import (
    assess_answers,
    attach_tutor_response,
    create_profile as build_student_profile,
    get_state,
    list_sessions,
    start_workflow,
    tutor_answer,
)

router = APIRouter(tags=["workflow"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/sessions", response_model=list[SessionSummary])
def sessions(_: User = Depends(get_current_user)) -> list[SessionSummary]:
    return list_sessions()


@router.post("/profiles", response_model=StudentProfile)
def create_student_profile(request: ProfileRequest, _: User = Depends(get_current_user)) -> StudentProfile:
    return build_student_profile(request.message)


@router.post("/workflow/start", response_model=WorkflowState)
def workflow_start(request: ProfileRequest, _: User = Depends(get_current_user)) -> WorkflowState:
    return start_workflow(request)


@router.get("/workflow/{session_id}", response_model=WorkflowState)
def workflow_state(session_id: str, _: User = Depends(get_current_user)) -> WorkflowState:
    try:
        return get_state(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc


@router.post("/demo-workflow", response_model=WorkflowState)
def demo_workflow(request: ProfileRequest, _: User = Depends(get_current_user)) -> WorkflowState:
    return start_workflow(request)


@router.post("/tutor", response_model=TutorResponse)
def tutor(request: TutorRequest, _: User = Depends(get_current_user)) -> TutorResponse:
    if request.session_id:
        try:
            state = attach_tutor_response(request.session_id, request)
            if state.tutor is None:
                raise HTTPException(status_code=500, detail="tutor response missing")
            return state.tutor
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="session not found") from exc
    return tutor_answer(request)


@router.post("/assessments", response_model=AssessmentResponse)
def assessment(request: AssessmentRequest, _: User = Depends(get_current_user)) -> AssessmentResponse:
    try:
        return assess_answers(request.session_id, request.answers)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="session not found") from exc
