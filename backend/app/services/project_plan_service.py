from __future__ import annotations

import json
import time
from datetime import datetime
from collections.abc import Iterator

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models.learning import AgentTaskRecord, LearningProject, LearningProjectEvent, ProjectPlanSession, ResearchDirection
from app.models.user import User
from app.schemas import (
    LearningProjectRead,
    ProjectPlanAdjustRequest,
    ProjectPlanBuildResponse,
    ProjectPlanRead,
    ProjectPlanRequest,
)
from app.services.direction_service import ProjectSuggestion
from app.services.knowledge_service import COURSE_TITLE, search_knowledge
from app.services.llm_client import qwen_chat_json, qwen_chat_stream_text


class ProjectPlanAgentResult(BaseModel):
    title: str
    summary: str
    learning_type: str
    target_breakdown: list[str]
    key_questions: list[str]
    knowledge_points: list[str]
    resource_plan: list[str]
    milestones: list[str]
    expected_outputs: list[str]
    risk_notes: list[str]
    next_questions: list[str]
    assistant_message: str
    suggested_project: ProjectSuggestion


def _message(role: str, content: str) -> dict:
    return {"role": role, "content": content, "created_at": datetime.utcnow().isoformat()}


def _knowledge_context(db: Session, query: str) -> str:
    hits = search_knowledge(db, query, limit=8)
    if not hits:
        return "No course knowledge matched. Ask the user to confirm source materials that should be added."
    return "\n".join(
        f"- {hit.knowledge_point} / {hit.document_title}: {hit.content} source={hit.source_uri}"
        for hit in hits
    )


def _run_project_plan_agent(
    db: Session,
    learning_type: str,
    learning_goal: str,
    extra_requirements: str,
    messages: list[dict],
    current_plan: dict | None = None,
) -> ProjectPlanAgentResult:
    knowledge_context = _knowledge_context(db, f"{learning_goal}\n{extra_requirements}")
    prompt = _build_project_plan_prompt(
        learning_type,
        learning_goal,
        extra_requirements,
        messages,
        knowledge_context,
        current_plan,
    )
    return qwen_chat_json(
        "你是严谨的高校学习项目规划智能体，只返回合法 JSON。",
        prompt,
        ProjectPlanAgentResult,
    )


def _build_project_plan_prompt(
    learning_type: str,
    learning_goal: str,
    extra_requirements: str,
    messages: list[dict],
    knowledge_context: str,
    current_plan: dict | None = None,
) -> str:
    return f"""
你是高校 AI 个性化学习平台中的 ProjectPlannerAgent。
你的任务是围绕用户的学习目标生成可调整的项目计划，而不是展示用户画像。
只能返回合法 JSON，严格匹配 schema。

学习类型：
{learning_type}

学习目标：
{learning_goal}

补充要求：
{extra_requirements or "无"}

当前课程知识库：
{COURSE_TITLE}

可引用知识来源：
{knowledge_context}

历史对话：
{json.dumps(messages, ensure_ascii=False)}

当前计划草案：
{json.dumps(current_plan or {}, ensure_ascii=False)}

要求：
1. target_breakdown 用 4-7 条拆解用户目标。
2. key_questions 给出还需要澄清的问题，但不能阻止生成计划。
3. milestones 形成用户能理解的学习/项目推进阶段。
4. resource_plan 覆盖文档、例题、实操、可视化、课堂对话等资源类型。
5. suggested_project 必须完整，可直接用于创建 LearningProject。
6. 不要给出预设模板答案，不要声称已完成真实实验或已引用不存在论文。
7. 如果用户要求代写、虚构实验、虚构引用，必须写入 risk_notes 并改成合规学习支持方案。

schema:
{json.dumps(ProjectPlanAgentResult.model_json_schema(mode="validation"), ensure_ascii=False)}
"""


def _stream_prompt_from_json_prompt(json_prompt: str) -> str:
    return f"""
你是高校 AI 个性化学习平台中的 ProjectPlannerAgent。请先用自然语言流式说明你正在如何拆解目标和规划项目。
输出要求：
1. 不要输出 JSON。
2. 用简洁中文分段输出。
3. 说明目标拆解、关键知识点、阶段安排、资源计划、风险边界。
4. 不要声称已完成真实实验或已引用不存在论文。

规划上下文如下：
{json_prompt}
"""


def create_project_plan(db: Session, user: User, request: ProjectPlanRequest) -> ProjectPlanRead:
    messages = [_message("user", f"学习目标：{request.learning_goal}\n补充要求：{request.extra_requirements or '无'}")]
    started = time.perf_counter()
    result = _run_project_plan_agent(
        db,
        request.learning_type,
        request.learning_goal,
        request.extra_requirements,
        messages,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    messages.append(_message("assistant", result.assistant_message))
    session = ProjectPlanSession(
        user_id=user.id,
        learning_type=request.learning_type,
        learning_goal=request.learning_goal,
        extra_requirements=request.extra_requirements,
        title=result.title,
        plan_data=result.model_dump(mode="json"),
        messages=messages,
        status="planning",
    )
    db.add(session)
    db.flush()
    db.add(
        AgentTaskRecord(
            session_id=f"project-plan:{session.id}",
            user_id=user.id,
            agent="ProjectPlannerAgent",
            status="success",
            input_summary=request.learning_goal[:500],
            output_summary=result.summary[:500],
            latency_ms=latency_ms,
        )
    )
    db.commit()
    db.refresh(session)
    return ProjectPlanRead.model_validate(session)


def stream_create_project_plan(db: Session, user: User, request: ProjectPlanRequest) -> Iterator[dict]:
    messages = [_message("user", f"学习目标：{request.learning_goal}\n补充要求：{request.extra_requirements or '无'}")]
    knowledge_context = _knowledge_context(db, f"{request.learning_goal}\n{request.extra_requirements}")
    json_prompt = _build_project_plan_prompt(
        request.learning_type,
        request.learning_goal,
        request.extra_requirements,
        messages,
        knowledge_context,
    )
    stream_prompt = _stream_prompt_from_json_prompt(json_prompt)
    started = time.perf_counter()
    streamed_text = ""

    yield {"event": "start", "data": {"message": "开始生成项目计划"}}
    for token in qwen_chat_stream_text("你是高校学习项目规划智能体。", stream_prompt):
        streamed_text += token
        yield {"event": "token", "data": {"content": token}}

    result = qwen_chat_json(
        "你是严谨的高校学习项目规划智能体，只返回合法 JSON。",
        json_prompt,
        ProjectPlanAgentResult,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    assistant_content = streamed_text.strip() or result.assistant_message
    messages.append(_message("assistant", assistant_content))
    session = ProjectPlanSession(
        user_id=user.id,
        learning_type=request.learning_type,
        learning_goal=request.learning_goal,
        extra_requirements=request.extra_requirements,
        title=result.title,
        plan_data=result.model_dump(mode="json"),
        messages=messages,
        status="planning",
    )
    db.add(session)
    db.flush()
    db.add(
        AgentTaskRecord(
            session_id=f"project-plan:{session.id}",
            user_id=user.id,
            agent="ProjectPlannerAgent",
            status="success",
            input_summary=request.learning_goal[:500],
            output_summary=result.summary[:500],
            latency_ms=latency_ms,
        )
    )
    db.commit()
    db.refresh(session)
    yield {"event": "plan", "data": ProjectPlanRead.model_validate(session).model_dump(mode="json")}
    yield {"event": "done", "data": {"message": "项目计划生成完成"}}


def get_project_plan_or_404(db: Session, user: User, plan_id: int) -> ProjectPlanSession:
    session = db.get(ProjectPlanSession, plan_id)
    if session is None or session.user_id != user.id:
        raise KeyError("project plan not found")
    return session


def adjust_project_plan(
    db: Session,
    user: User,
    plan_id: int,
    request: ProjectPlanAdjustRequest,
) -> ProjectPlanRead:
    session = get_project_plan_or_404(db, user, plan_id)
    if session.status == "built":
        raise ValueError("project plan has already been built")
    messages = [*session.messages, _message("user", request.message)]
    started = time.perf_counter()
    result = _run_project_plan_agent(
        db,
        session.learning_type,
        session.learning_goal,
        session.extra_requirements,
        messages,
        session.plan_data,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    messages.append(_message("assistant", result.assistant_message))
    session.title = result.title
    session.plan_data = result.model_dump(mode="json")
    session.messages = messages
    session.updated_at = datetime.utcnow()
    db.add(
        AgentTaskRecord(
            session_id=f"project-plan:{session.id}",
            user_id=user.id,
            agent="ProjectPlannerAgent",
            status="success",
            input_summary=request.message[:500],
            output_summary=result.summary[:500],
            latency_ms=latency_ms,
        )
    )
    db.commit()
    db.refresh(session)
    return ProjectPlanRead.model_validate(session)


def stream_adjust_project_plan(
    db: Session,
    user: User,
    plan_id: int,
    request: ProjectPlanAdjustRequest,
) -> Iterator[dict]:
    session = get_project_plan_or_404(db, user, plan_id)
    if session.status == "built":
        raise ValueError("project plan has already been built")

    messages = [*session.messages, _message("user", request.message)]
    knowledge_context = _knowledge_context(db, f"{session.learning_goal}\n{session.extra_requirements}\n{request.message}")
    json_prompt = _build_project_plan_prompt(
        session.learning_type,
        session.learning_goal,
        session.extra_requirements,
        messages,
        knowledge_context,
        session.plan_data,
    )
    stream_prompt = _stream_prompt_from_json_prompt(json_prompt)
    started = time.perf_counter()
    streamed_text = ""

    yield {"event": "start", "data": {"message": "开始调整项目计划"}}
    for token in qwen_chat_stream_text("你是高校学习项目规划智能体。", stream_prompt):
        streamed_text += token
        yield {"event": "token", "data": {"content": token}}

    result = qwen_chat_json(
        "你是严谨的高校学习项目规划智能体，只返回合法 JSON。",
        json_prompt,
        ProjectPlanAgentResult,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    messages.append(_message("assistant", streamed_text.strip() or result.assistant_message))
    session.title = result.title
    session.plan_data = result.model_dump(mode="json")
    session.messages = messages
    session.updated_at = datetime.utcnow()
    db.add(
        AgentTaskRecord(
            session_id=f"project-plan:{session.id}",
            user_id=user.id,
            agent="ProjectPlannerAgent",
            status="success",
            input_summary=request.message[:500],
            output_summary=result.summary[:500],
            latency_ms=latency_ms,
        )
    )
    db.commit()
    db.refresh(session)
    yield {"event": "plan", "data": ProjectPlanRead.model_validate(session).model_dump(mode="json")}
    yield {"event": "done", "data": {"message": "项目计划调整完成"}}


def build_project_from_plan(db: Session, user: User, plan_id: int) -> ProjectPlanBuildResponse:
    session = get_project_plan_or_404(db, user, plan_id)
    if session.status == "built" and session.project_id:
        project = db.get(LearningProject, session.project_id)
        if project is None:
            raise KeyError("built project not found")
        return ProjectPlanBuildResponse(
            plan=ProjectPlanRead.model_validate(session),
            project=LearningProjectRead.model_validate(project),
        )

    result = ProjectPlanAgentResult.model_validate(session.plan_data)
    suggestion = result.suggested_project
    direction = ResearchDirection(
        user_id=user.id,
        template_id=None,
        title=result.title,
        normalized_title=result.title,
        domain=suggestion.subject,
        goal_type=session.learning_type,
        description=result.summary,
        raw_input=session.learning_goal,
        extracted_data=result.model_dump(mode="json"),
        clarification_questions=result.key_questions,
        risk_notes=result.risk_notes,
        status="ready",
    )
    db.add(direction)
    db.flush()

    project = LearningProject(
        user_id=user.id,
        direction_id=direction.id,
        title=suggestion.title,
        research_direction=suggestion.research_direction,
        subject=suggestion.subject,
        goal_type=suggestion.goal_type,
        learning_goal=suggestion.learning_goal,
        foundation_summary=suggestion.foundation_summary,
        expected_output=suggestion.expected_output,
        recommended_period=suggestion.recommended_period,
        daily_minutes=suggestion.daily_minutes,
        difficulty=suggestion.difficulty,
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
    session.status = "built"
    session.direction_id = direction.id
    session.project_id = project.id
    session.updated_at = datetime.utcnow()
    db.add(
        LearningProjectEvent(
            project_id=project.id,
            user_id=user.id,
            event_type="created_from_project_plan",
            summary="用户确认项目计划后构建学习项目。",
            payload={"project_plan_id": session.id, "direction_id": direction.id},
        )
    )
    db.commit()
    db.refresh(session)
    db.refresh(project)
    return ProjectPlanBuildResponse(
        plan=ProjectPlanRead.model_validate(session),
        project=LearningProjectRead.model_validate(project),
    )
