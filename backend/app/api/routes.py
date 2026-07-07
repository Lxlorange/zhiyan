from fastapi import APIRouter

from app.schemas import (
    AssessmentRequest,
    AssessmentResponse,
    DemoWorkflowResponse,
    ProfileRequest,
    StudentProfile,
    TutorRequest,
    TutorResponse,
)
from app.services.mock_agents import assess_answers, build_profile, run_demo_workflow, tutor_answer

router = APIRouter(prefix="/api")


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/profiles", response_model=StudentProfile)
def create_profile(request: ProfileRequest) -> StudentProfile:
    return build_profile(request)


@router.post("/demo-workflow", response_model=DemoWorkflowResponse)
def demo_workflow(request: ProfileRequest) -> DemoWorkflowResponse:
    return run_demo_workflow(request)


@router.post("/tutor", response_model=TutorResponse)
def tutor(request: TutorRequest) -> TutorResponse:
    return tutor_answer(request)


@router.post("/assessments", response_model=AssessmentResponse)
def assessment(request: AssessmentRequest) -> AssessmentResponse:
    return assess_answers(request.answers)
