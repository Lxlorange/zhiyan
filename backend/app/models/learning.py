from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class StudentProfileRecord(Base):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    current_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    profile_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    versions: Mapped[list["StudentProfileVersion"]] = relationship(
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="StudentProfileVersion.revision",
    )


class StudentProfileVersion(Base):
    __tablename__ = "student_profile_versions"
    __table_args__ = (UniqueConstraint("profile_id", "revision", name="uq_profile_revision"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"), index=True, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(64), default="dialogue", nullable=False)
    update_reason: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_features: Mapped[dict] = mapped_column(JSONB, nullable=False)
    profile_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    profile: Mapped[StudentProfileRecord] = relationship(back_populates="versions")


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    chapters: Mapped[list["CourseChapter"]] = relationship(back_populates="course", cascade="all, delete-orphan")


class CourseChapter(Base):
    __tablename__ = "course_chapters"
    __table_args__ = (UniqueConstraint("course_id", "order_index", name="uq_course_chapter_order"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    course: Mapped[Course] = relationship(back_populates="chapters")
    knowledge_points: Mapped[list["KnowledgePoint"]] = relationship(back_populates="chapter", cascade="all, delete-orphan")


class KnowledgePoint(Base):
    __tablename__ = "knowledge_points"
    __table_args__ = (UniqueConstraint("chapter_id", "name", name="uq_chapter_knowledge_point"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chapter_id: Mapped[int] = mapped_column(ForeignKey("course_chapters.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    prerequisites: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    tags: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)

    chapter: Mapped[CourseChapter] = relationship(back_populates="knowledge_points")


class KnowledgeDocument(Base):
    __tablename__ = "knowledge_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    course_id: Mapped[int] = mapped_column(ForeignKey("courses.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    doc_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_uri: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("knowledge_documents.id"), index=True, nullable=False)
    knowledge_point_id: Mapped[Optional[int]] = mapped_column(ForeignKey("knowledge_points.id"), index=True, nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    keywords: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)

    document: Mapped[KnowledgeDocument] = relationship(back_populates="chunks")


class WorkflowSessionRecord(Base):
    __tablename__ = "workflow_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    profile_id: Mapped[Optional[int]] = mapped_column(ForeignKey("student_profiles.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    state_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class GeneratedResourceRecord(Base):
    __tablename__ = "generated_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    resource_key: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    knowledge_points: Mapped[list] = mapped_column(JSONB, nullable=False)
    content_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    sources: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    safety_notes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AgentTaskRecord(Base):
    __tablename__ = "agent_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    agent: Mapped[str] = mapped_column(String(80), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    input_summary: Mapped[str] = mapped_column(Text, nullable=False)
    output_summary: Mapped[str] = mapped_column(Text, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class LearningPathRecord(Base):
    __tablename__ = "learning_paths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    steps_data: Mapped[list] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class AnswerRecord(Base):
    __tablename__ = "answer_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    question_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    knowledge_point: Mapped[str] = mapped_column(String(128), nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    expected_answer: Mapped[str] = mapped_column(Text, nullable=False)
    is_correct: Mapped[bool] = mapped_column(nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ResearchDirectionTemplate(Base):
    __tablename__ = "research_direction_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    suitable_users: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    prerequisites: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    recommended_period: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    resource_types: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    stage_outputs: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    related_chapters: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    related_documents: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    tags: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    created_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_teacher_recommended: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ResearchDirection(Base):
    __tablename__ = "research_directions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    template_id: Mapped[Optional[int]] = mapped_column(ForeignKey("research_direction_templates.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    domain: Mapped[str] = mapped_column(String(128), nullable=False)
    goal_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    raw_input: Mapped[str] = mapped_column(Text, nullable=False)
    extracted_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    clarification_questions: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    risk_notes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    analysis_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    review_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    reviewed_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class LearningProject(Base):
    __tablename__ = "learning_projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    direction_id: Mapped[int] = mapped_column(ForeignKey("research_directions.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    research_direction: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(128), nullable=False)
    goal_type: Mapped[str] = mapped_column(String(64), nullable=False)
    learning_goal: Mapped[str] = mapped_column(Text, nullable=False)
    foundation_summary: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    recommended_period: Mapped[str] = mapped_column(String(64), nullable=False)
    daily_minutes: Mapped[int] = mapped_column(Integer, default=40, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(32), nullable=False)
    related_course: Mapped[str] = mapped_column(String(255), nullable=False)
    related_knowledge_points: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    related_documents: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    current_stage: Mapped[str] = mapped_column(String(128), default="方向确认", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    teacher_notes: Mapped[str] = mapped_column(Text, default="", nullable=False)
    risk_notes: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    personalization_strategy: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    today_recommendations: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    recent_classrooms: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    current_weak_points: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    output_checklist: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    next_step: Mapped[str] = mapped_column(Text, default="", nullable=False)
    generated_resource_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_item_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    shared_token: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_learned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class LearningProjectEvent(Base):
    __tablename__ = "learning_project_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("learning_projects.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ResearchDirectionEvent(Base):
    __tablename__ = "research_direction_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    direction_id: Mapped[int] = mapped_column(ForeignKey("research_directions.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class ProjectPlanSession(Base):
    __tablename__ = "project_plan_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    learning_type: Mapped[str] = mapped_column(String(64), default="none", nullable=False)
    learning_goal: Mapped[str] = mapped_column(Text, nullable=False)
    extra_requirements: Mapped[str] = mapped_column(Text, default="", nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    plan_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    messages: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="planning", nullable=False)
    direction_id: Mapped[Optional[int]] = mapped_column(ForeignKey("research_directions.id"), nullable=True)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("learning_projects.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class LearningSyllabusVersion(Base):
    __tablename__ = "learning_syllabus_versions"
    __table_args__ = (UniqueConstraint("project_id", "version_no", name="uq_project_syllabus_version"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("learning_projects.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    generation_method: Mapped[str] = mapped_column(String(64), default="ai", nullable=False)
    generation_reason: Mapped[str] = mapped_column(Text, nullable=False)
    profile_revision: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    knowledge_base_version: Mapped[str] = mapped_column(String(128), default="AI4S-PRACTICE", nullable=False)
    user_adjustments: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    agent_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    items: Mapped[list["LearningSyllabusItem"]] = relationship(
        back_populates="syllabus_version",
        cascade="all, delete-orphan",
        order_by="LearningSyllabusItem.user_order",
    )
    operations: Mapped[list["LearningSyllabusOperation"]] = relationship(
        back_populates="syllabus_version",
        cascade="all, delete-orphan",
        order_by="LearningSyllabusOperation.created_at",
    )


class LearningSyllabusItem(Base):
    __tablename__ = "learning_syllabus_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    syllabus_version_id: Mapped[int] = mapped_column(ForeignKey("learning_syllabus_versions.id"), index=True, nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("learning_projects.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    item_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    stage: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    difficulty: Mapped[str] = mapped_column(String(32), default="medium", nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=45, nullable=False)
    recommendation_reason: Mapped[str] = mapped_column(Text, nullable=False)
    objective: Mapped[str] = mapped_column(Text, nullable=False)
    prerequisites: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    knowledge_points: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    related_documents: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    recommended_resource_types: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    classroom_types: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    completion_criteria: Mapped[str] = mapped_column(Text, default="", nullable=False)
    assessment_method: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True, nullable=False)
    user_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    syllabus_version: Mapped[LearningSyllabusVersion] = relationship(back_populates="items")


class LearningSyllabusOperation(Base):
    __tablename__ = "learning_syllabus_operations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    syllabus_version_id: Mapped[int] = mapped_column(ForeignKey("learning_syllabus_versions.id"), index=True, nullable=False)
    item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("learning_syllabus_items.id"), index=True, nullable=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("learning_projects.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    operation_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    syllabus_version: Mapped[LearningSyllabusVersion] = relationship(back_populates="operations")


class ClassroomSession(Base):
    __tablename__ = "classroom_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    syllabus_item_id: Mapped[int] = mapped_column(ForeignKey("learning_syllabus_items.id"), index=True, nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("learning_projects.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="learning", nullable=False)
    progress_state: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    ppt_resource_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    slides_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    slide_progress: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    quiz_passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    practice_passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    reflection_passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    resources: Mapped[list["ClassroomResource"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        foreign_keys="ClassroomResource.session_id",
        order_by="ClassroomResource.created_at",
    )
    submissions: Mapped[list["ClassroomSubmission"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="ClassroomSubmission.created_at",
    )


class ClassroomResource(Base):
    __tablename__ = "classroom_resources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("classroom_sessions.id"), index=True, nullable=False)
    syllabus_item_id: Mapped[int] = mapped_column(ForeignKey("learning_syllabus_items.id"), index=True, nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("learning_projects.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), default="", nullable=False)
    source: Mapped[str] = mapped_column(String(128), default="OpenMAIC-inspired", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="ready", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    session: Mapped[ClassroomSession] = relationship(
        back_populates="resources",
        foreign_keys=[session_id],
    )


class ClassroomSubmission(Base):
    __tablename__ = "classroom_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("classroom_sessions.id"), index=True, nullable=False)
    syllabus_item_id: Mapped[int] = mapped_column(ForeignKey("learning_syllabus_items.id"), index=True, nullable=False)
    project_id: Mapped[int] = mapped_column(ForeignKey("learning_projects.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    submission_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    feedback: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    session: Mapped[ClassroomSession] = relationship(back_populates="submissions")


class DailyLearningPlan(Base):
    __tablename__ = "daily_learning_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("learning_projects.id"), index=True, nullable=False)
    syllabus_version_id: Mapped[int] = mapped_column(ForeignKey("learning_syllabus_versions.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    daily_minutes: Mapped[int] = mapped_column(Integer, default=40, nullable=False)
    generation_reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    items: Mapped[list["DailyLearningPlanItem"]] = relationship(
        back_populates="daily_plan",
        cascade="all, delete-orphan",
        order_by="DailyLearningPlanItem.day_index, DailyLearningPlanItem.user_order",
    )


class DailyLearningPlanItem(Base):
    __tablename__ = "daily_learning_plan_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    daily_plan_id: Mapped[int] = mapped_column(ForeignKey("daily_learning_plans.id"), index=True, nullable=False)
    syllabus_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("learning_syllabus_items.id"), index=True, nullable=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("learning_projects.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    day_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, default=40, nullable=False)
    learning_focus: Mapped[str] = mapped_column(Text, default="", nullable=False)
    resource_types: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    user_order: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    daily_plan: Mapped[DailyLearningPlan] = relationship(back_populates="items")
