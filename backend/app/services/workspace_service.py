from __future__ import annotations

from datetime import datetime
import html
import re
import socket
import urllib.error
import urllib.request
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator
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
    LiteraturePaperSuggestRequest,
    LiteraturePaperSuggestResponse,
    LiteraturePaperUpdateRequest,
    ProfileCenterResponse,
    ProfileEntryRead,
    ProfileEntryUpdateRequest,
    ProfileVersionRead,
    ResearchToolRunRead,
    ResearchToolRunRequest,
    WorkspaceOverviewResponse,
)
from app.services.llm_client import qwen_chat_json
from app.services.scholarly_search_service import resolve_scholarly_resource
from app.services.knowledge_service import search_knowledge
from app.services.formula_guidance import FORMULA_OUTPUT_INSTRUCTIONS


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

    @field_validator(
        "diagnosis",
        "structure_suggestions",
        "citation_suggestions",
        "method_steps",
        "topic_options",
        "experiment_plan",
        "scoring_rubric",
        "source_notes",
        "safety_notes",
        "next_actions",
        mode="before",
    )
    @classmethod
    def _coerce_string_list(cls, value: Any) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            items: list[str] = []
            for item in value:
                if item is None:
                    continue
                if isinstance(item, str):
                    text = item.strip()
                    if text:
                        items.append(text)
                else:
                    text = str(item).strip()
                    if text:
                        items.append(text)
            return items
        if isinstance(value, dict):
            flattened: list[str] = []
            for key, item in value.items():
                if isinstance(item, (str, int, float, bool)):
                    text = f"{key}: {item}".strip()
                else:
                    text = str(item).strip()
                if text:
                    flattened.append(text)
            return flattened
        if isinstance(value, str):
            parts = re.split(r"[\n;；,，]+", value)
            return [part.strip() for part in parts if part.strip()]
        text = str(value).strip()
        return [text] if text else []

    @field_validator("defense_questions", mode="before")
    @classmethod
    def _coerce_defense_questions(cls, value: Any) -> list[dict[str, Any]]:
        if value is None or value == "":
            return []
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            return [value]
        return []


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
            recommendations=[],
        )
    profile_data = record.profile_data or {}
    return ProfileCenterResponse(
        profile_id=record.id,
        current_revision=record.current_revision,
        profile_data=profile_data,
        entries=_build_profile_entries(record),
        versions=[
            ProfileVersionRead.model_validate(version)
            for version in sorted(record.versions, key=lambda item: item.revision, reverse=True)[:10]
        ],
        recommendations=[],
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


def delete_profile_entry(db: Session, user: User, key: str) -> ProfileCenterResponse:
    record = db.scalar(
        select(StudentProfileRecord)
        .options(selectinload(StudentProfileRecord.versions))
        .where(StudentProfileRecord.user_id == user.id)
        .order_by(desc(StudentProfileRecord.updated_at))
    )
    if record is None:
        raise KeyError("profile not found")

    profile_data = dict(record.profile_data or {})
    meta = dict(profile_data.get("_entry_meta") or {})
    if key not in profile_data and key not in meta:
        raise KeyError("profile entry not found")

    profile_data.pop(key, None)
    meta.pop(key, None)
    profile_data["_entry_meta"] = meta

    record.current_revision += 1
    record.profile_data = profile_data
    record.updated_at = datetime.utcnow()
    label = PROFILE_ENTRY_LABELS.get(key, key)
    db.add(
        StudentProfileVersion(
            profile_id=record.id,
            revision=record.current_revision,
            source="manual_delete",
            update_reason=f"用户删除画像条目：{label}",
            extracted_features={"deleted_key": key},
            profile_data=profile_data,
        )
    )
    db.add(
        AgentTaskRecord(
            session_id=f"profile-entry-{user.id}",
            user_id=user.id,
            agent="MemoryAgent",
            status="completed",
            input_summary=f"删除画像条目：{label}",
            output_summary="用户手动删除画像条目",
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
    ordered_keys = list(PROFILE_ENTRY_LABELS)
    ordered_keys.extend(
        key for key in profile_data.keys()
        if key != "_entry_meta" and key not in PROFILE_ENTRY_LABELS
    )
    ordered_keys.extend(
        key for key in meta.keys()
        if key != "_entry_meta" and key not in ordered_keys
    )
    for key in ordered_keys:
        label = PROFILE_ENTRY_LABELS.get(key, key.replace("_", " "))
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


def suggest_literature_metadata(request: LiteraturePaperSuggestRequest) -> LiteraturePaperSuggestResponse:
    hit = resolve_scholarly_resource(request.title, request.title)
    if hit is None:
        return LiteraturePaperSuggestResponse(
            title=request.title,
            authors=[],
            venue='',
            year='',
            source_uri='',
            abstract='',
            keywords=[request.title] if request.title else [],
            source_name='manual',
            reason='未检索到可用论文来源，请手动补充作者、来源和摘要',
        )

    source_name = hit.source or 'Scholar'
    abstract = getattr(hit, 'abstract', '') or ''
    if not abstract:
        abstract = _fetch_page_abstract(hit.url)

    return LiteraturePaperSuggestResponse(
        title=hit.title or request.title,
        authors=[],
        venue='',
        year='',
        source_uri=hit.url,
        abstract=abstract,
        keywords=[request.title],
        source_name=source_name,
        reason=hit.reason,
    )


def _fetch_page_abstract(url: str) -> str:
    if not url:
        return ''
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "User-Agent": "Mozilla/5.0 (compatible; zhiyan-xinglian-learning-platform/0.1)",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
                return ""
            html_text = response.read().decode("utf-8", errors="ignore")[:200000]
    except (TimeoutError, socket.timeout, urllib.error.URLError, urllib.error.HTTPError):
        return ""

    for pattern in (
        r'<meta\s+name=["\']citation_abstract["\']\s+content=["\']([^"\']+)["\']',
        r'<meta\s+name=["\']description["\']\s+content=["\']([^"\']+)["\']',
        r'<meta\s+property=["\']og:description["\']\s+content=["\']([^"\']+)["\']',
    ):
        match = re.search(pattern, html_text, flags=re.I | re.S)
        if match:
            text = html.unescape(match.group(1))
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                return text

    abstract_block = re.search(
        r'(?is)<(?:div|section|p)[^>]*(?:class|id)=["\'][^"\']*abstract[^"\']*["\'][^>]*>(.*?)</(?:div|section|p)>',
        html_text,
    )
    if abstract_block:
        text = re.sub(r"<[^>]+>", " ", abstract_block.group(1))
        text = html.unescape(re.sub(r"\s+", " ", text)).strip()
        if text:
            return text

    return ""


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
        f"\n{FORMULA_OUTPUT_INSTRUCTIONS}"
    )
    output = qwen_chat_json(system_prompt, user_prompt, _ResearchToolOutput, user=user)
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


def _parse_datetime(value: Any) -> Optional[datetime]:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError:
        return None
