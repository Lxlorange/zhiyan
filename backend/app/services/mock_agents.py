from app.schemas import AssessmentResponse, ProfileRequest, StudentProfile, TutorRequest, TutorResponse, WorkflowState
from app.services.ai_workflow import assess_answers, create_profile, start_workflow, tutor_answer


def build_profile(request: ProfileRequest) -> StudentProfile:
    return create_profile(request.message)


def run_demo_workflow(request: ProfileRequest) -> WorkflowState:
    return start_workflow(request)
