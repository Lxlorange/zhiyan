from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.models.learning import (
    AgentTaskRecord,
    ClassroomResource,
    ClassroomSubmission,
    LearningProject,
    LiteraturePaper,
    ResearchToolRun,
    StudentProfileRecord,
    StudentProfileVersion,
)
from app.models.user import User
from app.schemas import (
    AgentTrace,
    LiteraturePaperCreateRequest,
    LiteraturePaperRead,
    LiteraturePaperUpdateRequest,
    PracticeGenerateRequest,
    PracticeGenerateResponse,
    PracticeQuestionRead,
    ProfileCenterResponse,
    ProfileEntryRead,
    ProfileEntryUpdateRequest,
    ProfileVersionRead,
    ResearchToolRunRead,
    ResearchToolRunRequest,
    WorkspaceOverviewResponse,
)
from app.services.llm_client import LLMConfigurationError, LLMResponseError, qwen_chat_json
from app.services.knowledge_service import search_knowledge


PROFILE_ENTRY_LABELS: dict[str, str] = {
    "knowledge_base": "知识基础",
    "learning_goal": "学习目标",
    "cognitive_style": "认知风格",
    "weak_points": "易错点",
    "practice_level": "实践能力",
    "resource_preference": "资源偏好",
    "learning_pace": "学习节奏",
    "interest_direction": "兴趣方向",
    "current_research_direction": "当前科研方向",
    "mastery": "掌握度分布",
    "question_habit": "提问习惯",
    "output_goal": "产出目标",
    "academic_writing": "学术写作能力",
    "literature_reading": "文献阅读能力",
    "coding_practice": "代码实践能力",
    "experiment_design": "实验设计能力",
}


class _ResearchToolOutput(BaseModel):
    title: str
    revised_text: str = ""
    diagnosis: list[str] = Field(default_factory=list)
    structure_suggestions: list[str] = Field(default_factory=list)
    citation_suggestions: list[str] = Field(default_factory=list)
    method_steps: list[str] = Field(default_factory=list)
    topic_options: list[str] = Field(default_factory=list)
    final_topic: str = ""
    experiment_plan: list[str] = Field(default_factory=list)
    defense_questions: list[dict[str, Any]] = Field(default_factory=list)
    scoring_rubric: list[str] = Field(default_factory=list)
    source_notes: list[str] = Field(default_factory=list)
    safety_notes: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class _PracticeQuestionLLM(BaseModel):
    questions: list[PracticeQuestionRead] = Field(default_factory=list)
    source_summary: str = ""


def get_workspace_overview(db: Session, user: User) -> WorkspaceOverviewResponse:
    projects = list(
        db.scalars(
            select(LearningProject)
            .where(LearningProject.user_id == user.id)
            .order_by(desc(LearningProject.updated_at))
            .limit(12)
        )
    )
    resources = list(
        db.scalars(
            select(ClassroomResource)
            .where(ClassroomResource.user_id == user.id)
            .order_by(desc(ClassroomResource.created_at))
            .limit(30)
        )
    )
    tasks = list(
        db.scalars(
            select(AgentTaskRecord)
            .where(AgentTaskRecord.user_id == user.id)
            .order_by(desc(AgentTaskRecord.created_at))
            .limit(40)
        )
    )
    submissions = list(
        db.scalars(
            select(ClassroomSubmission)
            .where(ClassroomSubmission.user_id == user.id)
            .order_by(desc(ClassroomSubmission.created_at))
            .limit(30)
        )
    )
    literature = list_literature(db, user)
    tool_runs = list_tool_runs(db, user)
    profile = get_profile_center(db, user)
    return WorkspaceOverviewResponse(
        projects=projects,
        profile=profile,
        resources=resources,
        agent_tasks=[
            AgentTrace(
                agent=task.agent,
                status=task.status,
                input_summary=task.input_summary,
                output_summary=task.output_summary,
                latency_ms=task.latency_ms,
            )
            for task in tasks
        ],
        submissions=submissions,
        literature=literature,
        tool_runs=tool_runs,
        metrics={
            "projects": len(projects),
            "resources": len(resources),
            "agent_tasks": len(tasks),
            "submissions": len(submissions),
            "literature": len(literature),
            "tool_runs": len(tool_runs),
        },
    )


def get_profile_center(db: Session, user: User) -> ProfileCenterResponse:
    record = db.scalar(
        select(StudentProfileRecord)
        .options(selectinload(StudentProfileRecord.versions))
        .where(StudentProfileRecord.user_id == user.id)
        .order_by(desc(StudentProfileRecord.updated_at))
    )
    if record is None:
        return ProfileCenterResponse(
            entries=[],
            recommendations=[
                "先在学习画像页用自然语言描述专业、目标、基础和偏好。",
                "完成课堂例题、实操和复盘后，系统会逐步积累画像版本。",
            ]
        )
    profile_data = record.profile_data or {}
    weak_points = profile_data.get("weak_points") or []
    preferences = profile_data.get("resource_preference") or []
    recommendations = [
        f"优先补齐薄弱点：{', '.join(map(str, weak_points[:3]))}" if weak_points else "继续通过课堂复盘积累薄弱点证据。",
        f"生成资源时优先使用：{', '.join(map(str, preferences[:3]))}" if preferences else "建议补充资源偏好，便于个性化推荐。",
    ]
    return ProfileCenterResponse(
        profile_id=record.id,
        current_revision=record.current_revision,
        profile_data=profile_data,
        entries=_build_profile_entries(record),
        versions=[
            ProfileVersionRead.model_validate(version)
            for version in sorted(record.versions, key=lambda item: item.revision, reverse=True)[:10]
        ],
        recommendations=recommendations,
    )


def update_profile_entry(
    db: Session,
    user: User,
    request: ProfileEntryUpdateRequest,
) -> ProfileCenterResponse:
    record = db.scalar(
        select(StudentProfileRecord)
        .options(selectinload(StudentProfileRecord.versions))
        .where(StudentProfileRecord.user_id == user.id)
        .order_by(desc(StudentProfileRecord.updated_at))
    )
    if record is None:
        record = StudentProfileRecord(user_id=user.id, current_revision=0, profile_data={})
        db.add(record)
        db.flush()

    profile_data = dict(record.profile_data or {})
    meta = dict(profile_data.get("_entry_meta") or {})
    if request.value in (None, "", [], {}):
        profile_data.pop(request.key, None)
    else:
        profile_data[request.key] = request.value

    meta[request.key] = {
        "confidence": request.confidence,
        "source": request.source,
        "source_object_id": request.source_object_id,
        "agent": "MemoryAgent",
        "is_confirmed": request.is_confirmed,
        "is_enabled": request.is_enabled,
        "updated_at": datetime.utcnow().isoformat(),
    }
    profile_data["_entry_meta"] = meta

    record.current_revision += 1
    record.profile_data = profile_data
    record.updated_at = datetime.utcnow()
    db.add(
        StudentProfileVersion(
            profile_id=record.id,
            revision=record.current_revision,
            source=request.source,
            update_reason=request.update_reason,
            extracted_features={
                "key": request.key,
                "value": request.value,
                "confidence": request.confidence,
                "is_enabled": request.is_enabled,
            },
            profile_data=profile_data,
        )
    )
    db.add(
        AgentTaskRecord(
            session_id=f"profile-entry-{user.id}",
            user_id=user.id,
            agent="MemoryAgent",
            status="completed",
            input_summary=f"更新画像条目：{PROFILE_ENTRY_LABELS.get(request.key, request.key)}",
            output_summary=request.update_reason,
            latency_ms=0,
        )
    )
    db.commit()
    db.refresh(record)
    return get_profile_center(db, user)


def _build_profile_entries(record: StudentProfileRecord) -> list[ProfileEntryRead]:
    profile_data = record.profile_data or {}
    meta = profile_data.get("_entry_meta") or {}
    entries: list[ProfileEntryRead] = []
    for key, label in PROFILE_ENTRY_LABELS.items():
        value = profile_data.get(key)
        entry_meta = meta.get(key) or {}
        if value in (None, "", [], {}) and not entry_meta:
            continue
        updated_at = _parse_datetime(entry_meta.get("updated_at")) or record.updated_at
        entries.append(
            ProfileEntryRead(
                key=key,
                label=label,
                value=value,
                confidence=int(entry_meta.get("confidence", 70)),
                source=str(entry_meta.get("source", "dialogue")),
                source_object_id=entry_meta.get("source_object_id"),
                agent=str(entry_meta.get("agent", "ProfileAgent")),
                is_confirmed=bool(entry_meta.get("is_confirmed", False)),
                is_enabled=bool(entry_meta.get("is_enabled", True)),
                revision=record.current_revision,
                updated_at=updated_at,
            )
        )
    return entries


def list_literature(db: Session, user: User) -> list[LiteraturePaperRead]:
    papers = db.scalars(
        select(LiteraturePaper)
        .where(LiteraturePaper.user_id == user.id)
        .order_by(desc(LiteraturePaper.updated_at))
        .limit(100)
    )
    return [LiteraturePaperRead.model_validate(paper) for paper in papers]


def create_literature(db: Session, user: User, request: LiteraturePaperCreateRequest) -> LiteraturePaperRead:
    paper = LiteraturePaper(
        user_id=user.id,
        project_id=request.project_id,
        title=request.title,
        authors=request.authors,
        venue=request.venue,
        year=request.year,
        source_uri=request.source_uri,
        abstract=request.abstract,
        keywords=request.keywords,
        reading_status=request.reading_status,
        notes=request.notes,
        citation_text=_build_citation_text(request.title, request.authors, request.venue, request.year),
    )
    db.add(paper)
    db.commit()
    db.refresh(paper)
    return LiteraturePaperRead.model_validate(paper)


def update_literature(db: Session, user: User, paper_id: int, request: LiteraturePaperUpdateRequest) -> LiteraturePaperRead:
    paper = db.scalar(select(LiteraturePaper).where(LiteraturePaper.id == paper_id, LiteraturePaper.user_id == user.id))
    if paper is None:
        raise KeyError("literature paper not found")
    updates = request.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(paper, key, value)
    paper.citation_text = _build_citation_text(paper.title, paper.authors, paper.venue, paper.year)
    paper.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(paper)
    return LiteraturePaperRead.model_validate(paper)


def list_tool_runs(db: Session, user: User) -> list[ResearchToolRunRead]:
    runs = db.scalars(
        select(ResearchToolRun)
        .where(ResearchToolRun.user_id == user.id)
        .order_by(desc(ResearchToolRun.created_at))
        .limit(80)
    )
    return [ResearchToolRunRead.model_validate(run) for run in runs]


def run_research_tool(db: Session, user: User, request: ResearchToolRunRequest) -> ResearchToolRunRead:
    source_context = _research_source_context(db, user, request)
    system_prompt = (
        "你是高校科研学习平台的 ResearchToolAgent。"
        "请严格输出 JSON，帮助学生完成选题凝练、文献综述、实验设计、论文写作、复现规划和模拟答辩。"
        "必须优先使用 source_context 中给出的来源；不要编造不存在的论文、数据或实验结果；需要提示用户补充来源时写入 safety_notes。"
    )
    user_prompt = (
        f"工具类型：{request.tool_type}\n"
        f"输入内容：{request.input_text}\n"
        f"补充要求：{request.extra_requirement}\n"
        f"source_context:\n{source_context}\n\n"
        "工具行为要求："
        "topic 输出 3-5 个可行选题、最终具体选题、依据、风险和下一步；"
        "paper_reading/review 输出论文摘要矩阵、研究脉络、方法对比、局限性和带来源的综述段落建议；"
        "experiment 输出技术路线、数据采集方案、评价指标、实验变量、图表规范建议和阶段计划；"
        "defense 输出开题/中期/答辩问题、追问、参考回答要点、评分量表和修改建议。"
        "输出字段：title, revised_text, diagnosis, structure_suggestions, citation_suggestions, method_steps, "
        "topic_options, final_topic, experiment_plan, defense_questions, scoring_rubric, source_notes, safety_notes, next_actions。"
    )
    output = qwen_chat_json(system_prompt, user_prompt, _ResearchToolOutput)
    run = ResearchToolRun(
        user_id=user.id,
        project_id=request.project_id,
        tool_type=request.tool_type,
        title=output.title,
        input_text=request.input_text,
        output_data=output.model_dump(),
        agent_trace=[
            {
                "agent": "ResearchToolAgent",
                "status": "completed",
                "input_summary": request.input_text[:300],
                "output_summary": output.title,
                "latency_ms": 0,
            },
            {
                "agent": "SafetyAgent",
                "status": "completed",
                "input_summary": "检查是否存在无来源事实、过度承诺和引用风险",
                "output_summary": "已生成 safety_notes",
                "latency_ms": 0,
            },
        ],
        status="completed",
    )
    db.add(run)
    db.add(
        AgentTaskRecord(
            session_id=f"research-tool-{user.id}",
            user_id=user.id,
            agent="ResearchToolAgent",
            status="completed",
            input_summary=request.input_text[:300],
            output_summary=output.title,
            latency_ms=0,
        )
    )
    db.commit()
    db.refresh(run)
    return ResearchToolRunRead.model_validate(run)


def generate_practice_questions(
    db: Session,
    user: User,
    request: PracticeGenerateRequest,
) -> PracticeGenerateResponse:
    points = _practice_points(db, user, request)
    source_context = _practice_source_context(db, user, points, request.project_id)
    if not points:
        points = ["核心概念理解"]

    try:
        output = _generate_practice_with_llm(points, source_context, request)
        questions = output.questions[: max(1, len(points) * request.count_per_point * len(request.question_types))]
        if questions:
            return PracticeGenerateResponse(
                questions=questions,
                used_llm=True,
                source_summary=output.source_summary or _source_summary(source_context),
            )
    except (LLMConfigurationError, LLMResponseError):
        pass

    return PracticeGenerateResponse(
        questions=_fallback_practice_questions(points, source_context, request),
        used_llm=False,
        source_summary=_source_summary(source_context),
    )


def _practice_points(db: Session, user: User, request: PracticeGenerateRequest) -> list[str]:
    points = [str(point).strip() for point in request.weak_points if str(point).strip()]
    if points:
        return list(dict.fromkeys(points))[:12]
    profile = get_profile_center(db, user)
    for entry in profile.entries:
        if entry.key == "weak_points":
            raw = entry.value
            if isinstance(raw, list):
                points.extend(str(item).strip() for item in raw)
            else:
                points.extend(part.strip() for part in str(raw or "").replace("，", ",").split(","))
    return [point for point in dict.fromkeys(points) if point][:12]


def _practice_source_context(db: Session, user: User, points: list[str], project_id: int | None) -> list[dict[str, Any]]:
    query = " ".join(points) or "练习 题目 薄弱点"
    hits = [hit.model_dump(mode="json") for hit in search_knowledge(db, query, limit=10)]
    if project_id:
        project = db.get(LearningProject, project_id)
        if project is not None and project.user_id == user.id:
            hits.insert(
                0,
                {
                    "document_title": project.title,
                    "document_type": "learning_project",
                    "knowledge_point": "项目目标",
                    "content": f"{project.learning_goal}\n{project.foundation_summary}\n{project.expected_output}",
                    "source_uri": f"project:{project.id}",
                },
            )
    return hits[:12]


def _generate_practice_with_llm(
    points: list[str],
    source_context: list[dict[str, Any]],
    request: PracticeGenerateRequest,
) -> _PracticeQuestionLLM:
    context = "\n\n".join(
        f"[{index}] {item.get('document_title', '')} / {item.get('knowledge_point', '')}\n{item.get('content', '')}"
        for index, item in enumerate(source_context, start=1)
    )
    prompt = f"""
请基于学生薄弱点和资料库片段生成练习题，只输出 JSON。

薄弱点：{points}
题型：{request.question_types}
难度：{request.difficulty}
每个薄弱点每种题型数量：{request.count_per_point}

资料库片段：
{context}

要求：
1. questions 中每题包含 id、type、point、prompt、options、answer、explanation、source_title、source_excerpt、difficulty。
2. type 使用 choice、judgement、short 三类之一；选择题必须给 4 个 options。
3. 题目必须贴合资料库片段或项目目标；资料不足时用基础概念题，但 explanation 说明需要补充资料。
4. source_excerpt 保留不超过 120 字。
5. source_summary 概括本次题目依据。
"""
    return qwen_chat_json(
        "你是高校个性化学习系统的练习题生成 Agent，负责把画像薄弱点和资料库证据转成可练习题目。",
        prompt,
        _PracticeQuestionLLM,
    )


def _fallback_practice_questions(
    points: list[str],
    source_context: list[dict[str, Any]],
    request: PracticeGenerateRequest,
) -> list[PracticeQuestionRead]:
    question_types = request.question_types or ["choice"]
    questions: list[PracticeQuestionRead] = []
    source_by_point = _source_by_point(source_context)
    for point_index, point in enumerate(points):
        source = source_by_point.get(point) or (source_context[point_index % len(source_context)] if source_context else {})
        source_title = str(source.get("document_title") or "当前学习资料")
        source_excerpt = str(source.get("content") or "")[:160]
        for type_index, question_type in enumerate(question_types):
            for count_index in range(request.count_per_point):
                question_id = f"{point_index + 1}-{question_type}-{count_index + 1}"
                if question_type == "judgement":
                    questions.append(
                        PracticeQuestionRead(
                            id=question_id,
                            type="judgement",
                            point=point,
                            prompt=f"判断：学习「{point}」时，只记住定义就足够，不需要结合资料或项目场景验证。",
                            answer="错误",
                            explanation=f"「{point}」需要结合概念、资料证据和应用边界一起理解。",
                            source_title=source_title,
                            source_excerpt=source_excerpt,
                            difficulty=request.difficulty,
                        )
                    )
                elif question_type == "short":
                    questions.append(
                        PracticeQuestionRead(
                            id=question_id,
                            type="short",
                            point=point,
                            prompt=f"请用 3-5 句话说明「{point}」的核心含义，并写出一个你还需要继续查证的问题。",
                            answer="参考答案应包含概念解释、适用场景、易错点和下一步查证问题。",
                            explanation="简答题用于暴露理解缺口，便于后续更新学习画像。",
                            source_title=source_title,
                            source_excerpt=source_excerpt,
                            difficulty=request.difficulty,
                        )
                    )
                else:
                    questions.append(
                        PracticeQuestionRead(
                            id=question_id,
                            type="choice",
                            point=point,
                            prompt=f"围绕「{point}」，下列哪一项最能体现该知识点在学习项目中的正确使用？",
                            options=[
                                f"先说明 {point} 的概念，再结合资料或案例验证",
                                "直接套用结论，不说明适用条件",
                                "只给最终答案，不记录推理过程",
                                "忽略数据来源和实验边界",
                            ],
                            answer=f"先说明 {point} 的概念，再结合资料或案例验证",
                            explanation="正确使用知识点需要概念、证据和边界条件同时成立。",
                            source_title=source_title,
                            source_excerpt=source_excerpt,
                            difficulty=request.difficulty,
                        )
                    )
    return questions


def _source_by_point(source_context: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in source_context:
        point = str(item.get("knowledge_point") or "")
        if point and point not in result:
            result[point] = item
    return result


def _source_summary(source_context: list[dict[str, Any]]) -> str:
    if not source_context:
        return "未检索到资料库片段，已基于画像薄弱点生成基础练习。"
    titles = [str(item.get("document_title") or "资料片段") for item in source_context[:3]]
    return f"已参考 {len(source_context)} 个资料片段：{'、'.join(titles)}。"


def _research_source_context(db: Session, user: User, request: ResearchToolRunRequest) -> str:
    query = f"{request.input_text} {request.extra_requirement}"
    hits = search_knowledge(db, query, limit=8)
    filters = [LiteraturePaper.user_id == user.id]
    if request.project_id:
        filters.append(LiteraturePaper.project_id == request.project_id)
    papers = list(
        db.scalars(
            select(LiteraturePaper)
            .where(*filters)
            .order_by(desc(LiteraturePaper.updated_at))
            .limit(12)
        )
    )
    knowledge_lines = [
        f"- knowledge: {hit.document_title} [{hit.document_type}] {hit.content} source={hit.source_uri}"
        for hit in hits
    ]
    paper_lines = [
        f"- literature: {paper.title}; authors={paper.authors}; venue={paper.venue}; year={paper.year}; "
        f"abstract={paper.abstract[:800]}; source={paper.source_uri or paper.citation_text}"
        for paper in papers
    ]
    if not knowledge_lines and not paper_lines:
        return "暂无可用来源。回答必须明确提示用户先补充论文、课程规范或实验室资料。"
    return "\n".join([*knowledge_lines, *paper_lines])


def _build_citation_text(title: str, authors: list[str], venue: str, year: str) -> str:
    author_text = ", ".join(authors) if authors else "Unknown Author"
    suffix = f"{venue}, {year}" if venue and year else venue or year or "未填写来源"
    return f"{author_text}. {title}. {suffix}."


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
