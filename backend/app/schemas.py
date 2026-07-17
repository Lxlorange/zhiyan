from datetime import datetime
from typing import Any, Dict, List, Optional

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
    avatar_url: str = ""
    school: str = ""
    major: str = ""
    bio: str = ""
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=64)
    email: Optional[EmailStr] = None
    avatar_url: Optional[str] = Field(default=None, max_length=512)
    school: Optional[str] = Field(default=None, max_length=128)
    major: Optional[str] = Field(default=None, max_length=128)
    bio: Optional[str] = Field(default=None, max_length=512)


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
    chunk_id: Optional[int] = None
    document_title: str
    document_type: str
    knowledge_point: str
    content: str
    source_uri: str
    keywords: List[str]
    page_no: Optional[int] = None
    slide_no: Optional[int] = None
    section_title: str = ""
    distance: Optional[float] = None
    keyword_hit: Optional[int] = None


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


class ProjectPlanMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str
    created_at: datetime


class ProjectPlanRequest(BaseModel):
    learning_type: str = Field(default="", pattern="^(|course_project|research_project|course_knowledge)$")
    learning_goal: str = Field(..., min_length=1, max_length=2000)
    extra_requirements: str = Field(default="", max_length=60000)


class ProjectPlanAdjustRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=60000)


class ProjectPlanRead(BaseModel):
    id: int
    learning_type: str
    learning_goal: str
    extra_requirements: str
    title: str
    plan_data: Dict[str, object]
    messages: List[ProjectPlanMessage]
    status: str
    direction_id: Optional[int] = None
    project_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectPlanBuildResponse(BaseModel):
    plan: ProjectPlanRead
    project: "LearningProjectRead"


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
    study_weekends: bool = False
    study_weekdays: List[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    recommended_period: Optional[str] = None
    difficulty: Optional[str] = None
    deadline: Optional[datetime] = None


class LearningProjectUpdateRequest(BaseModel):
    title: Optional[str] = None
    learning_goal: Optional[str] = None
    expected_output: Optional[str] = None
    recommended_period: Optional[str] = None
    daily_minutes: Optional[int] = Field(default=None, ge=10, le=300)
    study_weekends: Optional[bool] = None
    study_weekdays: Optional[List[int]] = None
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
    study_weekends: bool = False
    study_weekdays: List[int] = Field(default_factory=list)
    difficulty: str
    related_course: str
    related_knowledge_points: List[str]
    related_documents: List[str]
    research_training: Dict[str, object] = Field(default_factory=dict)
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


ProjectPlanBuildResponse.model_rebuild()


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


class SyllabusGenerateRequest(BaseModel):
    generation_goal: str = Field(default="", max_length=1200)
    force_new_version: bool = True


class SyllabusItemCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    item_type: str = Field(default="concept", max_length=64)
    stage: str = Field(default="自定义", max_length=128)
    difficulty: str = Field(default="medium", max_length=32)
    estimated_minutes: int = Field(default=45, ge=5, le=600)
    recommendation_reason: str = Field(default="用户手动添加", max_length=2000)
    objective: str = Field(default="", max_length=2000)
    prerequisites: List[str] = Field(default_factory=list)
    knowledge_points: List[str] = Field(default_factory=list)
    related_documents: List[str] = Field(default_factory=list)
    recommended_resource_types: List[str] = Field(default_factory=list)
    classroom_types: List[str] = Field(default_factory=list)
    completion_criteria: str = Field(default="", max_length=2000)
    assessment_method: str = Field(default="", max_length=2000)
    user_order: Optional[int] = Field(default=None, ge=1)
    is_locked: bool = False


class SyllabusItemUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=2, max_length=255)
    item_type: Optional[str] = Field(default=None, max_length=64)
    stage: Optional[str] = Field(default=None, max_length=128)
    difficulty: Optional[str] = Field(default=None, max_length=32)
    estimated_minutes: Optional[int] = Field(default=None, ge=5, le=600)
    recommendation_reason: Optional[str] = Field(default=None, max_length=2000)
    objective: Optional[str] = Field(default=None, max_length=2000)
    prerequisites: Optional[List[str]] = None
    knowledge_points: Optional[List[str]] = None
    related_documents: Optional[List[str]] = None
    recommended_resource_types: Optional[List[str]] = None
    classroom_types: Optional[List[str]] = None
    completion_criteria: Optional[str] = Field(default=None, max_length=2000)
    assessment_method: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[str] = Field(default=None, max_length=32)
    is_locked: Optional[bool] = None


class SyllabusItemStatusRequest(BaseModel):
    status: str = Field(..., pattern="^(pending|in_progress|completed|skipped|deep|mastered|split|merged)$")
    reason: str = Field(default="", max_length=1000)


class SyllabusReorderRequest(BaseModel):
    item_ids: List[int] = Field(..., min_length=1)


class SyllabusItemSplitRequest(BaseModel):
    parts: List[SyllabusItemCreateRequest] = Field(..., min_length=2, max_length=8)
    reason: str = Field(default="拆分为更细学习项", max_length=1000)


class SyllabusItemsMergeRequest(BaseModel):
    item_ids: List[int] = Field(..., min_length=2, max_length=8)
    title: str = Field(..., min_length=2, max_length=255)
    reason: str = Field(default="合并相似学习项", max_length=1000)


class SyllabusRegenerateStageRequest(BaseModel):
    stage: str = Field(..., min_length=1, max_length=128)
    instruction: str = Field(default="", max_length=1200)


class SyllabusAdaptRequest(BaseModel):
    trigger_type: str = Field(..., min_length=2, max_length=64)
    evidence: str = Field(..., min_length=2, max_length=1600)
    require_confirmation: bool = False


class DailyPlanGenerateRequest(BaseModel):
    start_date: Optional[datetime] = None
    daily_minutes: Optional[int] = Field(default=None, ge=10, le=300)
    study_weekends: bool = False
    study_weekdays: List[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4])
    title: str = Field(default="", max_length=255)


class DailyPlanMoveItemRequest(BaseModel):
    planned_date: datetime


class DailyPlanShiftItemRequest(BaseModel):
    direction: str = Field(default="next", pattern="^(next|previous)$")


class DailyPlanCoachRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=3000)
    active_item_id: Optional[int] = None


class SyllabusOperationRead(BaseModel):
    id: int
    operation_type: str
    summary: str
    payload: Dict[str, object]
    item_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SyllabusItemRead(BaseModel):
    id: int
    syllabus_version_id: int
    project_id: int
    title: str
    item_type: str
    stage: str
    difficulty: str
    estimated_minutes: int
    recommendation_reason: str
    objective: str
    prerequisites: List[str]
    knowledge_points: List[str]
    related_documents: List[str]
    recommended_resource_types: List[str]
    classroom_types: List[str]
    completion_criteria: str
    assessment_method: str
    status: str
    user_order: int
    is_locked: bool
    is_manual: bool

    model_config = {"from_attributes": True}


class SyllabusVersionRead(BaseModel):
    id: int
    project_id: int
    version_no: int
    generation_method: str
    generation_reason: str
    profile_revision: Optional[int] = None
    knowledge_base_version: str
    user_adjustments: List[Dict[str, object]]
    is_current: bool
    status: str
    agent_summary: Dict[str, object]
    created_at: datetime
    updated_at: datetime
    items: List[SyllabusItemRead] = Field(default_factory=list)
    operations: List[SyllabusOperationRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class SyllabusEnsureResponse(BaseModel):
    state: str
    message: str
    syllabus: Optional[SyllabusVersionRead] = None


class SyllabusVersionSummary(BaseModel):
    id: int
    project_id: int
    version_no: int
    generation_method: str
    generation_reason: str
    is_current: bool
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SyllabusCompareResponse(BaseModel):
    base_version: int
    target_version: int
    added: List[SyllabusItemRead]
    removed: List[SyllabusItemRead]
    changed: List[Dict[str, object]]


class ClassroomResourceRead(BaseModel):
    id: int
    resource_type: str
    title: str
    content_data: Dict[str, object]
    file_path: str
    source: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ClassroomSubmissionRead(BaseModel):
    id: int
    submission_type: str
    content: Dict[str, object]
    score: int
    passed: bool
    feedback: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ClassroomSessionRead(BaseModel):
    id: int
    syllabus_item_id: int
    project_id: int
    title: str
    status: str
    progress_state: Dict[str, object]
    ppt_resource_id: Optional[int] = None
    slides_completed: bool = False
    slide_progress: Dict[str, object] = Field(default_factory=dict)
    generation_started_at: Optional[datetime] = None
    generation_error: str = ""
    quiz_passed: bool
    practice_passed: bool
    reflection_passed: bool
    completed_at: Optional[datetime] = None
    resources: List[ClassroomResourceRead] = Field(default_factory=list)
    submissions: List[ClassroomSubmissionRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class ClassroomPptGenerateRequest(BaseModel):
    instruction: str = Field(default="", max_length=1200)


class ClassroomVisualizationGenerateRequest(BaseModel):
    instruction: str = Field(default="", max_length=1200)
    preferred_kind: str = Field(default="auto", pattern="^(auto|diagram|simulation|code|timeline|visualization3d)$")


class ClassroomVoiceGenerateRequest(BaseModel):
    voice_name: str = Field(default="xiaoyan", max_length=64)
    speed: int = Field(default=50, ge=0, le=100)
    text_scope: str = Field(default="current_slide", pattern="^(current_slide|one_minute|five_minutes|all_slides)$")
    slide_index: int = Field(default=0, ge=0, le=60)
    page_context: str = Field(default="", max_length=2000)


class ClassroomDialogueRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=3000)
    quick_action: str = Field(default="", max_length=64)


class ClassroomQuizSubmitRequest(BaseModel):
    answers: Dict[str, str] = Field(..., min_length=1)


class ClassroomSlidesCompleteRequest(BaseModel):
    current_index: int = Field(..., ge=0)
    total_slides: int = Field(..., ge=1, le=60)
    visited_indices: List[int] = Field(..., min_length=1)


class ClassroomPracticeSubmitRequest(BaseModel):
    report: str = Field(..., min_length=30, max_length=5000)
    artifact_url: str = Field(default="", max_length=512)
    key_result: str = Field(default="", max_length=2000)


class ClassroomReflectionSubmitRequest(BaseModel):
    reflection: str = Field(..., min_length=50, max_length=5000)
    unresolved_questions: List[str] = Field(default_factory=list)
    next_action: str = Field(default="", max_length=1000)


class ClassroomNoteSaveRequest(BaseModel):
    markdown: str = Field(..., min_length=1, max_length=12000)
    slide_index: int = Field(default=0, ge=0, le=60)
    slide_title: str = Field(default="", max_length=255)


class ClassroomDialogueResponse(BaseModel):
    answer: str
    cards: List[Dict[str, object]] = Field(default_factory=list)
    suggested_actions: List[str] = Field(default_factory=list)
    profile_update_suggestion: str = ""
    session: ClassroomSessionRead


class DailyPlanItemRead(BaseModel):
    id: int
    day_index: int
    planned_date: datetime
    title: str
    estimated_minutes: int
    learning_focus: str
    resource_types: List[str]
    status: str
    user_order: int
    syllabus_item_id: Optional[int] = None
    project_id: int
    is_overdue: bool = False
    is_today: bool = False
    can_start: bool = True

    model_config = {"from_attributes": True}


class DailyPlanRead(BaseModel):
    id: int
    project_id: int
    syllabus_version_id: int
    title: str
    start_date: datetime
    daily_minutes: int
    study_weekends: bool = False
    study_weekdays: List[int] = Field(default_factory=list)
    generation_reason: str
    status: str
    created_at: datetime
    items: List[DailyPlanItemRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class DailyPlanCoachResponse(BaseModel):
    answer: str
    extracted_profile_signals: Dict[str, object] = Field(default_factory=dict)
    suggested_plan_actions: List[str] = Field(default_factory=list)
    profile_revision: Optional[int] = None
    plan: DailyPlanRead


class ProfileVersionRead(BaseModel):
    id: int
    revision: int
    source: str
    update_reason: str
    extracted_features: Dict[str, object]
    profile_data: Dict[str, object]
    created_at: datetime

    model_config = {"from_attributes": True}


class ProfileCenterResponse(BaseModel):
    profile_id: Optional[int] = None
    current_revision: int = 0
    profile_data: Dict[str, object] = Field(default_factory=dict)
    entries: List["ProfileEntryRead"] = Field(default_factory=list)
    versions: List[ProfileVersionRead] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class ProfileEntryRead(BaseModel):
    key: str
    label: str
    value: Any = None
    confidence: int = Field(default=70, ge=0, le=100)
    source: str = "unknown"
    source_object_id: Optional[str] = None
    agent: str = "MemoryAgent"
    is_confirmed: bool = False
    is_enabled: bool = True
    revision: int = 0
    updated_at: Optional[datetime] = None


class ProfileEntryUpdateRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=64)
    value: Any = None
    confidence: int = Field(default=90, ge=0, le=100)
    source: str = Field(default="manual", max_length=64)
    source_object_id: Optional[str] = Field(default=None, max_length=128)
    is_confirmed: bool = True
    is_enabled: bool = True
    update_reason: str = Field(default="用户手动编辑画像条目", max_length=1000)


ProfileCenterResponse.model_rebuild()


class LiteraturePaperCreateRequest(BaseModel):
    project_id: Optional[int] = None
    title: str = Field(..., min_length=1, max_length=255)
    authors: List[str] = Field(default_factory=list)
    venue: str = Field(default="", max_length=255)
    year: str = Field(default="", max_length=32)
    source_uri: str = Field(default="", max_length=512)
    abstract: str = Field(default="", max_length=8000)
    keywords: List[str] = Field(default_factory=list)
    reading_status: str = Field(default="unread", pattern="^(unread|reading|read|cited)$")
    notes: str = Field(default="", max_length=8000)


class LiteraturePaperUpdateRequest(BaseModel):
    title: Optional[str] = Field(default=None, min_length=1, max_length=255)
    authors: Optional[List[str]] = None
    venue: Optional[str] = Field(default=None, max_length=255)
    year: Optional[str] = Field(default=None, max_length=32)
    source_uri: Optional[str] = Field(default=None, max_length=512)
    abstract: Optional[str] = Field(default=None, max_length=8000)
    keywords: Optional[List[str]] = None
    reading_status: Optional[str] = Field(default=None, pattern="^(unread|reading|read|cited)$")
    notes: Optional[str] = Field(default=None, max_length=8000)


class LiteraturePaperRead(BaseModel):
    id: int
    project_id: Optional[int] = None
    title: str
    authors: List[str]
    venue: str
    year: str
    source_uri: str
    abstract: str
    keywords: List[str]
    reading_status: str
    notes: str
    citation_text: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResearchToolRunRequest(BaseModel):
    project_id: Optional[int] = None
    tool_type: str = Field(..., pattern="^(polish|format|citation|review|method|experiment|reproduce|topic|defense|paper_reading)$")
    input_text: str = Field(..., min_length=2, max_length=12000)
    extra_requirement: str = Field(default="", max_length=3000)


class ResearchToolRunRead(BaseModel):
    id: int
    project_id: Optional[int] = None
    tool_type: str
    title: str
    input_text: str
    output_data: Dict[str, object]
    agent_trace: List[Dict[str, object]]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class PracticeQuestionRead(BaseModel):
    id: str
    type: str
    point: str
    prompt: str
    options: List[str] = Field(default_factory=list)
    answer: str
    explanation: str = ""
    source_title: str = ""
    source_excerpt: str = ""
    difficulty: str = "medium"


class PracticeGenerateRequest(BaseModel):
    weak_points: List[str] = Field(default_factory=list, max_length=12)
    question_types: List[str] = Field(default_factory=lambda: ["choice", "judgement"], max_length=3)
    project_id: Optional[int] = None
    difficulty: str = Field(default="medium", pattern="^(easy|medium|hard)$")
    count_per_point: int = Field(default=1, ge=1, le=3)


class PracticeGenerateResponse(BaseModel):
    questions: List[PracticeQuestionRead]
    used_llm: bool = False
    source_summary: str = ""


class WorkspaceOverviewResponse(BaseModel):
    projects: List[LearningProjectRead] = Field(default_factory=list)
    profile: ProfileCenterResponse
    resources: List[ClassroomResourceRead] = Field(default_factory=list)
    agent_tasks: List[AgentTrace] = Field(default_factory=list)
    submissions: List[ClassroomSubmissionRead] = Field(default_factory=list)
    literature: List[LiteraturePaperRead] = Field(default_factory=list)
    tool_runs: List[ResearchToolRunRead] = Field(default_factory=list)
    metrics: Dict[str, int] = Field(default_factory=dict)


class DatabaseAskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=3000)
    project_id: Optional[int] = None
    knowledge_points: List[str] = Field(default_factory=list)
    limit: int = Field(default=8, ge=1, le=16)


class DatabaseCitation(BaseModel):
    id: str
    source_type: str
    title: str
    document_type: str = ""
    knowledge_point: str = ""
    content: str
    source_uri: str = ""
    page_no: Optional[int] = None
    slide_no: Optional[int] = None
    section_title: str = ""
    score: Optional[float] = None
    review_url: str = ""


class DatabaseAskResponse(BaseModel):
    answer: str
    citations: List[DatabaseCitation] = Field(default_factory=list)
    related_points: List[str] = Field(default_factory=list)
    follow_up_questions: List[str] = Field(default_factory=list)
    confidence: str = "medium"
    used_llm: bool = False


class DatabaseGraphNode(BaseModel):
    id: str
    name: str
    category: str
    description: str = ""
    count: int = 0


class DatabaseGraphEdge(BaseModel):
    source: str
    target: str
    relation: str = "related"


class DatabaseGraphResponse(BaseModel):
    nodes: List[DatabaseGraphNode] = Field(default_factory=list)
    edges: List[DatabaseGraphEdge] = Field(default_factory=list)


class DatabaseNodeDetailResponse(BaseModel):
    name: str
    description: str = ""
    citations: List[DatabaseCitation] = Field(default_factory=list)
    related_points: List[str] = Field(default_factory=list)
    suggested_questions: List[str] = Field(default_factory=list)
