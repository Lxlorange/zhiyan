from datetime import datetime
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


class ProfileDialogueResponse(BaseModel):
    profile_id: int
    profile: StudentProfile
    update_reason: str
    extracted_features: Dict[str, object]
    revision: int


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
    session_id: Optional[str] = None
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


class KnowledgePointRead(BaseModel):
    id: int
    name: str
    description: str
    chapter: str
    prerequisites: List[str]
    tags: List[str]
    difficulty: str


class KnowledgeSearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    limit: int = Field(default=6, ge=1, le=20)


class KnowledgeSearchHit(BaseModel):
    document_title: str
    document_type: str
    knowledge_point: str
    content: str
    source_uri: str
    keywords: List[str]


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


class DirectionTemplateRead(BaseModel):
    id: int
    title: str
    description: str
    suitable_users: List[str]
    prerequisites: List[str]
    recommended_period: str
    resource_types: List[str]
    stage_outputs: List[str]
    related_chapters: List[str]
    related_documents: List[str]
    tags: List[str]
    is_teacher_recommended: bool

    model_config = {"from_attributes": True}


class DirectionTemplateCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: str = Field(..., min_length=4)
    suitable_users: List[str] = Field(default_factory=list)
    prerequisites: List[str] = Field(default_factory=list)
    recommended_period: str = Field(default="14-21 天", max_length=64)
    resource_types: List[str] = Field(default_factory=list)
    stage_outputs: List[str] = Field(default_factory=list)
    related_chapters: List[str] = Field(default_factory=list)
    related_documents: List[str] = Field(default_factory=list)
    tags: List[str] = Field(default_factory=list)
    is_teacher_recommended: bool = True


class DirectionAnalyzeRequest(BaseModel):
    message: str = Field(..., min_length=1)
    template_id: Optional[int] = None
    extra_context: str = ""


class DirectionAnalyzeResponse(BaseModel):
    normalized_title: str
    description: str
    domain: str
    route_type: str
    recommended_goal: str
    expected_output: str
    initial_knowledge_points: List[str]
    extracted: Dict[str, object]
    clarification_questions: List[str]
    risk_notes: List[str]
    suggested_project: Dict[str, object]
    agent_summary: str


class DirectionCreateRequest(BaseModel):
    message: str = Field(..., min_length=1)
    template_id: Optional[int] = None
    extra_context: str = ""


class ResearchDirectionRead(BaseModel):
    id: int
    template_id: Optional[int]
    title: str
    normalized_title: str
    domain: str
    goal_type: str
    description: str
    raw_input: str
    extracted_data: Dict[str, object]
    clarification_questions: List[str]
    risk_notes: List[str]
    status: str
    analysis_revision: int = 1
    review_status: str = "pending"
    review_notes: str = ""
    reviewed_by_user_id: Optional[int] = None
    reviewed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class DirectionReviewRequest(BaseModel):
    review_status: str = Field(..., pattern="^(approved|rejected|needs_revision)$")
    review_notes: str = Field(default="", max_length=1000)


class LearningProjectCreateRequest(BaseModel):
    direction_id: int
    title: Optional[str] = None
    daily_minutes: Optional[int] = Field(default=None, ge=10, le=300)
    recommended_period: Optional[str] = None
    difficulty: Optional[str] = None
    deadline: Optional[datetime] = None


class LearningProjectUpdateRequest(BaseModel):
    title: Optional[str] = None
    learning_goal: Optional[str] = None
    expected_output: Optional[str] = None
    recommended_period: Optional[str] = None
    daily_minutes: Optional[int] = Field(default=None, ge=10, le=300)
    difficulty: Optional[str] = None
    status: Optional[str] = None
    deadline: Optional[datetime] = None
    teacher_notes: Optional[str] = None


class LearningProjectRead(BaseModel):
    id: int
    direction_id: int
    title: str
    research_direction: str
    subject: str
    goal_type: str
    learning_goal: str
    foundation_summary: str
    expected_output: str
    recommended_period: str
    daily_minutes: int
    difficulty: str
    related_course: str
    related_knowledge_points: List[str]
    related_documents: List[str]
    status: str
    current_stage: str
    progress: int
    deadline: Optional[datetime] = None
    teacher_notes: str = ""
    risk_notes: List[str]
    personalization_strategy: List[str]
    today_recommendations: List[str]
    recent_classrooms: List[Dict[str, object]]
    current_weak_points: List[str]
    output_checklist: List[str]
    next_step: str
    generated_resource_count: int
    completed_item_count: int
    shared_token: str

    model_config = {"from_attributes": True}


class LearningProjectHomeResponse(BaseModel):
    project: LearningProjectRead
    current_stage: str
    today_recommendations: List[str]
    recent_classrooms: List[Dict[str, object]]
    current_weak_points: List[str]
    generated_resource_count: int
    completed_item_count: int
    next_step: str
    output_checklist: List[str]


class LearningProjectExportResponse(BaseModel):
    project: LearningProjectRead
    markdown: str


class DirectionDashboardResponse(BaseModel):
    total_directions: int
    total_projects: int
    review_distribution: Dict[str, int]
    domain_distribution: Dict[str, int]
    goal_type_distribution: Dict[str, int]
    project_status_distribution: Dict[str, int]
    risk_projects: List[LearningProjectRead]
    pending_reviews: List[ResearchDirectionRead]
    recommended_templates: List[DirectionTemplateRead]
