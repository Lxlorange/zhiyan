from typing import Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72)
    full_name: str = Field(default="", max_length=64)
    role: str = Field(default="student", pattern="^(student|teacher|admin)$")


class UserLogin(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class UserRead(BaseModel):
    id: int
    username: str
    email: EmailStr
    full_name: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserRead


class ProfileRequest(BaseModel):
    message: str = Field(..., min_length=1)


class StudentProfile(BaseModel):
    knowledge_base: str
    learning_goal: str
    cognitive_style: str
    weak_points: List[str]
    practice_level: str
    resource_preference: List[str]
    learning_pace: str
    interest_direction: str
    mastery: Dict[str, int] = Field(default_factory=dict)
    revision: int = 1


class KnowledgeGap(BaseModel):
    id: str
    title: str
    severity: str
    evidence: str
    related_points: List[str]


class LearningStep(BaseModel):
    id: str
    title: str
    objective: str
    reason: str
    resources: List[str]
    estimated_minutes: int
    status: str = "pending"


class AgentTrace(BaseModel):
    agent: str
    status: str
    input_summary: str
    output_summary: str
    latency_ms: int


class ResourceCard(BaseModel):
    id: str
    type: str
    title: str
    target_profile: str
    knowledge_points: List[str]
    content: str
    format_hint: str
    sources: List[str]
    safety_notes: List[str] = Field(default_factory=list)


class TutorRequest(BaseModel):
    question: str = Field(..., min_length=1)
    profile: Optional[StudentProfile] = None


class TutorResponse(BaseModel):
    answer: str
    knowledge_points: List[str]
    sources: List[str]
    follow_up_exercise: str
    strategy: str


class QuizQuestion(BaseModel):
    id: str
    prompt: str
    options: List[str]
    answer: str
    knowledge_point: str


class AssessmentRequest(BaseModel):
    session_id: str
    answers: Dict[str, str]


class AssessmentResponse(BaseModel):
    score: int
    weak_points: List[str]
    correct: Dict[str, bool]
    feedback: List[str]
    updated_profile: StudentProfile
    updated_path: List[LearningStep]
    updated_suggestion: str


class WorkflowState(BaseModel):
    session_id: str
    profile: StudentProfile
    gaps: List[KnowledgeGap]
    path: List[LearningStep]
    resources: List[ResourceCard]
    quiz: List[QuizQuestion]
    tutor: Optional[TutorResponse] = None
    assessment: Optional[AssessmentResponse] = None
    agent_trace: List[AgentTrace]


class CourseMapResponse(BaseModel):
    course: str
    chapters: List[str]
    knowledge_points: List[str]


class SessionSummary(BaseModel):
    session_id: str
    title: str
    profile_revision: int
    weak_points: List[str]


class DashboardMetric(BaseModel):
    label: str
    value: str
    trend: str


class TeacherDashboardResponse(BaseModel):
    metrics: List[DashboardMetric]
    weak_point_distribution: Dict[str, int]
    resource_type_distribution: Dict[str, int]
    at_risk_students: List[SessionSummary]
    teaching_suggestions: List[str]
