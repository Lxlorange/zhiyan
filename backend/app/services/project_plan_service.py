from __future__ import annotations

import json
import time
from datetime import datetime
from collections.abc import Iterator
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.learning import (
    AgentTaskRecord,
    LearningProject,
    LearningProjectEvent,
    ProjectPlanSession,
    ResearchDirection,
    StudentProfileRecord,
)
from app.models.user import User
from app.schemas import (
    LearningProjectRead,
    ProjectPlanAdjustRequest,
    ProjectPlanBuildResponse,
    ProjectPlanRead,
    ProjectPlanRequest,
)
from app.services.direction_service import ProjectSuggestion
from app.services.knowledge_ingestion_service import build_rag_context
from app.services.llm_client import LLMResponseError, qwen_chat_json, qwen_chat_stream_text
from app.services.scholarly_search_service import ScholarlySearchError, verify_candidate_resource_url
from app.services.formula_guidance import FORMULA_OUTPUT_INSTRUCTIONS
from app.services.taxonomy_service import build_knowledge_link_graph


class RecommendedResource(BaseModel):
    title: str
    url: str = ""
    source: str = ""
    reason: str = ""
    verified: bool = False


class ResearchReadingItem(BaseModel):
    level: str = Field(..., pattern="^(foundation|classic|seminal|frontier)$")
    order: int = Field(..., ge=1, le=40)
    title: str
    authors: list[str] = Field(default_factory=list)
    year: str = ""
    venue: str = ""
    arxiv_url: str = ""
    doi_url: str = ""
    source_url: str = ""
    summary: str
    why_read: str
    reading_task: str
    review_focus: list[str] = Field(default_factory=list)


class ResearchTrainingPlan(BaseModel):
    enabled: bool = False
    field_name: str = ""
    reading_levels: list[str] = Field(default_factory=list)
    reading_list: list[ResearchReadingItem] = Field(default_factory=list)
    review_cycle: str = ""
    review_rubric: list[str] = Field(default_factory=list)
    planning_requirements: list[str] = Field(default_factory=list)


class ProjectPlanAgentResult(BaseModel):
    title: str
    summary: str
    learning_type: str
    target_breakdown: list[str]
    key_questions: list[str]
    knowledge_points: list[str]
    resource_plan: list[str]
    recommended_resources: list[RecommendedResource] = Field(default_factory=list)
    milestones: list[str]
    expected_outputs: list[str]
    risk_notes: list[str]
    next_questions: list[str]
    assistant_message: str
    suggested_project: ProjectSuggestion
    research_training: ResearchTrainingPlan = Field(default_factory=ResearchTrainingPlan)
    knowledge_funnel_path: list[dict[str, object]] = Field(default_factory=list)


def _message(role: str, content: str) -> dict:
    return {"role": role, "content": content, "created_at": datetime.utcnow().isoformat()}


def _split_display_and_model_message(message: str) -> tuple[str, str]:
    marker = "\n\n用户上传了以下已解析参考资料。"
    if marker not in message:
        return message, message
    display = message.split(marker, 1)[0].strip()
    return display or message, message


def _knowledge_context(db: Session, query: str) -> str:
    return build_rag_context(db, query, limit=8)


def _path_steps_from_suggestions(suggestions: object, *, limit: int = 12) -> list[dict[str, object]]:
    if not isinstance(suggestions, list) or not suggestions:
        return []
    first = suggestions[0]
    raw_steps = first.get("steps", []) if isinstance(first, dict) else getattr(first, "steps", [])
    if not isinstance(raw_steps, list):
        return []
    steps: list[dict[str, object]] = []
    for index, step in enumerate(raw_steps[:limit], start=1):
        if isinstance(step, dict):
            label = str(step.get("label") or "").strip()
            evidence = step.get("evidence") if isinstance(step.get("evidence"), list) else []
            item = {
                "order": step.get("order") or index,
                "label": label,
                "phase": step.get("phase") or "",
                "estimated_minutes": step.get("estimated_minutes") or 45,
                "reason": step.get("reason") or "",
                "evidence": evidence,
            }
        else:
            label = str(getattr(step, "label", "") or "").strip()
            item = {
                "order": getattr(step, "order", None) or index,
                "label": label,
                "phase": getattr(step, "phase", "") or "",
                "estimated_minutes": getattr(step, "estimated_minutes", None) or 45,
                "reason": getattr(step, "reason", "") or "",
                "evidence": getattr(step, "evidence", None) or [],
            }
        if label:
            steps.append(item)
    return steps


def _knowledge_funnel_context(db: Session, user: User, query: str) -> tuple[str, list[dict[str, object]]]:
    graph = build_knowledge_link_graph(db, user, query=query, limit=80)
    steps = _path_steps_from_suggestions(graph.path_suggestions)
    if not steps:
        return "知识漏斗未命中可用路径；按普通项目规划生成。", []

    lines = [
        "知识漏斗已命中用户 RAG 知识库。课程必须优先沿以下学习路径生成，不能只按模型常识重新排序："
    ]
    for item in steps:
        evidence = "；".join(str(value) for value in (item.get("evidence") or [])[:2])
        lines.append(
            f"{item['order']}. {item['label']} | 阶段={item['phase']} | 建议时长={item['estimated_minutes']} 分钟 | "
            f"理由={item['reason']} | 证据={evidence}"
        )
    lines.extend(
        [
            "",
            "生成要求：",
            "- target_breakdown、milestones、resource_plan、suggested_project.related_knowledge_points 必须覆盖上述路径中的核心节点。",
            "- 如果要生成课程或学习清单，顺序必须遵循 order：先前置节点，再核心节点，再应用/产出节点。",
            "- 如果用户目标与某些路径节点弱相关，可以合并或降权，但不要凭空新增大量未命中的知识点。",
        ]
    )
    return "\n".join(lines), steps

def _profile_context(db: Session, user: User) -> str:
    record = db.scalar(
        select(StudentProfileRecord)
        .where(StudentProfileRecord.user_id == user.id)
        .order_by(desc(StudentProfileRecord.current_revision), desc(StudentProfileRecord.updated_at))
    )
    if record is None:
        return "[]"

    profile_data = dict(record.profile_data or {})
    meta = dict(profile_data.get("_entry_meta") or {})
    entries: list[dict[str, object]] = []
    for key, value in profile_data.items():
        if key == "_entry_meta" or value in (None, "", [], {}):
            continue
        entry_meta = dict(meta.get(key) or {})
        if entry_meta.get("is_enabled", True) is False:
            continue
        entries.append(
            {
                "key": key,
                "value": value,
                "confidence": entry_meta.get("confidence", 70),
                "source": entry_meta.get("source", "memory"),
                "agent": entry_meta.get("agent", "MemoryAgent"),
            }
        )

    return json.dumps(
        {"revision": record.current_revision, "enabled_entries": entries},
        ensure_ascii=False,
    )


def _run_project_plan_agent(
    db: Session,
    user: User,
    learning_type: str,
    learning_goal: str,
    extra_requirements: str,
    messages: list[dict],
    current_plan: Optional[dict] = None,
) -> ProjectPlanAgentResult:
    knowledge_context = _knowledge_context(db, f"{learning_goal}\n{extra_requirements}")
    funnel_context, funnel_steps = _knowledge_funnel_context(db, user, f"{learning_goal}\n{extra_requirements}")
    profile_context = _profile_context(db, user)
    prompt = _build_project_plan_prompt(
        learning_type,
        learning_goal,
        extra_requirements,
        messages,
        knowledge_context,
        funnel_context,
        profile_context,
        current_plan,
    )
    result = qwen_chat_json(
        "你是严谨的高校学习项目规划智能体，只返回合法 JSON。",
        prompt,
        ProjectPlanAgentResult,
        user=user,
    )
    result = _verify_recommended_resources(result, learning_goal)
    result = _apply_funnel_path_to_plan(result, funnel_steps)
    return _verify_research_training(result, learning_type, learning_goal)


def _build_project_plan_prompt(
    learning_type: str,
    learning_goal: str,
    extra_requirements: str,
    messages: list[dict],
    knowledge_context: str,
    funnel_context: str,
    profile_context: str,
    current_plan: Optional[dict] = None,
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

当前知识来源约束：
仅允许使用用户本次输入、上传附件、已入库知识库和检索到的真实来源；如果资料不足，必须写入 risk_notes 或 next_questions，不得补写固定课程内容。

可引用知识来源：
{knowledge_context}

知识漏斗路径约束：
{funnel_context}

用户学习画像上下文：
{profile_context}

画像使用约束：
1. 画像只作为个性化生成依据，不要在 assistant_message、summary、recommended_resources 或前台可见内容中展示“用户画像上下文”原文。
2. 根据 learning_pace、practice_level、daily_minutes 等条目调整阶段粒度、每日学习压力和复盘频率。
3. 根据 resource_preference、cognitive_style 调整 PPT、例题、可视化、实操、论文阅读、互动提问的比例。
4. 根据 weak_points、mastery、question_habit 增加必要前置补课、错题复练和检查点。
5. 根据 output_goal、academic_writing、literature_reading、coding_practice、experiment_design 调整最终产出和验收标准。
6. 只使用已启用画像条目；不要推断或编造画像中没有的稳定习惯。

知识库使用约束：
1. 涉及课程内容、实验方法、论文写作规范、习题解析时，优先引用上方知识库来源。
2. recommended_resources 中如使用知识库资料，source 必须写明文档标题、页码或幻灯片编号。
3. 不得声称知识库没有出现的课件内容已经存在；缺少来源时写入 risk_notes 或 next_questions。
4. 如果“知识漏斗路径约束”中给出了路径，milestones 和 suggested_project.related_knowledge_points 必须按该路径的先后顺序组织课程，而不是按 PPT 页码或通用目录重排。

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
{FORMULA_OUTPUT_INSTRUCTIONS}

8. recommended_resources 必须返回资源对象列表，每项包含 title、url、source、reason；url 必须是你确信真实存在且与学习目标直接相关的 http/https 链接，例如官方文档、课程主页、arXiv/DOI/Semantic Scholar/OpenAlex、教材官网、权威教程或用户上传/知识库来源。不得只给资源标题让后端猜链接，不得编造 DOI、论文链接或官网链接；没有可靠链接时不要放入 recommended_resources，改写入 risk_notes。
9. 对通用技能学习目标优先推荐官方文档、权威教程、课程主页和实践项目；只有用户明确要求论文、综述、科研选题、实验或引用时，才推荐论文数据库链接。
10. 当 learning_type 为 research_project 时，必须启用 research_training.enabled=true，并返回四级阅读清单：
    - foundation：基础论文/教程
    - classic：领域经典论文
    - seminal：开山论文
    - frontier：科研前沿论文
    每一级至少 1 篇，总数 4-12 篇；每篇必须包含阅读顺序 order、摘要 summary、阅读原因 why_read、复盘任务 reading_task。
    每篇论文必须尽量提供 arxiv_url、doi_url 或 source_url 之一；链接必须是 http/https，不能编造 DOI 或 arXiv。
    research_training.review_rubric 必须包含详实程度、关联度、工作量、规划性、批判性思考五个维度。
    planning_requirements 必须要求学生按周期提交“论文复盘总结 + 下一步计划”。
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
{FORMULA_OUTPUT_INSTRUCTIONS}

规划上下文如下：
{json_prompt}
"""


def create_project_plan(db: Session, user: User, request: ProjectPlanRequest) -> ProjectPlanRead:
    messages = [_message("user", request.learning_goal)]
    started = time.perf_counter()
    result = _run_project_plan_agent(
        db,
        user,
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
    messages = [_message("user", request.learning_goal)]
    knowledge_context = _knowledge_context(db, f"{request.learning_goal}\n{request.extra_requirements}")
    funnel_context, funnel_steps = _knowledge_funnel_context(db, user, f"{request.learning_goal}\n{request.extra_requirements}")
    profile_context = _profile_context(db, user)
    json_prompt = _build_project_plan_prompt(
        request.learning_type,
        request.learning_goal,
        request.extra_requirements,
        messages,
        knowledge_context,
        funnel_context,
        profile_context,
    )
    stream_prompt = _stream_prompt_from_json_prompt(json_prompt)
    started = time.perf_counter()
    streamed_text = ""

    yield {"event": "start", "data": {"message": "开始生成项目计划"}}
    for token in qwen_chat_stream_text("你是高校学习项目规划智能体。", stream_prompt, user=user):
        streamed_text += token
        yield {"event": "token", "data": {"content": token}}

    result = qwen_chat_json(
        "你是严谨的高校学习项目规划智能体，只返回合法 JSON。",
        json_prompt,
        ProjectPlanAgentResult,
        user=user,
    )
    result = _verify_recommended_resources(result, request.learning_goal)
    result = _apply_funnel_path_to_plan(result, funnel_steps)
    result = _verify_research_training(result, request.learning_type, request.learning_goal)
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
    display_message, model_message = _split_display_and_model_message(request.message)
    messages = [*session.messages, _message("user", display_message)]
    started = time.perf_counter()
    result = _run_project_plan_agent(
        db,
        user,
        session.learning_type,
        session.learning_goal,
        session.extra_requirements,
        [*session.messages, _message("user", model_message)],
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
            input_summary=display_message[:500],
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

    display_message, model_message = _split_display_and_model_message(request.message)
    messages = [*session.messages, _message("user", display_message)]
    model_messages = [*session.messages, _message("user", model_message)]
    knowledge_context = _knowledge_context(db, f"{session.learning_goal}\n{session.extra_requirements}\n{model_message}")
    funnel_context, funnel_steps = _knowledge_funnel_context(
        db,
        user,
        f"{session.learning_goal}\n{session.extra_requirements}\n{model_message}",
    )
    profile_context = _profile_context(db, user)
    json_prompt = _build_project_plan_prompt(
        session.learning_type,
        session.learning_goal,
        session.extra_requirements,
        model_messages,
        knowledge_context,
        funnel_context,
        profile_context,
        session.plan_data,
    )
    stream_prompt = _stream_prompt_from_json_prompt(json_prompt)
    started = time.perf_counter()
    streamed_text = ""

    yield {"event": "start", "data": {"message": "开始调整项目计划"}}
    for token in qwen_chat_stream_text("你是高校学习项目规划智能体。", stream_prompt, user=user):
        streamed_text += token
        yield {"event": "token", "data": {"content": token}}

    result = qwen_chat_json(
        "你是严谨的高校学习项目规划智能体，只返回合法 JSON。",
        json_prompt,
        ProjectPlanAgentResult,
        user=user,
    )
    result = _verify_recommended_resources(result, session.learning_goal)
    result = _apply_funnel_path_to_plan(result, funnel_steps)
    result = _verify_research_training(result, session.learning_type, session.learning_goal)
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
            input_summary=display_message[:500],
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
    funnel_path = _funnel_path_from_plan_data(session.plan_data)
    related_points = _merge_ordered(
        [str(item.get("label") or "") for item in funnel_path],
        list(suggestion.related_knowledge_points or []),
    )
    research_training = result.research_training.model_dump(mode="json")
    if funnel_path:
        research_training["knowledge_funnel_path"] = funnel_path
        research_training["path_generation_method"] = "knowledge_funnel_rag"
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
        study_weekends=False,
        study_weekdays=[0, 1, 2, 3, 4],
        difficulty=suggestion.difficulty,
        related_course=suggestion.related_course,
        related_knowledge_points=related_points,
        related_documents=suggestion.related_documents,
        research_training=research_training,
        status="resources_queued",
        current_stage="项目资源准备中",
        risk_notes=suggestion.risk_notes,
        personalization_strategy=suggestion.personalization_strategy,
        today_recommendations=suggestion.today_recommendations,
        current_weak_points=suggestion.current_weak_points,
        output_checklist=suggestion.output_checklist,
        next_step="系统正在后台生成学习清单和课堂资源，完成后可从项目主页进入学习清单开始学习。",
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


def _apply_funnel_path_to_plan(result: ProjectPlanAgentResult, funnel_steps: list[dict[str, object]]) -> ProjectPlanAgentResult:
    if not funnel_steps:
        return result
    ordered_labels = [str(step.get("label") or "").strip() for step in funnel_steps if str(step.get("label") or "").strip()]
    result.suggested_project.related_knowledge_points = _merge_ordered(
        ordered_labels,
        list(result.suggested_project.related_knowledge_points or []),
    )[:18]
    plan_data = result.model_dump(mode="json")
    plan_data["knowledge_funnel_path"] = funnel_steps
    result = ProjectPlanAgentResult.model_validate(plan_data)
    result.assistant_message = (
        result.assistant_message
        + "\n\n已命中知识库资料，我会按知识漏斗的先修路径组织课程："
        + " -> ".join(ordered_labels[:8])
    )
    return result


def _funnel_path_from_plan_data(plan_data: object) -> list[dict[str, object]]:
    if not isinstance(plan_data, dict):
        return []
    raw = plan_data.get("knowledge_funnel_path")
    if not isinstance(raw, list):
        return []
    result: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        result.append(
            {
                "order": int(item.get("order") or len(result) + 1),
                "label": label,
                "phase": str(item.get("phase") or ""),
                "estimated_minutes": int(item.get("estimated_minutes") or 45),
                "reason": str(item.get("reason") or ""),
                "evidence": [str(value) for value in item.get("evidence", []) if str(value).strip()]
                if isinstance(item.get("evidence"), list)
                else [],
            }
        )
    return result


def _merge_ordered(primary: list[str], secondary: list[str]) -> list[str]:
    result: list[str] = []
    for value in [*primary, *secondary]:
        text = str(value or "").strip()
        if text and text not in result:
            result.append(text)
    return result


def _verify_recommended_resources(result: ProjectPlanAgentResult, learning_goal: str) -> ProjectPlanAgentResult:
    verified: list[RecommendedResource] = []
    risk_notes = list(result.risk_notes)
    for resource in result.recommended_resources[:8]:
        if not resource.url:
            risk_notes.append(f"推荐资源「{resource.title}」没有提供可验证链接，已从前台推荐列表移除。")
            continue
        try:
            hit = verify_candidate_resource_url(
                title=resource.title,
                url=resource.url,
                topic=learning_goal,
                source=resource.source,
                reason=resource.reason,
            )
        except ScholarlySearchError as exc:
            risk_notes.append(f"推荐资源「{resource.title}」链接验证失败：{exc}")
            continue
        if hit is None:
            risk_notes.append(f"推荐资源「{resource.title}」未通过可达性或主题相关性验证，已从前台推荐列表移除。")
            continue
        verified.append(
            RecommendedResource(
                title=hit.title,
                url=hit.url,
                source=hit.source,
                reason=hit.reason,
                verified=True,
            )
        )
    if not verified:
        risk_notes.append(
            "推荐资源未产生可打开且主题相关的真实链接；前台不会展示未经验证的资源。"
            "请在对话中要求 Agent 提供官方文档、课程主页、论文 DOI/arXiv 或教材官网等明确 URL。"
        )
    result.recommended_resources = verified
    result.risk_notes = risk_notes
    return result


def _verify_research_training(
    result: ProjectPlanAgentResult,
    learning_type: str,
    learning_goal: str,
) -> ProjectPlanAgentResult:
    if learning_type != "research_project":
        result.research_training.enabled = False
        return result

    training = result.research_training
    if not training.enabled:
        raise LLMResponseError("科研项目必须返回 research_training.enabled=true")

    required_levels = {"foundation", "classic", "seminal", "frontier"}
    items_by_level: dict[str, list[ResearchReadingItem]] = {level: [] for level in required_levels}
    verified_items: list[ResearchReadingItem] = []
    risk_notes = list(result.risk_notes)

    for item in sorted(training.reading_list, key=lambda value: value.order):
        url = _reading_item_url(item)
        if not url:
            risk_notes.append(f"论文阅读项「{item.title}」缺少 arXiv、DOI 或真实来源链接，已从阅读清单移除。")
            continue
        if not _is_http_url(url):
            risk_notes.append(f"论文阅读项「{item.title}」链接格式非法：{url}，已从阅读清单移除。")
            continue
        try:
            hit = verify_candidate_resource_url(title=item.title, url=url, topic=learning_goal)
        except ScholarlySearchError as exc:
            raise LLMResponseError(f"无法验证科研阅读清单链接：{exc}") from exc
        if hit is None:
            risk_notes.append(f"论文阅读项「{item.title}」链接未通过主题相关性校验，已从阅读清单移除：{url}")
            continue
        item.source_url = hit.url
        if not item.arxiv_url and "arxiv.org" in hit.url:
            item.arxiv_url = hit.url
        if not item.doi_url and ("doi.org" in hit.url or "dx.doi.org" in hit.url):
            item.doi_url = hit.url
        verified_items.append(item)
        items_by_level[item.level].append(item)

    missing_levels = [level for level, items in items_by_level.items() if not items]
    if missing_levels:
        raise LLMResponseError(f"科研项目四级阅读清单缺少可验证链接的层级：{', '.join(missing_levels)}")

    required_rubric = {"详实程度", "关联度", "工作量", "规划性", "批判性思考"}
    if not required_rubric.issubset(set(training.review_rubric)):
        training.review_rubric = ["详实程度", "关联度", "工作量", "规划性", "批判性思考"]

    training.reading_levels = ["foundation", "classic", "seminal", "frontier"]
    training.reading_list = verified_items[:12]
    if not training.review_cycle:
        training.review_cycle = "每 3-7 天提交一篇论文复盘总结与下一步计划。"
    if not training.planning_requirements:
        training.planning_requirements = ["每篇论文复盘必须包含核心问题、方法、证据、局限、与本人选题的关系、下一步计划。"]

    result.research_training = training
    result.risk_notes = risk_notes
    result.recommended_resources = _merge_reading_resources(result.recommended_resources, verified_items)
    return result


def _reading_item_url(item: ResearchReadingItem) -> str:
    return item.arxiv_url or item.doi_url or item.source_url


def _is_http_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _merge_reading_resources(resources: list[RecommendedResource], readings: list[ResearchReadingItem]) -> list[RecommendedResource]:
    existing = {resource.url for resource in resources if resource.url}
    merged = list(resources)
    for reading in readings:
        url = _reading_item_url(reading)
        if not url or url in existing:
            continue
        merged.append(
            RecommendedResource(
                title=reading.title,
                url=url,
                source=reading.level,
                reason=reading.why_read,
                verified=True,
            )
        )
        existing.add(url)
    return merged[:12]

