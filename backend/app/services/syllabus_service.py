from __future__ import annotations

import time
from datetime import datetime
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
    DailyPlanGenerateRequest,
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
from app.services.knowledge_service import COURSE_CODE, search_knowledge
from app.services.llm_client import qwen_chat_json


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


def _knowledge_context(db: Session, project: LearningProject) -> list[dict]:
    query = " ".join(
        [
            project.research_direction,
            project.learning_goal,
            " ".join(project.related_knowledge_points or []),
        ]
    )
    return [hit.model_dump() for hit in search_knowledge(db, query, limit=10)]


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
        knowledge_base_version=COURSE_CODE,
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
    project.next_step = "进入学习路径页，调整清单并生成每日计划"
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
    item.status = request.status
    project = _project_or_404(db, user, item.project_id)
    if request.status in {"completed", "mastered"}:
        project.completed_item_count = db.scalar(
            select(func.count(LearningSyllabusItem.id)).where(
                LearningSyllabusItem.project_id == project.id,
                LearningSyllabusItem.user_id == user.id,
                LearningSyllabusItem.status.in_(["completed", "mastered"]),
            )
        ) or project.completed_item_count
        project.last_learned_at = datetime.utcnow()
    _log_operation(
        db,
        version=version,
        user=user,
        operation_type=f"mark_{request.status}",
        summary=f"标记“{item.title}”为 {request.status}",
        payload={"reason": request.reason},
        item_id=item.id,
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
    active_items = [item for item in version.items if item.status not in {"deleted", "skipped", "merged", "split"}]
    plan = DailyLearningPlan(
        project_id=project.id,
        syllabus_version_id=version.id,
        user_id=user.id,
        title=request.title or f"{project.title} 每日学习计划",
        start_date=request.start_date or datetime.utcnow(),
        daily_minutes=daily_minutes,
        generation_reason=f"按当前清单 v{version.version_no} 与每日 {daily_minutes} 分钟拆分",
    )
    db.add(plan)
    db.flush()
    day_index = 1
    used_minutes = 0
    order_in_day = 1
    for item in active_items:
        if used_minutes > 0 and used_minutes + item.estimated_minutes > daily_minutes:
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
                title=item.title,
                estimated_minutes=item.estimated_minutes,
                learning_focus=item.objective,
                resource_types=item.recommended_resource_types,
                user_order=order_in_day,
            )
        )
        used_minutes += item.estimated_minutes
        order_in_day += 1
    _log_operation(
        db,
        version=version,
        user=user,
        operation_type="generate_daily_plan",
        summary=f"生成每日计划：{plan.title}",
        payload={"daily_minutes": daily_minutes, "item_count": len(active_items)},
    )
    project.status = "daily_plan_ready"
    project.current_stage = "每日计划已生成"
    project.next_step = "按每日计划进入课堂学习"
    db.commit()
    db.refresh(plan)
    return get_daily_plan(db, user, plan.id)


def get_daily_plan(db: Session, user: User, plan_id: int) -> DailyLearningPlan:
    plan = db.scalar(
        select(DailyLearningPlan)
        .options(selectinload(DailyLearningPlan.items))
        .where(DailyLearningPlan.id == plan_id, DailyLearningPlan.user_id == user.id)
    )
    if plan is None:
        raise KeyError("daily plan not found")
    return plan


def list_daily_plans(db: Session, user: User, project_id: int) -> list[DailyLearningPlan]:
    _project_or_404(db, user, project_id)
    return list(
        db.scalars(
            select(DailyLearningPlan)
            .options(selectinload(DailyLearningPlan.items))
            .where(DailyLearningPlan.project_id == project_id, DailyLearningPlan.user_id == user.id)
            .order_by(DailyLearningPlan.created_at.desc())
        )
    )
