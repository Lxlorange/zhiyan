from __future__ import annotations

import json
import time
from datetime import datetime
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.learning import (
    AgentTaskRecord,
    LearningProject,
    LearningProjectEvent,
    ResearchDirection,
    ResearchDirectionEvent,
    ResearchDirectionTemplate,
    StudentProfileRecord,
)
from app.models.user import User
from app.schemas import (
    DirectionAnalyzeRequest,
    DirectionAnalyzeResponse,
    DirectionDashboardResponse,
    DirectionReviewRequest,
    DirectionTemplateCreateRequest,
    DirectionTemplateRead,
    LearningProjectCreateRequest,
    LearningProjectExportResponse,
    LearningProjectHomeResponse,
    LearningProjectRead,
    LearningProjectUpdateRequest,
    ResearchDirectionRead,
)
from app.services.knowledge_service import COURSE_TITLE
from app.services.knowledge_service import search_knowledge
from app.services.llm_client import qwen_chat_json


DIRECTION_TEMPLATE_SEEDS: list[dict] = []


class ProjectSuggestion(BaseModel):
    title: str
    research_direction: str
    subject: str
    goal_type: str
    learning_goal: str
    foundation_summary: str
    expected_output: str
    recommended_period: str
    daily_minutes: int = Field(..., ge=10, le=300)
    difficulty: str
    related_course: str
    related_knowledge_points: list[str]
    related_documents: list[str]
    risk_notes: list[str]
    personalization_strategy: list[str]
    today_recommendations: list[str]
    current_weak_points: list[str]
    output_checklist: list[str]
    next_step: str


class DirectionAgentResult(BaseModel):
    normalized_title: str
    description: str
    domain: str
    route_type: str
    recommended_goal: str
    expected_output: str
    initial_knowledge_points: list[str]
    extracted: dict
    clarification_questions: list[str]
    risk_notes: list[str]
    suggested_project: ProjectSuggestion
    agent_summary: str


def seed_direction_templates(db: Session) -> None:
    return


def list_direction_templates(db: Session) -> list[DirectionTemplateRead]:
    seed_direction_templates(db)
    rows = db.scalars(select(ResearchDirectionTemplate).order_by(ResearchDirectionTemplate.id)).all()
    return [DirectionTemplateRead.model_validate(row) for row in rows]


def create_direction_template(db: Session, user: User, request: DirectionTemplateCreateRequest) -> DirectionTemplateRead:
    existing = db.scalar(select(ResearchDirectionTemplate).where(ResearchDirectionTemplate.title == request.title))
    if existing:
        raise ValueError("direction template title already exists")
    template = ResearchDirectionTemplate(
        **request.model_dump(mode="json"),
        created_by_user_id=user.id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return DirectionTemplateRead.model_validate(template)


def _template_context(template: ResearchDirectionTemplate | None) -> str:
    if template is None:
        return "未选择方向模板。"
    return (
        f"方向模板：{template.title}\n"
        f"简介：{template.description}\n"
        f"适合人群：{template.suitable_users}\n"
        f"前置知识：{template.prerequisites}\n"
        f"推荐周期：{template.recommended_period}\n"
        f"资源类型：{template.resource_types}\n"
        f"阶段产出：{template.stage_outputs}\n"
        f"关联章节：{template.related_chapters}\n"
        f"关联资料：{template.related_documents}"
    )


def _latest_profile_context(db: Session, user: User | None) -> str:
    if user is None:
        return "No authenticated user profile."
    profile = db.scalar(
        select(StudentProfileRecord)
        .where(StudentProfileRecord.user_id == user.id)
        .order_by(StudentProfileRecord.updated_at.desc())
    )
    if profile is None:
        return "No profile record yet. Infer only from this request and course knowledge."
    return json.dumps(profile.profile_data, ensure_ascii=False)


def _knowledge_context(db: Session, query: str) -> str:
    hits = search_knowledge(db, query, limit=5)
    if not hits:
        return "No directly matched course knowledge. Mark sources that need to be added."
    return "\n".join(
        (
            f"- {hit.knowledge_point} / {hit.document_title} / {hit.document_type}: "
            f"{hit.content} source={hit.source_uri}"
        )
        for hit in hits
    )


def analyze_direction(db: Session, request: DirectionAnalyzeRequest, user: User | None = None) -> DirectionAnalyzeResponse:
    seed_direction_templates(db)
    template = None
    if request.template_id is not None:
        template = db.get(ResearchDirectionTemplate, request.template_id)
    profile_context = _latest_profile_context(db, user)
    knowledge_context = _knowledge_context(db, f"{request.message} {request.extra_context or ''}")
    prompt = f"""
你是 DirectionAgent，负责把用户输入的科研方向或课程目标转化为结构化学习项目建议。
必须只输出 JSON，且严格匹配 schema。

课程输入：{COURSE_TITLE}
模板上下文：
{_template_context(template)}

用户输入：
{request.message}

用户补充：
{request.extra_context or "无"}

要求：
1. 从自然语言抽取领域名称、所属学科、已有基础、目标产出、学习周期、学习偏好、可能知识点、目标类型。
2. 如果输入过于模糊，clarification_questions 必须给出 2-4 个澄清问题，但仍需给出可保存的草稿项目建议。
3. suggested_project 必须是完整学习项目容器，包含项目名、科研方向、学科类别、目标类型、学习目标、基础摘要、预期产出、推荐周期、每日时长、难度、课程、知识点、资料、风险、个性化策略、今日建议、薄弱点、产出清单、下一步。
4. 对作业代写、论文代写、虚构实验结果、虚构引用必须给出 risk_notes。
5. 不要让画像成为用户可见中心，项目建议应围绕科研方向学习。

schema:
{json.dumps(DirectionAgentResult.model_json_schema(mode="validation"), ensure_ascii=False)}
"""
    prompt = f"""{prompt}

Additional personalization context:
- User profile context: {profile_context}
- Course knowledge context:
{knowledge_context}
"""
    result = qwen_chat_json(
        "你是高校 AI4S 个性化学习平台的科研方向理解智能体。只返回合法 JSON。",
        prompt,
        DirectionAgentResult,
    )
    return DirectionAnalyzeResponse(**result.model_dump(mode="json"))


def _record_direction_ai_trace(
    db: Session,
    user: User,
    direction: ResearchDirection,
    request: DirectionAnalyzeRequest,
    analyzed: DirectionAnalyzeResponse,
    latency_ms: int,
) -> None:
    summary = analyzed.agent_summary or analyzed.description[:180]
    db.add(
        AgentTaskRecord(
            session_id=f"direction:{direction.id}",
            user_id=user.id,
            agent="DirectionAgent",
            status="success",
            input_summary=f"message={request.message[:220]}; template_id={request.template_id}",
            output_summary=summary[:500],
            latency_ms=latency_ms,
        )
    )
    db.add(
        ResearchDirectionEvent(
            direction_id=direction.id,
            user_id=user.id,
            event_type="ai_analyzed",
            summary=summary[:500],
            payload={
                "template_id": request.template_id,
                "extra_context": request.extra_context,
                "latency_ms": latency_ms,
                "analysis_revision": direction.analysis_revision,
            },
        )
    )


def create_direction(db: Session, user: User, request: DirectionAnalyzeRequest) -> ResearchDirection:
    started = time.perf_counter()
    analyzed = analyze_direction(db, request, user)
    latency_ms = int((time.perf_counter() - started) * 1000)
    direction = ResearchDirection(
        user_id=user.id,
        template_id=request.template_id,
        title=analyzed.normalized_title,
        normalized_title=analyzed.normalized_title,
        domain=analyzed.domain,
        goal_type=analyzed.route_type,
        description=analyzed.description,
        raw_input=request.message,
        extracted_data=analyzed.model_dump(mode="json"),
        clarification_questions=analyzed.clarification_questions,
        risk_notes=analyzed.risk_notes,
        status="draft" if analyzed.clarification_questions else "ready",
    )
    db.add(direction)
    db.flush()
    _record_direction_ai_trace(db, user, direction, request, analyzed, latency_ms)
    db.commit()
    db.refresh(direction)
    return direction


def list_directions(db: Session, user: User) -> list[ResearchDirectionRead]:
    rows = db.scalars(
        select(ResearchDirection).where(ResearchDirection.user_id == user.id).order_by(ResearchDirection.updated_at.desc())
    ).all()
    return [ResearchDirectionRead.model_validate(row) for row in rows]


def get_direction_or_404(db: Session, user: User, direction_id: int) -> ResearchDirection:
    direction = db.get(ResearchDirection, direction_id)
    if direction is None or direction.user_id != user.id:
        raise KeyError("direction not found")
    return direction


def regenerate_direction(db: Session, user: User, direction_id: int) -> ResearchDirection:
    direction = get_direction_or_404(db, user, direction_id)
    request = DirectionAnalyzeRequest(
        message=direction.raw_input,
        template_id=direction.template_id,
        extra_context="Regenerate from saved research direction. Preserve user goal but refresh structure and risks.",
    )
    previous = direction.extracted_data
    started = time.perf_counter()
    analyzed = analyze_direction(db, request, user)
    latency_ms = int((time.perf_counter() - started) * 1000)
    direction.title = analyzed.normalized_title
    direction.normalized_title = analyzed.normalized_title
    direction.domain = analyzed.domain
    direction.goal_type = analyzed.route_type
    direction.description = analyzed.description
    direction.extracted_data = analyzed.model_dump(mode="json")
    direction.clarification_questions = analyzed.clarification_questions
    direction.risk_notes = analyzed.risk_notes
    direction.status = "draft" if analyzed.clarification_questions else "ready"
    direction.analysis_revision += 1
    direction.review_status = "pending"
    direction.review_notes = ""
    db.add(
        ResearchDirectionEvent(
            direction_id=direction.id,
            user_id=user.id,
            event_type="regenerated",
            summary="Direction analysis regenerated.",
            payload={
                "previous_revision": direction.analysis_revision - 1,
                "new_revision": direction.analysis_revision,
                "previous_title": previous.get("normalized_title") if isinstance(previous, dict) else "",
            },
        )
    )
    _record_direction_ai_trace(db, user, direction, request, analyzed, latency_ms)
    db.commit()
    db.refresh(direction)
    return direction


def create_project(db: Session, user: User, request: LearningProjectCreateRequest) -> LearningProject:
    direction = get_direction_or_404(db, user, request.direction_id)
    suggestion = ProjectSuggestion.model_validate(DirectionAnalyzeResponse(**direction.extracted_data).suggested_project)
    title = request.title or suggestion.title
    project = LearningProject(
        user_id=user.id,
        direction_id=direction.id,
        title=title,
        research_direction=suggestion.research_direction,
        subject=suggestion.subject,
        goal_type=suggestion.goal_type,
        learning_goal=suggestion.learning_goal,
        foundation_summary=suggestion.foundation_summary,
        expected_output=suggestion.expected_output,
        recommended_period=request.recommended_period or suggestion.recommended_period,
        daily_minutes=request.daily_minutes or suggestion.daily_minutes,
        difficulty=request.difficulty or suggestion.difficulty,
        deadline=request.deadline,
        related_course=suggestion.related_course,
        related_knowledge_points=suggestion.related_knowledge_points,
        related_documents=suggestion.related_documents,
        status="draft",
        risk_notes=suggestion.risk_notes,
        personalization_strategy=suggestion.personalization_strategy,
        today_recommendations=suggestion.today_recommendations,
        current_weak_points=suggestion.current_weak_points,
        output_checklist=suggestion.output_checklist,
        next_step=suggestion.next_step,
    )
    db.add(project)
    db.flush()
    db.add(
        LearningProjectEvent(
            project_id=project.id,
            user_id=user.id,
            event_type="created",
            summary="根据科研方向理解结果创建学习项目。",
            payload={"direction_id": direction.id},
        )
    )
    db.commit()
    db.refresh(project)
    return project


def list_projects(db: Session, user: User) -> list[LearningProjectRead]:
    rows = db.scalars(
        select(LearningProject).where(LearningProject.user_id == user.id).order_by(LearningProject.updated_at.desc())
    ).all()
    return [LearningProjectRead.model_validate(row) for row in rows]


def get_project_or_404(db: Session, user: User, project_id: int) -> LearningProject:
    project = db.get(LearningProject, project_id)
    if project is None or project.user_id != user.id:
        raise KeyError("project not found")
    return project


def update_project(
    db: Session,
    user: User,
    project_id: int,
    request: LearningProjectUpdateRequest,
) -> LearningProject:
    project = get_project_or_404(db, user, project_id)
    data = request.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(project, key, value)
    db.add(
        LearningProjectEvent(
            project_id=project.id,
            user_id=user.id,
            event_type="updated",
            summary="用户编辑学习项目配置。",
            payload=data,
        )
    )
    db.commit()
    db.refresh(project)
    return project


def project_home(db: Session, user: User, project_id: int) -> LearningProjectHomeResponse:
    project = get_project_or_404(db, user, project_id)
    project_read = LearningProjectRead.model_validate(project)
    return LearningProjectHomeResponse(
        project=project_read,
        current_stage=project.current_stage,
        today_recommendations=project.today_recommendations,
        recent_classrooms=project.recent_classrooms,
        current_weak_points=project.current_weak_points,
        generated_resource_count=project.generated_resource_count,
        completed_item_count=project.completed_item_count,
        next_step=project.next_step,
        output_checklist=project.output_checklist,
    )


def archive_project(db: Session, user: User, project_id: int) -> LearningProject:
    project = get_project_or_404(db, user, project_id)
    project.status = "archived"
    db.add(LearningProjectEvent(project_id=project.id, user_id=user.id, event_type="archived", summary="用户归档项目。"))
    db.commit()
    db.refresh(project)
    return project


def pause_project(db: Session, user: User, project_id: int) -> LearningProject:
    project = get_project_or_404(db, user, project_id)
    project.status = "paused"
    db.add(LearningProjectEvent(project_id=project.id, user_id=user.id, event_type="paused", summary="用户暂停项目。"))
    db.commit()
    db.refresh(project)
    return project


def resume_project(db: Session, user: User, project_id: int) -> LearningProject:
    project = get_project_or_404(db, user, project_id)
    project.status = "learning"
    db.add(LearningProjectEvent(project_id=project.id, user_id=user.id, event_type="resumed", summary="用户恢复项目。"))
    db.commit()
    db.refresh(project)
    return project


def request_project_syllabus_regeneration(db: Session, user: User, project_id: int) -> LearningProject:
    project = get_project_or_404(db, user, project_id)
    project.status = "needs_replan"
    project.current_stage = "等待重新生成学习清单"
    project.progress = min(project.progress, 10)
    db.add(
        LearningProjectEvent(
            project_id=project.id,
            user_id=user.id,
            event_type="syllabus_regeneration_requested",
            summary="User requested learning checklist regeneration.",
            payload={
                "direction_id": project.direction_id,
                "difficulty": project.difficulty,
                "deadline": project.deadline.isoformat() if project.deadline else None,
            },
        )
    )
    db.commit()
    db.refresh(project)
    return project


def copy_project(db: Session, user: User, project_id: int) -> LearningProject:
    source = get_project_or_404(db, user, project_id)
    copy = LearningProject(
        user_id=user.id,
        direction_id=source.direction_id,
        title=f"{source.title} 副本",
        research_direction=source.research_direction,
        subject=source.subject,
        goal_type=source.goal_type,
        learning_goal=source.learning_goal,
        foundation_summary=source.foundation_summary,
        expected_output=source.expected_output,
        recommended_period=source.recommended_period,
        daily_minutes=source.daily_minutes,
        difficulty=source.difficulty,
        related_course=source.related_course,
        related_knowledge_points=source.related_knowledge_points,
        related_documents=source.related_documents,
        status="draft",
        current_stage=source.current_stage,
        progress=0,
        risk_notes=source.risk_notes,
        personalization_strategy=source.personalization_strategy,
        today_recommendations=source.today_recommendations,
        current_weak_points=source.current_weak_points,
        output_checklist=source.output_checklist,
        next_step=source.next_step,
    )
    db.add(copy)
    db.flush()
    db.add(
        LearningProjectEvent(
            project_id=copy.id,
            user_id=user.id,
            event_type="copied",
            summary="用户复制学习项目。",
            payload={"source_project_id": source.id},
        )
    )
    db.commit()
    db.refresh(copy)
    return copy


def share_project(db: Session, user: User, project_id: int) -> LearningProject:
    project = get_project_or_404(db, user, project_id)
    if not project.shared_token:
        project.shared_token = uuid4().hex
    db.add(
        LearningProjectEvent(
            project_id=project.id,
            user_id=user.id,
            event_type="shared",
            summary="用户生成项目分享令牌。",
        )
    )
    db.commit()
    db.refresh(project)
    return project


def export_project(db: Session, user: User, project_id: int) -> LearningProjectExportResponse:
    project = get_project_or_404(db, user, project_id)
    project_read = LearningProjectRead.model_validate(project)
    markdown = f"""# {project.title}

## 科研方向

{project.research_direction}

## 学习目标

{project.learning_goal}

## 当前基础

{project.foundation_summary}

## 预期产出

{project.expected_output}

## 个性化策略

{chr(10).join(f"- {item}" for item in project.personalization_strategy)}

## 当前薄弱点

{chr(10).join(f"- {item}" for item in project.current_weak_points)}

## 下一步

{project.next_step}
"""
    return LearningProjectExportResponse(project=project_read, markdown=markdown)


def review_direction(
    db: Session,
    reviewer: User,
    direction_id: int,
    request: DirectionReviewRequest,
) -> ResearchDirection:
    direction = db.get(ResearchDirection, direction_id)
    if direction is None:
        raise KeyError("direction not found")
    direction.review_status = request.review_status
    direction.review_notes = request.review_notes
    direction.reviewed_by_user_id = reviewer.id
    direction.reviewed_at = datetime.utcnow()
    direction.status = "ready" if request.review_status == "approved" else direction.status
    db.add(
        ResearchDirectionEvent(
            direction_id=direction.id,
            user_id=reviewer.id,
            event_type="teacher_reviewed",
            summary=f"Direction reviewed as {request.review_status}.",
            payload={"review_notes": request.review_notes},
        )
    )
    db.commit()
    db.refresh(direction)
    return direction


def build_direction_dashboard(db: Session) -> DirectionDashboardResponse:
    seed_direction_templates(db)
    directions = db.scalars(select(ResearchDirection).order_by(ResearchDirection.updated_at.desc())).all()
    projects = db.scalars(select(LearningProject).order_by(LearningProject.updated_at.desc())).all()
    templates = db.scalars(
        select(ResearchDirectionTemplate)
        .where(ResearchDirectionTemplate.is_teacher_recommended.is_(True))
        .order_by(ResearchDirectionTemplate.id)
        .limit(8)
    ).all()

    def count_by(rows: list, attr: str) -> dict[str, int]:
        result: dict[str, int] = {}
        for row in rows:
            key = str(getattr(row, attr) or "unknown")
            result[key] = result.get(key, 0) + 1
        return result

    risk_projects = [
        LearningProjectRead.model_validate(project)
        for project in projects
        if project.risk_notes or project.status in {"paused", "needs_replan"}
    ][:10]
    pending_reviews = [
        ResearchDirectionRead.model_validate(direction)
        for direction in directions
        if direction.review_status in {"pending", "needs_revision"}
    ][:20]
    return DirectionDashboardResponse(
        total_directions=len(directions),
        total_projects=len(projects),
        review_distribution=count_by(directions, "review_status"),
        domain_distribution=count_by(directions, "domain"),
        goal_type_distribution=count_by(directions, "goal_type"),
        project_status_distribution=count_by(projects, "status"),
        risk_projects=risk_projects,
        pending_reviews=pending_reviews,
        recommended_templates=[DirectionTemplateRead.model_validate(template) for template in templates],
    )
