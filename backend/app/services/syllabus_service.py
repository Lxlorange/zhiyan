from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Optional

from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.learning import (
    AgentTaskRecord,
    DailyLearningPlan,
    DailyLearningPlanItem,
    LearningProject,
    LearningProjectEvent,
    LearningSyllabusItem,
    LearningSyllabusOperation,
    LearningSyllabusVersion,
    StudentProfileRecord,
)
from app.models.user import User
from app.schemas import (
    DailyPlanCoachRequest,
    DailyPlanCoachResponse,
    DailyPlanGenerateRequest,
    DailyPlanMoveItemRequest,
    DailyPlanShiftItemRequest,
    SyllabusAdaptRequest,
    SyllabusCompareResponse,
    SyllabusGenerateRequest,
    SyllabusItemCreateRequest,
    SyllabusItemSplitRequest,
    SyllabusItemStatusRequest,
    SyllabusItemUpdateRequest,
    SyllabusItemsMergeRequest,
    SyllabusRegenerateStageRequest,
    SyllabusReorderRequest,
)
from app.services.ai_workflow import build_profile_with_summary
from app.services.knowledge_ingestion_service import search_knowledge_enhanced
from app.services.llm_client import qwen_chat_json
from app.services.persistence_service import upsert_profile_from_dialogue
from app.services.formula_guidance import FORMULA_OUTPUT_INSTRUCTIONS


class _GeneratedSyllabusItem(BaseModel):
    title: str
    item_type: str
    stage: str
    difficulty: str
    estimated_minutes: int = Field(ge=5, le=600)
    recommendation_reason: str
    objective: str
    prerequisites: list[str] = Field(default_factory=list)
    knowledge_points: list[str] = Field(default_factory=list)
    related_documents: list[str] = Field(default_factory=list)
    recommended_resource_types: list[str] = Field(default_factory=list)
    classroom_types: list[str] = Field(default_factory=list)
    completion_criteria: str
    assessment_method: str


class _GeneratedSyllabus(BaseModel):
    generation_reason: str
    syllabus_agent_summary: str
    path_planner_summary: str
    adaptation_strategy: str
    items: list[_GeneratedSyllabusItem] = Field(min_length=6, max_length=12)


class _GeneratedAdaptation(BaseModel):
    adjustment_reason: str
    impact_scope: list[str] = Field(default_factory=list)
    requires_confirmation: bool = False
    items: list[_GeneratedSyllabusItem] = Field(min_length=1, max_length=12)


def _project_or_404(db: Session, user: User, project_id: int) -> LearningProject:
    project = db.scalar(
        select(LearningProject).where(LearningProject.id == project_id, LearningProject.user_id == user.id)
    )
    if project is None:
        raise KeyError("project not found")
    return project


def _version_or_404(db: Session, user: User, version_id: int) -> LearningSyllabusVersion:
    version = db.scalar(
        select(LearningSyllabusVersion)
        .options(
            selectinload(LearningSyllabusVersion.items),
            selectinload(LearningSyllabusVersion.operations),
        )
        .where(LearningSyllabusVersion.id == version_id, LearningSyllabusVersion.user_id == user.id)
    )
    if version is None:
        raise KeyError("syllabus version not found")
    return version


def _item_or_404(db: Session, user: User, item_id: int) -> LearningSyllabusItem:
    item = db.scalar(
        select(LearningSyllabusItem).where(LearningSyllabusItem.id == item_id, LearningSyllabusItem.user_id == user.id)
    )
    if item is None:
        raise KeyError("syllabus item not found")
    return item


def _current_version(db: Session, user: User, project_id: int) -> Optional[LearningSyllabusVersion]:
    return db.scalar(
        select(LearningSyllabusVersion)
        .options(selectinload(LearningSyllabusVersion.items), selectinload(LearningSyllabusVersion.operations))
        .where(
            LearningSyllabusVersion.project_id == project_id,
            LearningSyllabusVersion.user_id == user.id,
            LearningSyllabusVersion.is_current.is_(True),
            LearningSyllabusVersion.status != "deleted",
        )
        .order_by(LearningSyllabusVersion.version_no.desc())
    )


def _next_version_no(db: Session, project_id: int) -> int:
    current = db.scalar(
        select(func.max(LearningSyllabusVersion.version_no)).where(LearningSyllabusVersion.project_id == project_id)
    )
    return int(current or 0) + 1


def _latest_profile(db: Session, user: User) -> Optional[StudentProfileRecord]:
    return db.scalar(
        select(StudentProfileRecord)
        .where(StudentProfileRecord.user_id == user.id)
        .order_by(StudentProfileRecord.current_revision.desc(), StudentProfileRecord.updated_at.desc())
    )


def _as_list(value: object) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [str(value)]


def _log_operation(
    db: Session,
    *,
    version: LearningSyllabusVersion,
    user: User,
    operation_type: str,
    summary: str,
    payload: Optional[dict] = None,
    item_id: Optional[int] = None,
) -> LearningSyllabusOperation:
    operation = LearningSyllabusOperation(
        syllabus_version_id=version.id,
        item_id=item_id,
        project_id=version.project_id,
        user_id=user.id,
        operation_type=operation_type,
        summary=summary,
        payload=payload or {},
    )
    db.add(operation)
    version.user_adjustments = [
        *list(version.user_adjustments or []),
        {
            "type": operation_type,
            "summary": summary,
            "item_id": item_id,
            "created_at": datetime.utcnow().isoformat(),
        },
    ]
    return operation


def _write_project_event(
    db: Session,
    *,
    project: LearningProject,
    user: User,
    event_type: str,
    summary: str,
    payload: Optional[dict] = None,
) -> None:
    db.add(
        LearningProjectEvent(
            project_id=project.id,
            user_id=user.id,
            event_type=event_type,
            summary=summary,
            payload=payload or {},
        )
    )


def _recalculate_project_learning_progress(db: Session, user: User, project: LearningProject) -> None:
    active_count = db.scalar(
        select(func.count(LearningSyllabusItem.id))
        .join(LearningSyllabusVersion, LearningSyllabusItem.syllabus_version_id == LearningSyllabusVersion.id)
        .where(
            LearningSyllabusItem.project_id == project.id,
            LearningSyllabusItem.user_id == user.id,
            LearningSyllabusVersion.is_current.is_(True),
            LearningSyllabusVersion.status != "deleted",
            LearningSyllabusItem.status.notin_(["deleted", "merged", "split", "skipped"]),
        )
    ) or 0
    completed_count = db.scalar(
        select(func.count(LearningSyllabusItem.id))
        .join(LearningSyllabusVersion, LearningSyllabusItem.syllabus_version_id == LearningSyllabusVersion.id)
        .where(
            LearningSyllabusItem.project_id == project.id,
            LearningSyllabusItem.user_id == user.id,
            LearningSyllabusVersion.is_current.is_(True),
            LearningSyllabusVersion.status != "deleted",
            LearningSyllabusItem.status.in_(["completed", "mastered"]),
        )
    ) or 0
    project.completed_item_count = int(completed_count)
    project.progress = round((completed_count / active_count) * 100) if active_count else 0


def _knowledge_context(db: Session, project: LearningProject) -> list[dict]:
    query = " ".join(
        [
            project.research_direction,
            project.learning_goal,
            " ".join(project.related_knowledge_points or []),
        ]
    )
    return search_knowledge_enhanced(db, query, limit=10)


def _knowledge_base_version(knowledge: list[dict]) -> str:
    sources: list[str] = []
    for hit in knowledge:
        source = str(hit.get("source_uri") or hit.get("document_title") or "").strip()
        if source and source not in sources:
            sources.append(source)
        if len(sources) >= 3:
            break
    if not sources:
        return "未命中知识库资料"
    return ("知识库：" + " / ".join(sources))[:128]


def _profile_context(profile: Optional[StudentProfileRecord]) -> dict:
    if profile is None:
        return {}
    data = dict(profile.profile_data or {})
    data["revision"] = profile.current_revision
    return data


def _project_prompt(project: LearningProject, profile: Optional[StudentProfileRecord], knowledge: list[dict]) -> str:
    return (
        "请为一个高校科研学习项目生成可执行的个性化学习清单。必须输出严格 JSON，不要 Markdown。\n"
        "清单必须围绕科研方向，不要把重点放在展示用户画像；用户画像只作为个性化依据。\n"
        "学习项类型至少覆盖概念理解、数学基础、代码实践、实验复现、论文阅读、案例分析、可视化演示、练习评估、项目报告、综述写作、拓展阅读、阶段复盘中的多种类型。\n"
        "每个学习项必须给出推荐理由、关联知识点、可生成课堂内容类型、完成标准和评估方式。\n"
        "如果项目是科研项目，学习清单必须根据用户输入方向和可用资料动态覆盖以下课程模式：\n"
        "1. 文献综述课：提供相关论文摘要、资料来源、阅读矩阵和研究脉络；\n"
        "2. 选题凝练课：从宽泛方向形成具体题目、研究问题、边界和预期贡献；\n"
        "3. 实验助手课：生成技术路线、数据采集方案、评价指标、实验变量、图表规范和阶段计划；\n"
        "4. 论文写作课：按课程论文规范完成摘要、引言、相关工作、方法、实验与讨论；\n"
        "5. 模拟答辩课：生成开题/中期/最终答辩问题、追问、评分和修改建议。\n"
        "这些模式都从课堂入口进入，但 item_type 和 classroom_types 要明确区分，例如 literature_review, topic_selection, experiment_assistant, paper_writing, mock_defense。\n"
        "每个科研学习项的 related_documents 必须尽量引用课程知识库或用户文献库中已有资料名称，不要编造来源。\n"
        f"{FORMULA_OUTPUT_INSTRUCTIONS}\n"
        f"项目标题：{project.title}\n"
        f"科研方向：{project.research_direction}\n"
        f"学科：{project.subject}\n"
        f"学习目标：{project.learning_goal}\n"
        f"基础摘要：{project.foundation_summary}\n"
        f"预期产出：{project.expected_output}\n"
        f"推荐周期：{project.recommended_period}\n"
        f"每日学习时长：{project.daily_minutes} 分钟\n"
        f"难度：{project.difficulty}\n"
        f"教师要求：{project.teacher_notes}\n"
        f"截止时间：{project.deadline.isoformat() if project.deadline else '未设置'}\n"
        f"用户画像：{_profile_context(profile)}\n"
        f"课程知识库检索结果：{knowledge}\n"
        "输出 JSON 格式："
        '{"generation_reason":"...","syllabus_agent_summary":"...",'
        '"path_planner_summary":"...","adaptation_strategy":"...",'
        '"items":[{"title":"...","item_type":"concept","stage":"阶段一",'
        '"difficulty":"medium","estimated_minutes":45,"recommendation_reason":"...",'
        '"objective":"...","prerequisites":["..."],"knowledge_points":["..."],'
        '"related_documents":["..."],"recommended_resource_types":["讲解文档"],'
        '"classroom_types":["总结讲解","例题互动"],"completion_criteria":"...",'
        '"assessment_method":"..."}]}'
    )


def generate_syllabus(
    db: Session,
    user: User,
    project_id: int,
    request: SyllabusGenerateRequest,
) -> LearningSyllabusVersion:
    project = _project_or_404(db, user, project_id)
    profile = _latest_profile(db, user)
    knowledge = _knowledge_context(db, project)
    started_at = time.perf_counter()

    result = qwen_chat_json(
        "你是 SyllabusAgent 与 PathPlannerAgent。你的任务是把科研方向拆成可操作学习清单，并保证结构化、可执行、可评估。",
        _project_prompt(project, profile, knowledge)
        + f"\n本次额外生成目标：{request.generation_goal or '按项目目标完整生成'}",
        _GeneratedSyllabus,
        user=user,
    )
    latency_ms = int((time.perf_counter() - started_at) * 1000)

    for old_version in db.scalars(
        select(LearningSyllabusVersion).where(
            LearningSyllabusVersion.project_id == project.id,
            LearningSyllabusVersion.user_id == user.id,
            LearningSyllabusVersion.is_current.is_(True),
        )
    ):
        old_version.is_current = False

    version = LearningSyllabusVersion(
        project_id=project.id,
        user_id=user.id,
        version_no=_next_version_no(db, project.id),
        generation_method="ai",
        generation_reason=result.generation_reason,
        profile_revision=profile.current_revision if profile else None,
        knowledge_base_version=_knowledge_base_version(knowledge),
        is_current=True,
        agent_summary={
            "SyllabusAgent": result.syllabus_agent_summary,
            "PathPlannerAgent": result.path_planner_summary,
            "AdaptationAgent": result.adaptation_strategy,
        },
    )
    db.add(version)
    db.flush()

    for index, generated in enumerate(result.items, start=1):
        db.add(_item_from_generated(generated, version=version, project=project, user=user, order=index))
    db.flush()
    next_order = len(result.items) + 1
    for reading_item in _research_reading_items_from_project(project):
        db.add(_item_from_research_reading(reading_item, version=version, project=project, user=user, order=next_order))
        next_order += 1
    db.flush()

    db.add(
        AgentTaskRecord(
            session_id=f"project-{project.id}-syllabus-v{version.version_no}",
            user_id=user.id,
            agent="SyllabusAgent+PathPlannerAgent",
            status="completed",
            input_summary=f"{project.research_direction} / {project.learning_goal}",
            output_summary=f"生成 {len(result.items)} 个学习项，版本 v{version.version_no}",
            latency_ms=latency_ms,
        )
    )
    project.status = "syllabus_ready"
    project.current_stage = "学习清单已生成"
    project.progress = max(project.progress, 10)
    project.next_step = "进入每日计划，按日期继续学习"
    _create_daily_plan_for_version(
        db,
        user=user,
        project=project,
        version=version,
        title=f"{project.title} 每日学习计划",
        start_date=datetime.utcnow(),
        daily_minutes=project.daily_minutes,
        study_weekends=project.study_weekends,
        study_weekdays=project.study_weekdays or [0, 1, 2, 3, 4],
        generation_reason=f"学习清单 v{version.version_no} 生成后自动排期",
    )
    _write_project_event(
        db,
        project=project,
        user=user,
        event_type="syllabus_generated",
        summary=f"生成学习清单 v{version.version_no}",
        payload={"version_id": version.id, "item_count": len(result.items), "latency_ms": latency_ms},
    )
    db.commit()
    db.refresh(version)
    return get_syllabus_version(db, user, version.id)


def _item_from_generated(
    generated: _GeneratedSyllabusItem,
    *,
    version: LearningSyllabusVersion,
    project: LearningProject,
    user: User,
    order: int,
) -> LearningSyllabusItem:
    return LearningSyllabusItem(
        syllabus_version_id=version.id,
        project_id=project.id,
        user_id=user.id,
        title=generated.title,
        item_type=generated.item_type,
        stage=generated.stage,
        difficulty=generated.difficulty,
        estimated_minutes=generated.estimated_minutes,
        recommendation_reason=generated.recommendation_reason,
        objective=generated.objective,
        prerequisites=_as_list(generated.prerequisites),
        knowledge_points=_as_list(generated.knowledge_points),
        related_documents=_as_list(generated.related_documents),
        recommended_resource_types=_as_list(generated.recommended_resource_types),
        classroom_types=_as_list(generated.classroom_types),
        completion_criteria=generated.completion_criteria,
        assessment_method=generated.assessment_method,
        user_order=order,
    )


def _research_reading_items_from_project(project: LearningProject) -> list[dict]:
    training = project.research_training or {}
    if not training.get("enabled"):
        return []
    readings = training.get("reading_list")
    if not isinstance(readings, list):
        return []
    return [reading for reading in readings if isinstance(reading, dict)]


def _item_from_research_reading(
    reading: dict,
    *,
    version: LearningSyllabusVersion,
    project: LearningProject,
    user: User,
    order: int,
) -> LearningSyllabusItem:
    level = str(reading.get("level") or "paper").strip()
    title = str(reading.get("title") or "").strip()
    if not title:
        raise ValueError("research reading item title is required")
    url = str(reading.get("arxiv_url") or reading.get("doi_url") or reading.get("source_url") or "").strip()
    source = f"{title} | {url}" if url else title
    level_labels = {
        "foundation": "基础论文/教程",
        "classic": "领域经典论文",
        "seminal": "开山论文",
        "frontier": "科研前沿论文",
    }
    level_label = level_labels.get(level, level)
    return LearningSyllabusItem(
        syllabus_version_id=version.id,
        project_id=project.id,
        user_id=user.id,
        title=f"{level_label}精读：{title}",
        item_type="paper_reading",
        stage=f"论文精读 · {level_label}",
        difficulty=project.difficulty or "medium",
        estimated_minutes=max(45, min(180, int(project.daily_minutes or 60) * 2)),
        recommendation_reason=str(reading.get("why_read") or "科研项目要求按阅读顺序完成论文复盘。"),
        objective=(
            f"围绕论文《{title}》完成一份可评分复盘：核心问题、方法证据、局限、"
            "与本人选题的关系，以及下一步计划。"
        ),
        prerequisites=[],
        knowledge_points=[project.research_direction, level_label, *list(reading.get("review_focus") or [])][:8],
        related_documents=[source],
        recommended_resource_types=["单篇论文 PPT", "论文复盘评分", "下一步计划"],
        classroom_types=["paper_ppt", "paper_review", "research_planning"],
        completion_criteria="完成单篇论文 PPT 学习、例题、实操任务，并提交论文复盘总结与下一步计划。",
        assessment_method="按详实程度、关联度、工作量、规划性、批判性思考五个维度评分。",
        user_order=order,
        is_manual=False,
    )


def get_current_syllabus(db: Session, user: User, project_id: int) -> LearningSyllabusVersion:
    _project_or_404(db, user, project_id)
    version = _current_version(db, user, project_id)
    if version is None:
        raise KeyError("current syllabus not found")
    return version


def get_syllabus_version(db: Session, user: User, version_id: int) -> LearningSyllabusVersion:
    return _version_or_404(db, user, version_id)


def list_syllabus_versions(db: Session, user: User, project_id: int) -> list[LearningSyllabusVersion]:
    _project_or_404(db, user, project_id)
    return list(
        db.scalars(
            select(LearningSyllabusVersion)
            .where(
                LearningSyllabusVersion.project_id == project_id,
                LearningSyllabusVersion.user_id == user.id,
                LearningSyllabusVersion.status != "deleted",
            )
            .order_by(LearningSyllabusVersion.version_no.desc())
        )
    )


def activate_syllabus_version(db: Session, user: User, version_id: int) -> LearningSyllabusVersion:
    version = _version_or_404(db, user, version_id)
    for old_version in db.scalars(
        select(LearningSyllabusVersion).where(
            LearningSyllabusVersion.project_id == version.project_id,
            LearningSyllabusVersion.user_id == user.id,
        )
    ):
        old_version.is_current = old_version.id == version.id
    _log_operation(db, version=version, user=user, operation_type="activate", summary=f"设置 v{version.version_no} 为当前版本")
    db.commit()
    return get_syllabus_version(db, user, version.id)


def copy_syllabus_version(db: Session, user: User, version_id: int) -> LearningSyllabusVersion:
    source = _version_or_404(db, user, version_id)
    for old_version in db.scalars(
        select(LearningSyllabusVersion).where(
            LearningSyllabusVersion.project_id == source.project_id,
            LearningSyllabusVersion.user_id == user.id,
            LearningSyllabusVersion.is_current.is_(True),
        )
    ):
        old_version.is_current = False
    new_version = LearningSyllabusVersion(
        project_id=source.project_id,
        user_id=user.id,
        version_no=_next_version_no(db, source.project_id),
        generation_method="copy",
        generation_reason=f"从 v{source.version_no} 复制，用于继续调整",
        profile_revision=source.profile_revision,
        knowledge_base_version=source.knowledge_base_version,
        is_current=True,
        agent_summary=source.agent_summary,
    )
    db.add(new_version)
    db.flush()
    for index, item in enumerate(source.items, start=1):
        db.add(_copy_item(item, version=new_version, user=user, order=index))
    _log_operation(
        db,
        version=new_version,
        user=user,
        operation_type="copy_version",
        summary=f"复制 v{source.version_no} 为 v{new_version.version_no}",
        payload={"source_version_id": source.id},
    )
    db.commit()
    return get_syllabus_version(db, user, new_version.id)


def _copy_item(
    item: LearningSyllabusItem,
    *,
    version: LearningSyllabusVersion,
    user: User,
    order: int,
) -> LearningSyllabusItem:
    return LearningSyllabusItem(
        syllabus_version_id=version.id,
        project_id=version.project_id,
        user_id=user.id,
        title=item.title,
        item_type=item.item_type,
        stage=item.stage,
        difficulty=item.difficulty,
        estimated_minutes=item.estimated_minutes,
        recommendation_reason=item.recommendation_reason,
        objective=item.objective,
        prerequisites=list(item.prerequisites or []),
        knowledge_points=list(item.knowledge_points or []),
        related_documents=list(item.related_documents or []),
        recommended_resource_types=list(item.recommended_resource_types or []),
        classroom_types=list(item.classroom_types or []),
        completion_criteria=item.completion_criteria,
        assessment_method=item.assessment_method,
        status=item.status,
        user_order=order,
        is_locked=item.is_locked,
        is_manual=item.is_manual,
    )


def compare_syllabus_versions(
    db: Session,
    user: User,
    base_version_id: int,
    target_version_id: int,
) -> SyllabusCompareResponse:
    base = _version_or_404(db, user, base_version_id)
    target = _version_or_404(db, user, target_version_id)
    base_by_title = {item.title: item for item in base.items if item.status != "deleted"}
    target_by_title = {item.title: item for item in target.items if item.status != "deleted"}
    added = [item for title, item in target_by_title.items() if title not in base_by_title]
    removed = [item for title, item in base_by_title.items() if title not in target_by_title]
    changed = []
    for title, base_item in base_by_title.items():
        target_item = target_by_title.get(title)
        if not target_item:
            continue
        fields = {}
        for field in ["stage", "difficulty", "estimated_minutes", "knowledge_points", "classroom_types", "status"]:
            if getattr(base_item, field) != getattr(target_item, field):
                fields[field] = {"base": getattr(base_item, field), "target": getattr(target_item, field)}
        if fields:
            changed.append({"title": title, "base_item_id": base_item.id, "target_item_id": target_item.id, "fields": fields})
    return SyllabusCompareResponse(
        base_version=base.version_no,
        target_version=target.version_no,
        added=added,
        removed=removed,
        changed=changed,
    )


def add_syllabus_item(
    db: Session,
    user: User,
    version_id: int,
    request: SyllabusItemCreateRequest,
) -> LearningSyllabusVersion:
    version = _version_or_404(db, user, version_id)
    max_order = max([item.user_order for item in version.items] or [0])
    project = _project_or_404(db, user, version.project_id)
    item = LearningSyllabusItem(
        syllabus_version_id=version.id,
        project_id=version.project_id,
        user_id=user.id,
        title=request.title,
        item_type=request.item_type,
        stage=request.stage,
        difficulty=request.difficulty,
        estimated_minutes=request.estimated_minutes,
        recommendation_reason=request.recommendation_reason,
        objective=request.objective,
        prerequisites=request.prerequisites,
        knowledge_points=request.knowledge_points,
        related_documents=request.related_documents,
        recommended_resource_types=request.recommended_resource_types,
        classroom_types=request.classroom_types,
        completion_criteria=request.completion_criteria,
        assessment_method=request.assessment_method,
        user_order=request.user_order or max_order + 1,
        is_locked=request.is_locked,
        is_manual=True,
    )
    db.add(item)
    db.flush()
    _log_operation(
        db,
        version=version,
        user=user,
        operation_type="add_item",
        summary=f"新增学习项：{request.title}",
        payload=request.model_dump(),
        item_id=item.id,
    )
    project.status = "syllabus_adjusted"
    db.commit()
    return get_syllabus_version(db, user, version.id)


def update_syllabus_item(
    db: Session,
    user: User,
    item_id: int,
    request: SyllabusItemUpdateRequest,
) -> LearningSyllabusVersion:
    item = _item_or_404(db, user, item_id)
    version = _version_or_404(db, user, item.syllabus_version_id)
    if item.is_locked:
        raise ValueError("locked syllabus item cannot be edited")
    changes = request.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(item, field, value)
    for plan_item in db.scalars(
        select(DailyLearningPlanItem).where(
            DailyLearningPlanItem.syllabus_item_id == item.id,
            DailyLearningPlanItem.user_id == user.id,
        )
    ):
        if "title" in changes:
            plan_item.title = item.title
        if "estimated_minutes" in changes:
            plan_item.estimated_minutes = item.estimated_minutes
        if "objective" in changes:
            plan_item.learning_focus = item.objective
        if "recommended_resource_types" in changes:
            plan_item.resource_types = item.recommended_resource_types
    _log_operation(
        db,
        version=version,
        user=user,
        operation_type="update_item",
        summary=f"更新学习项：{item.title}",
        payload=changes,
        item_id=item.id,
    )
    db.commit()
    return get_syllabus_version(db, user, version.id)


def delete_syllabus_item(db: Session, user: User, item_id: int) -> LearningSyllabusVersion:
    item = _item_or_404(db, user, item_id)
    version = _version_or_404(db, user, item.syllabus_version_id)
    if item.is_locked:
        raise ValueError("locked syllabus item cannot be deleted")
    item.status = "deleted"
    for plan_item in db.scalars(
        select(DailyLearningPlanItem).where(
            DailyLearningPlanItem.syllabus_item_id == item.id,
            DailyLearningPlanItem.user_id == user.id,
        )
    ):
        plan_item.status = "removed"
    _log_operation(
        db,
        version=version,
        user=user,
        operation_type="delete_item",
        summary=f"删除学习项：{item.title}",
        payload={"title": item.title},
        item_id=item.id,
    )
    db.commit()
    return get_syllabus_version(db, user, version.id)


def reorder_syllabus_items(
    db: Session,
    user: User,
    version_id: int,
    request: SyllabusReorderRequest,
) -> LearningSyllabusVersion:
    version = _version_or_404(db, user, version_id)
    items = {item.id: item for item in version.items}
    for order, item_id in enumerate(request.item_ids, start=1):
        if item_id in items:
            items[item_id].user_order = order
    _log_operation(
        db,
        version=version,
        user=user,
        operation_type="reorder_items",
        summary="调整学习项顺序",
        payload={"item_ids": request.item_ids},
    )
    db.commit()
    return get_syllabus_version(db, user, version.id)


def update_syllabus_item_status(
    db: Session,
    user: User,
    item_id: int,
    request: SyllabusItemStatusRequest,
) -> LearningSyllabusVersion:
    item = _item_or_404(db, user, item_id)
    version = _version_or_404(db, user, item.syllabus_version_id)
    previous_status = item.status
    item.status = request.status
    for plan_item in db.scalars(
        select(DailyLearningPlanItem).where(
            DailyLearningPlanItem.syllabus_item_id == item.id,
            DailyLearningPlanItem.user_id == user.id,
        )
    ):
        plan_item.status = request.status
    project = _project_or_404(db, user, item.project_id)
    if request.status in {"in_progress", "completed", "mastered"}:
        project.last_learned_at = datetime.utcnow()
        project.status = "learning"
        project.current_stage = item.stage
        project.next_step = item.title if request.status == "in_progress" else "继续进入下一项学习"
    _recalculate_project_learning_progress(db, user, project)
    if project.progress >= 100:
        project.status = "completed"
        project.current_stage = "学习清单已完成"
        project.next_step = "进入练习评估或阶段复盘"
    _log_operation(
        db,
        version=version,
        user=user,
        operation_type=f"mark_{request.status}",
        summary=f"更新学习项状态：{item.title} -> {request.status}",
        payload={"reason": request.reason, "previous_status": previous_status, "status": request.status},
        item_id=item.id,
    )
    _write_project_event(
        db,
        project=project,
        user=user,
        event_type="syllabus_item_status_changed",
        summary=f"{item.title}: {previous_status} -> {request.status}",
        payload={
            "item_id": item.id,
            "version_id": version.id,
            "previous_status": previous_status,
            "status": request.status,
            "reason": request.reason,
            "progress": project.progress,
        },
    )
    db.commit()
    return get_syllabus_version(db, user, version.id)


def split_syllabus_item(
    db: Session,
    user: User,
    item_id: int,
    request: SyllabusItemSplitRequest,
) -> LearningSyllabusVersion:
    item = _item_or_404(db, user, item_id)
    version = _version_or_404(db, user, item.syllabus_version_id)
    project = _project_or_404(db, user, item.project_id)
    if item.is_locked:
        raise ValueError("locked syllabus item cannot be split")
    item.status = "split"
    insert_order = item.user_order
    for offset, part in enumerate(request.parts, start=1):
        db.add(
            LearningSyllabusItem(
                syllabus_version_id=version.id,
                project_id=project.id,
                user_id=user.id,
                title=part.title,
                item_type=part.item_type,
                stage=part.stage or item.stage,
                difficulty=part.difficulty,
                estimated_minutes=part.estimated_minutes,
                recommendation_reason=part.recommendation_reason,
                objective=part.objective,
                prerequisites=part.prerequisites,
                knowledge_points=part.knowledge_points,
                related_documents=part.related_documents,
                recommended_resource_types=part.recommended_resource_types,
                classroom_types=part.classroom_types,
                completion_criteria=part.completion_criteria,
                assessment_method=part.assessment_method,
                user_order=insert_order + offset,
                is_manual=True,
            )
        )
    _log_operation(
        db,
        version=version,
        user=user,
        operation_type="split_item",
        summary=f"拆分学习项：{item.title}",
        payload={"reason": request.reason, "part_count": len(request.parts)},
        item_id=item.id,
    )
    db.commit()
    return get_syllabus_version(db, user, version.id)


def merge_syllabus_items(
    db: Session,
    user: User,
    request: SyllabusItemsMergeRequest,
) -> LearningSyllabusVersion:
    items = [_item_or_404(db, user, item_id) for item_id in request.item_ids]
    version_ids = {item.syllabus_version_id for item in items}
    if len(version_ids) != 1:
        raise ValueError("only items in the same syllabus version can be merged")
    version = _version_or_404(db, user, items[0].syllabus_version_id)
    project = _project_or_404(db, user, version.project_id)
    order = min(item.user_order for item in items)
    merged = LearningSyllabusItem(
        syllabus_version_id=version.id,
        project_id=project.id,
        user_id=user.id,
        title=request.title,
        item_type=items[0].item_type,
        stage=items[0].stage,
        difficulty=items[0].difficulty,
        estimated_minutes=sum(item.estimated_minutes for item in items),
        recommendation_reason=request.reason,
        objective="；".join([item.objective for item in items if item.objective]),
        prerequisites=sorted({value for item in items for value in item.prerequisites}),
        knowledge_points=sorted({value for item in items for value in item.knowledge_points}),
        related_documents=sorted({value for item in items for value in item.related_documents}),
        recommended_resource_types=sorted({value for item in items for value in item.recommended_resource_types}),
        classroom_types=sorted({value for item in items for value in item.classroom_types}),
        completion_criteria="；".join([item.completion_criteria for item in items if item.completion_criteria]),
        assessment_method="；".join([item.assessment_method for item in items if item.assessment_method]),
        user_order=order,
        is_manual=True,
    )
    db.add(merged)
    db.flush()
    for item in items:
        item.status = "merged"
    _log_operation(
        db,
        version=version,
        user=user,
        operation_type="merge_items",
        summary=f"合并 {len(items)} 个学习项为：{request.title}",
        payload={"item_ids": request.item_ids, "reason": request.reason},
        item_id=merged.id,
    )
    db.commit()
    return get_syllabus_version(db, user, version.id)


def regenerate_stage(
    db: Session,
    user: User,
    version_id: int,
    request: SyllabusRegenerateStageRequest,
) -> LearningSyllabusVersion:
    source = _version_or_404(db, user, version_id)
    project = _project_or_404(db, user, source.project_id)
    profile = _latest_profile(db, user)
    current_stage_items = [item for item in source.items if item.stage == request.stage and item.status != "deleted"]
    prompt = (
        _project_prompt(project, profile, _knowledge_context(db, project))
        + f"\n只重新生成阶段：{request.stage}\n"
        + f"原阶段学习项：{[item.title for item in current_stage_items]}\n"
        + f"用户指令：{request.instruction or '优化该阶段的顺序、难度和资源类型'}"
    )
    result = qwen_chat_json(
        "你是 PathPlannerAgent。请只输出当前阶段的替换学习项 JSON。",
        prompt,
        _GeneratedAdaptation,
        user=user,
    )
    new_version = copy_syllabus_version(db, user, source.id)
    for item in new_version.items:
        if item.stage == request.stage:
            item.status = "deleted"
    for index, generated in enumerate(result.items, start=max([item.user_order for item in new_version.items] or [0]) + 1):
        db.add(_item_from_generated(generated, version=new_version, project=project, user=user, order=index))
    new_version.generation_method = "regenerate_stage"
    new_version.generation_reason = result.adjustment_reason
    _log_operation(
        db,
        version=new_version,
        user=user,
        operation_type="regenerate_stage",
        summary=f"重新生成阶段：{request.stage}",
        payload={"stage": request.stage, "instruction": request.instruction, "impact_scope": result.impact_scope},
    )
    db.commit()
    return get_syllabus_version(db, user, new_version.id)


def adapt_syllabus(
    db: Session,
    user: User,
    project_id: int,
    request: SyllabusAdaptRequest,
) -> LearningSyllabusVersion:
    project = _project_or_404(db, user, project_id)
    source = get_current_syllabus(db, user, project_id)
    profile = _latest_profile(db, user)
    prompt = (
        _project_prompt(project, profile, _knowledge_context(db, project))
        + f"\n当前清单：{[{'id': item.id, 'title': item.title, 'stage': item.stage, 'status': item.status} for item in source.items]}\n"
        + f"触发类型：{request.trigger_type}\n"
        + f"证据：{request.evidence}\n"
        "请生成需要插入或替换的学习项，并解释调整原因。"
    )
    result = qwen_chat_json(
        "你是 AdaptationAgent。请根据学习行为反馈动态调整路径，输出严格 JSON。",
        prompt,
        _GeneratedAdaptation,
        user=user,
    )
    new_version = copy_syllabus_version(db, user, source.id)
    max_order = max([item.user_order for item in new_version.items] or [0])
    for index, generated in enumerate(result.items, start=max_order + 1):
        db.add(_item_from_generated(generated, version=new_version, project=project, user=user, order=index))
    new_version.generation_method = "adaptation"
    new_version.generation_reason = result.adjustment_reason
    new_version.agent_summary = {
        **dict(new_version.agent_summary or {}),
        "AdaptationAgent": {
            "trigger_type": request.trigger_type,
            "evidence": request.evidence,
            "impact_scope": result.impact_scope,
            "requires_confirmation": result.requires_confirmation or request.require_confirmation,
        },
    }
    _log_operation(
        db,
        version=new_version,
        user=user,
        operation_type="adapt_path",
        summary=result.adjustment_reason,
        payload={
            "trigger_type": request.trigger_type,
            "evidence": request.evidence,
            "impact_scope": result.impact_scope,
            "requires_confirmation": result.requires_confirmation or request.require_confirmation,
        },
    )
    _write_project_event(
        db,
        project=project,
        user=user,
        event_type="syllabus_adapted",
        summary=result.adjustment_reason,
        payload={"version_id": new_version.id, "trigger_type": request.trigger_type},
    )
    db.commit()
    return get_syllabus_version(db, user, new_version.id)


def generate_daily_plan(
    db: Session,
    user: User,
    project_id: int,
    request: DailyPlanGenerateRequest,
) -> DailyLearningPlan:
    project = _project_or_404(db, user, project_id)
    version = get_current_syllabus(db, user, project_id)
    daily_minutes = request.daily_minutes or project.daily_minutes
    study_weekdays = _normalize_weekdays(request.study_weekdays, request.study_weekends)
    study_weekends = any(day >= 5 for day in study_weekdays)
    plan = _create_daily_plan_for_version(
        db,
        user=user,
        project=project,
        version=version,
        title=request.title or f"{project.title} 每日学习计划",
        start_date=request.start_date or datetime.utcnow(),
        daily_minutes=daily_minutes,
        study_weekends=study_weekends,
        study_weekdays=study_weekdays,
        generation_reason=f"按当前清单 v{version.version_no}、每日 {daily_minutes} 分钟与可学习日自动排期",
    )
    _log_operation(
        db,
        version=version,
        user=user,
        operation_type="generate_daily_plan",
        summary=f"生成每日计划：{plan.title}",
        payload={
            "daily_minutes": daily_minutes,
            "study_weekends": study_weekends,
            "study_weekdays": study_weekdays,
            "item_count": len(plan.items),
        },
    )
    project.status = "daily_plan_ready"
    project.daily_minutes = daily_minutes
    project.study_weekends = study_weekends
    project.study_weekdays = study_weekdays
    project.current_stage = "每日计划已生成"
    project.next_step = "按每日计划进入课堂学习"
    db.commit()
    db.refresh(plan)
    return get_daily_plan(db, user, plan.id)


def _create_daily_plan_for_version(
    db: Session,
    *,
    user: User,
    project: LearningProject,
    version: LearningSyllabusVersion,
    title: str,
    start_date: datetime,
    daily_minutes: int,
    study_weekends: bool,
    study_weekdays: list[int],
    generation_reason: str,
) -> DailyLearningPlan:
    for old_plan in db.scalars(
        select(DailyLearningPlan).where(
            DailyLearningPlan.project_id == project.id,
            DailyLearningPlan.user_id == user.id,
            DailyLearningPlan.status == "active",
        )
    ):
        old_plan.status = "archived"

    allowed_weekdays = _normalize_weekdays(study_weekdays, study_weekends)
    current_date = _next_study_date(_date_floor(start_date), allowed_weekdays)
    plan = DailyLearningPlan(
        project_id=project.id,
        syllabus_version_id=version.id,
        user_id=user.id,
        title=title,
        start_date=current_date,
        daily_minutes=daily_minutes,
        study_weekends=study_weekends,
        study_weekdays=allowed_weekdays,
        generation_reason=generation_reason,
    )
    db.add(plan)
    db.flush()

    active_items = sorted(
        [item for item in version.items if item.status not in {"deleted", "skipped", "merged", "split"}],
        key=lambda item: item.user_order,
    )
    day_index = 1
    used_minutes = 0
    order_in_day = 1
    for item in active_items:
        item_minutes = max(1, int(item.estimated_minutes or daily_minutes))
        if used_minutes > 0 and used_minutes + item_minutes > daily_minutes:
            current_date = _next_study_date(current_date + timedelta(days=1), allowed_weekdays)
            day_index += 1
            used_minutes = 0
            order_in_day = 1
        db.add(
            DailyLearningPlanItem(
                daily_plan_id=plan.id,
                syllabus_item_id=item.id,
                project_id=project.id,
                user_id=user.id,
                day_index=day_index,
                planned_date=current_date,
                title=item.title,
                estimated_minutes=item_minutes,
                learning_focus=item.objective,
                resource_types=item.recommended_resource_types,
                status=item.status if item.status in {"completed", "mastered"} else "pending",
                user_order=order_in_day,
            )
        )
        used_minutes += item_minutes
        order_in_day += 1
    db.flush()
    return plan


def _date_floor(value: datetime) -> datetime:
    return datetime(value.year, value.month, value.day)


def _normalize_weekdays(weekdays: list[int], study_weekends: bool) -> list[int]:
    normalized = sorted({int(day) for day in weekdays if 0 <= int(day) <= 6})
    if not normalized:
        normalized = [0, 1, 2, 3, 4]
    return normalized


def _next_study_date(value: datetime, allowed_weekdays: list[int]) -> datetime:
    next_date = _date_floor(value)
    for _ in range(3700):
        if next_date.weekday() in allowed_weekdays:
            return next_date
        next_date += timedelta(days=1)
    raise ValueError("cannot find an available study date")


def _daily_plan_item_or_404(db: Session, user: User, item_id: int) -> DailyLearningPlanItem:
    item = db.scalar(
        select(DailyLearningPlanItem).where(
            DailyLearningPlanItem.id == item_id,
            DailyLearningPlanItem.user_id == user.id,
        )
    )
    if item is None:
        raise KeyError("daily plan item not found")
    return item


def move_daily_plan_item(
    db: Session,
    user: User,
    item_id: int,
    request: DailyPlanMoveItemRequest,
) -> DailyLearningPlan:
    item = _daily_plan_item_or_404(db, user, item_id)
    plan = get_daily_plan(db, user, item.daily_plan_id)
    target_date = _date_floor(request.planned_date)
    if target_date.weekday() not in _normalize_weekdays(plan.study_weekdays or [], plan.study_weekends):
        raise ValueError("target date is not an enabled study day")
    item.planned_date = target_date
    _normalize_daily_plan_order(plan)
    db.commit()
    return get_daily_plan(db, user, plan.id)


def shift_daily_plan_item(
    db: Session,
    user: User,
    item_id: int,
    request: DailyPlanShiftItemRequest,
) -> DailyLearningPlan:
    item = _daily_plan_item_or_404(db, user, item_id)
    plan = get_daily_plan(db, user, item.daily_plan_id)
    allowed_weekdays = _normalize_weekdays(plan.study_weekdays or [], plan.study_weekends)
    step = 1 if request.direction == "next" else -1
    target = _date_floor(item.planned_date + timedelta(days=step))
    for _ in range(3700):
        if target.weekday() in allowed_weekdays:
            item.planned_date = target
            _normalize_daily_plan_order(plan)
            db.commit()
            return get_daily_plan(db, user, plan.id)
        target = _date_floor(target + timedelta(days=step))
    raise ValueError("cannot find an available study date")


def coach_daily_plan(
    db: Session,
    user: User,
    plan_id: int,
    request: DailyPlanCoachRequest,
) -> DailyPlanCoachResponse:
    plan = get_daily_plan(db, user, plan_id)
    project = _project_or_404(db, user, plan.project_id)
    active_item = None
    if request.active_item_id is not None:
        active_item = next((item for item in plan.items if item.id == request.active_item_id), None)
        if active_item is None:
            raise KeyError("daily plan item not found")

    pending_items = [
        item for item in sorted(plan.items, key=lambda value: (value.planned_date, value.user_order))
        if item.status not in {"completed", "mastered", "removed"}
    ][:8]
    completed_count = len([item for item in plan.items if item.status in {"completed", "mastered"}])
    actionable_count = len([item for item in plan.items if item.status != "removed"])
    current_profile = _latest_profile(db, user)
    current_profile_data = current_profile.profile_data if current_profile else {}
    profile_message = "\n".join(
        [
            "请根据学生在每日学习计划中的自然语言反馈，更新动态学习画像。",
            "不要编造学生没有表达的信息；如果学生没有提到某一维度，请基于旧画像保持稳定。",
            f"学生原话：{request.message}",
            f"项目：{project.title}",
            f"学习目标：{project.learning_goal}",
            f"计划进度：{completed_count}/{actionable_count}",
            f"当前任务：{active_item.title if active_item else '未指定'}",
            f"当前任务学习重点：{active_item.learning_focus if active_item else ''}",
            f"近期待办：{[item.title for item in pending_items]}",
            f"旧画像：{current_profile_data}",
        ]
    )
    profile_result = build_profile_with_summary(profile_message)
    coach_result = _daily_plan_coach_result(
        project=project,
        plan=plan,
        active_item=active_item,
        student_message=request.message,
        profile_summary=profile_result.summary,
        pending_items=pending_items,
    )
    profile_record = upsert_profile_from_dialogue(
        db=db,
        user=user,
        profile=profile_result.profile,
        update_reason=f"每日计划教练根据学习复盘更新画像：{profile_result.summary}",
        extracted_features={
            "source_message": request.message,
            "active_item_id": request.active_item_id,
            "weak_points": profile_result.profile.weak_points,
            "learning_pace": profile_result.profile.learning_pace,
            "resource_preference": profile_result.profile.resource_preference,
            "mastery": profile_result.profile.mastery,
        },
        source="daily_plan_coach",
    )
    suggested_actions = coach_result.suggested_plan_actions[:4]
    _write_project_event(
        db,
        project=project,
        user=user,
        event_type="daily_plan_coach",
        summary=profile_result.summary,
        payload={
            "plan_id": plan.id,
            "active_item_id": request.active_item_id,
            "message": request.message,
            "profile_revision": profile_record.current_revision,
            "suggested_plan_actions": suggested_actions,
        },
    )
    db.commit()
    return DailyPlanCoachResponse(
        answer=coach_result.answer,
        extracted_profile_signals={
            "weak_points": profile_result.profile.weak_points,
            "learning_pace": profile_result.profile.learning_pace,
            "resource_preference": profile_result.profile.resource_preference,
            "interest_direction": profile_result.profile.interest_direction,
            "mastery": profile_result.profile.mastery,
        },
        suggested_plan_actions=suggested_actions,
        profile_revision=profile_record.current_revision,
        plan=get_daily_plan(db, user, plan.id),
    )


def _daily_plan_coach_result(
    *,
    project: LearningProject,
    plan: DailyLearningPlan,
    active_item: Optional[DailyLearningPlanItem],
    student_message: str,
    profile_summary: str,
    pending_items: list[DailyLearningPlanItem],
) -> "_DailyPlanCoachLLMResult":
    prompt = f"""
你是每日学习计划教练，负责把学生的自然语言复盘转成可执行的下一步建议。

项目：{project.title}
学习目标：{project.learning_goal}
计划：{plan.title}，每日 {plan.daily_minutes} 分钟
当前任务：{active_item.title if active_item else "未指定"}
当前任务重点：{active_item.learning_focus if active_item else ""}
近期待办：{[{"title": item.title, "date": item.planned_date.isoformat(), "minutes": item.estimated_minutes, "status": item.status} for item in pending_items]}
学生原话：{student_message}
画像抽取摘要：{profile_summary}

请输出 JSON：
{{
  "answer": "用 3-5 句话回应学生，明确今天先做什么、如何降低阻力、何时进入课堂或调整计划。",
  "suggested_plan_actions": ["可执行建议1", "可执行建议2", "可执行建议3"]
}}
要求：不要说空话；不要声称已移动计划日期，除非用户另外点击调整按钮；不要生成不存在的课程内容。
"""
    result = qwen_chat_json(
        "你是严谨的 AI 学习计划教练，只输出符合要求的 JSON。",
        prompt,
        _DailyPlanCoachLLMResult,
        user=user,
    )
    return result


class _DailyPlanCoachLLMResult(BaseModel):
    answer: str = Field(min_length=1)
    suggested_plan_actions: list[str] = Field(min_length=1, max_length=4)


def _normalize_daily_plan_order(plan: DailyLearningPlan) -> None:
    grouped_dates = sorted({item.planned_date for item in plan.items})
    day_index_by_date = {planned_date: index for index, planned_date in enumerate(grouped_dates, start=1)}
    for planned_date in grouped_dates:
        day_items = sorted(
            [item for item in plan.items if item.planned_date == planned_date],
            key=lambda item: (item.user_order, item.id),
        )
        for order, item in enumerate(day_items, start=1):
            item.day_index = day_index_by_date[planned_date]
            item.user_order = order


def get_daily_plan(db: Session, user: User, plan_id: int) -> DailyLearningPlan:
    plan = db.scalar(
        select(DailyLearningPlan)
        .options(selectinload(DailyLearningPlan.items))
        .where(DailyLearningPlan.id == plan_id, DailyLearningPlan.user_id == user.id)
    )
    if plan is None:
        raise KeyError("daily plan not found")
    if _sync_daily_plan_item_statuses(db, plan):
        db.commit()
    return plan


def list_daily_plans(db: Session, user: User, project_id: int, limit: int = 3) -> list[DailyLearningPlan]:
    _project_or_404(db, user, project_id)
    plans = list(
        db.scalars(
            select(DailyLearningPlan)
            .options(selectinload(DailyLearningPlan.items))
            .where(DailyLearningPlan.project_id == project_id, DailyLearningPlan.user_id == user.id)
            .order_by(DailyLearningPlan.created_at.desc())
            .limit(max(1, min(limit, 10)))
        )
    )
    for plan in plans:
        if _sync_daily_plan_item_statuses(db, plan):
            db.commit()
    return plans


def _sync_daily_plan_item_statuses(db: Session, plan: DailyLearningPlan) -> bool:
    syllabus_item_ids = [item.syllabus_item_id for item in plan.items if item.syllabus_item_id is not None]
    if not syllabus_item_ids:
        return False
    syllabus_items = {
        item.id: item
        for item in db.scalars(
            select(LearningSyllabusItem).where(LearningSyllabusItem.id.in_(syllabus_item_ids))
        )
    }
    changed = False
    for plan_item in plan.items:
        syllabus_item = syllabus_items.get(plan_item.syllabus_item_id)
        if syllabus_item is None:
            continue
        if syllabus_item.status in {"completed", "mastered", "removed", "deleted", "skipped"} and plan_item.status != syllabus_item.status:
            plan_item.status = "removed" if syllabus_item.status in {"deleted", "skipped"} else syllabus_item.status
            changed = True
        elif plan_item.status == "pending" and syllabus_item.status == "in_progress":
            plan_item.status = "in_progress"
            changed = True
    if changed:
        db.flush()
    return changed
