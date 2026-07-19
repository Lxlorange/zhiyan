from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import SessionLocal, get_db
from app.models.learning import LearningProject, LearningProjectEvent
from app.models.user import User
from app.schemas import (
    DailyPlanCoachRequest,
    DailyPlanCoachResponse,
    DailyPlanGenerateRequest,
    DailyPlanMoveItemRequest,
    DailyPlanReorderItemRequest,
    DailyPlanShiftItemRequest,
    DailyPlanRead,
    SyllabusAdaptRequest,
    SyllabusCompareResponse,
    SyllabusEnsureResponse,
    SyllabusGenerateRequest,
    SyllabusItemCreateRequest,
    SyllabusItemRead,
    SyllabusItemSplitRequest,
    SyllabusItemStatusRequest,
    SyllabusItemUpdateRequest,
    SyllabusItemsMergeRequest,
    SyllabusRegenerateStageRequest,
    SyllabusReorderRequest,
    SyllabusVersionRead,
    SyllabusVersionSummary,
)
from app.services.llm_client import LLMConfigurationError, LLMResponseError
from app.services.syllabus_service import (
    activate_syllabus_version,
    adapt_syllabus,
    add_syllabus_item,
    coach_daily_plan,
    compare_syllabus_versions,
    copy_syllabus_version,
    delete_syllabus_item,
    generate_daily_plan,
    get_daily_plan,
    generate_syllabus,
    get_current_syllabus,
    get_syllabus_version,
    list_daily_plans,
    list_syllabus_versions,
    merge_syllabus_items,
    move_daily_plan_item,
    reorder_daily_plan_item,
    regenerate_stage,
    reorder_syllabus_items,
    split_syllabus_item,
    shift_daily_plan_item,
    update_syllabus_item,
    update_syllabus_item_status,
)

router = APIRouter(tags=["syllabus"])


def _background_generate_syllabus(project_id: int, user_id: int, request: SyllabusGenerateRequest) -> None:
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        project = db.get(LearningProject, project_id)
        if user is None or project is None:
            return
        generate_syllabus(db, user, project_id, request)
    except Exception as exc:
        project = db.get(LearningProject, project_id)
        if project is not None:
            project.status = "syllabus_failed"
            project.current_stage = "学习清单生成失败"
            project.next_step = f"{exc.__class__.__name__}: {exc}"
            db.add(
                LearningProjectEvent(
                    project_id=project.id,
                    user_id=user_id,
                    event_type="syllabus_generation_failed",
                    summary="学习清单后台生成失败",
                    payload={"error": f"{exc.__class__.__name__}: {exc}"},
                )
            )
            db.commit()
    finally:
        db.close()


def _handle_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    if isinstance(exc, LLMConfigurationError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, LLMResponseError):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router.post("/learning-projects/{project_id}/syllabus/generate", response_model=SyllabusVersionRead)
def learning_project_syllabus_generate(
    project_id: int,
    request: SyllabusGenerateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyllabusVersionRead:
    try:
        return SyllabusVersionRead.model_validate(generate_syllabus(db, user, project_id, request))
    except (KeyError, ValueError, LLMConfigurationError, LLMResponseError) as exc:
        raise _handle_error(exc) from exc


@router.post("/learning-projects/{project_id}/syllabus/ensure", response_model=SyllabusEnsureResponse)
def learning_project_syllabus_ensure(
    project_id: int,
    background_tasks: BackgroundTasks,
    request: SyllabusGenerateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyllabusEnsureResponse:
    try:
        current = get_current_syllabus(db, user, project_id)
        return SyllabusEnsureResponse(
            state="ready",
            message="学习清单已生成",
            syllabus=SyllabusVersionRead.model_validate(current),
        )
    except KeyError:
        project = db.get(LearningProject, project_id)
        if project is None or project.user_id != user.id:
            raise HTTPException(status_code=404, detail="project not found")
        if project.status == "syllabus_failed":
            return SyllabusEnsureResponse(state="failed", message=project.next_step or "学习清单生成失败")
        if project.status == "syllabus_generating":
            return SyllabusEnsureResponse(state="generating", message="学习清单正在后台生成")

        project.status = "syllabus_generating"
        project.current_stage = "学习清单生成中"
        project.next_step = "系统正在后台生成项目学习清单，请稍后刷新查看。"
        db.add(
            LearningProjectEvent(
                project_id=project.id,
                user_id=user.id,
                event_type="syllabus_generation_started",
                summary="后台开始生成学习清单",
                payload={"generation_goal": request.generation_goal},
            )
        )
        db.commit()
        background_tasks.add_task(_background_generate_syllabus, project_id, user.id, request)
        return SyllabusEnsureResponse(state="started", message="学习清单已进入后台生成队列")


@router.get("/learning-projects/{project_id}/syllabus", response_model=SyllabusVersionRead)
def learning_project_current_syllabus(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyllabusVersionRead:
    try:
        return SyllabusVersionRead.model_validate(get_current_syllabus(db, user, project_id))
    except KeyError as exc:
        raise _handle_error(exc) from exc


@router.get("/learning-projects/{project_id}/syllabus/versions", response_model=list[SyllabusVersionSummary])
def learning_project_syllabus_versions(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[SyllabusVersionSummary]:
    try:
        return [SyllabusVersionSummary.model_validate(version) for version in list_syllabus_versions(db, user, project_id)]
    except KeyError as exc:
        raise _handle_error(exc) from exc


@router.get("/syllabus-versions/{version_id}", response_model=SyllabusVersionRead)
def syllabus_version_detail(
    version_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyllabusVersionRead:
    try:
        return SyllabusVersionRead.model_validate(get_syllabus_version(db, user, version_id))
    except KeyError as exc:
        raise _handle_error(exc) from exc


@router.post("/syllabus-versions/{version_id}/activate", response_model=SyllabusVersionRead)
def syllabus_version_activate(
    version_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyllabusVersionRead:
    try:
        return SyllabusVersionRead.model_validate(activate_syllabus_version(db, user, version_id))
    except KeyError as exc:
        raise _handle_error(exc) from exc


@router.post("/syllabus-versions/{version_id}/copy", response_model=SyllabusVersionRead)
def syllabus_version_copy(
    version_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyllabusVersionRead:
    try:
        return SyllabusVersionRead.model_validate(copy_syllabus_version(db, user, version_id))
    except KeyError as exc:
        raise _handle_error(exc) from exc


@router.get("/syllabus-versions/{base_version_id}/compare/{target_version_id}", response_model=SyllabusCompareResponse)
def syllabus_version_compare(
    base_version_id: int,
    target_version_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyllabusCompareResponse:
    try:
        return compare_syllabus_versions(db, user, base_version_id, target_version_id)
    except KeyError as exc:
        raise _handle_error(exc) from exc


@router.post("/syllabus-versions/{version_id}/items", response_model=SyllabusVersionRead)
def syllabus_item_create(
    version_id: int,
    request: SyllabusItemCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyllabusVersionRead:
    try:
        return SyllabusVersionRead.model_validate(add_syllabus_item(db, user, version_id, request))
    except (KeyError, ValueError) as exc:
        raise _handle_error(exc) from exc


@router.patch("/syllabus-items/{item_id}", response_model=SyllabusVersionRead)
def syllabus_item_update(
    item_id: int,
    request: SyllabusItemUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyllabusVersionRead:
    try:
        return SyllabusVersionRead.model_validate(update_syllabus_item(db, user, item_id, request))
    except (KeyError, ValueError) as exc:
        raise _handle_error(exc) from exc


@router.delete("/syllabus-items/{item_id}", status_code=204)
def syllabus_item_delete(
    item_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    try:
        delete_syllabus_item(db, user, item_id)
        return Response(status_code=204)
    except (KeyError, ValueError) as exc:
        raise _handle_error(exc) from exc


@router.post("/syllabus-versions/{version_id}/reorder", response_model=SyllabusVersionRead)
def syllabus_items_reorder(
    version_id: int,
    request: SyllabusReorderRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyllabusVersionRead:
    try:
        return SyllabusVersionRead.model_validate(reorder_syllabus_items(db, user, version_id, request))
    except KeyError as exc:
        raise _handle_error(exc) from exc


@router.post("/syllabus-items/{item_id}/status", response_model=SyllabusVersionRead)
def syllabus_item_status_update(
    item_id: int,
    request: SyllabusItemStatusRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyllabusVersionRead:
    try:
        return SyllabusVersionRead.model_validate(update_syllabus_item_status(db, user, item_id, request))
    except KeyError as exc:
        raise _handle_error(exc) from exc


@router.post("/syllabus-items/{item_id}/split", response_model=SyllabusVersionRead)
def syllabus_item_split(
    item_id: int,
    request: SyllabusItemSplitRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyllabusVersionRead:
    try:
        return SyllabusVersionRead.model_validate(split_syllabus_item(db, user, item_id, request))
    except (KeyError, ValueError) as exc:
        raise _handle_error(exc) from exc


@router.post("/syllabus-items/merge", response_model=SyllabusVersionRead)
def syllabus_items_merge(
    request: SyllabusItemsMergeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyllabusVersionRead:
    try:
        return SyllabusVersionRead.model_validate(merge_syllabus_items(db, user, request))
    except (KeyError, ValueError) as exc:
        raise _handle_error(exc) from exc


@router.post("/syllabus-versions/{version_id}/regenerate-stage", response_model=SyllabusVersionRead)
def syllabus_stage_regenerate(
    version_id: int,
    request: SyllabusRegenerateStageRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyllabusVersionRead:
    try:
        return SyllabusVersionRead.model_validate(regenerate_stage(db, user, version_id, request))
    except (KeyError, ValueError, LLMConfigurationError, LLMResponseError) as exc:
        raise _handle_error(exc) from exc


@router.post("/learning-projects/{project_id}/syllabus/adapt", response_model=SyllabusVersionRead)
def learning_project_syllabus_adapt(
    project_id: int,
    request: SyllabusAdaptRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyllabusVersionRead:
    try:
        return SyllabusVersionRead.model_validate(adapt_syllabus(db, user, project_id, request))
    except (KeyError, ValueError, LLMConfigurationError, LLMResponseError) as exc:
        raise _handle_error(exc) from exc


@router.post("/learning-projects/{project_id}/daily-plan/generate", response_model=DailyPlanRead)
def learning_project_daily_plan_generate(
    project_id: int,
    request: DailyPlanGenerateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyPlanRead:
    try:
        return DailyPlanRead.model_validate(generate_daily_plan(db, user, project_id, request))
    except (KeyError, ValueError) as exc:
        raise _handle_error(exc) from exc


@router.get("/learning-projects/{project_id}/daily-plans", response_model=list[DailyPlanRead])
def learning_project_daily_plans(
    project_id: int,
    limit: int = 3,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DailyPlanRead]:
    try:
        return [DailyPlanRead.model_validate(plan) for plan in list_daily_plans(db, user, project_id, limit=limit)]
    except KeyError as exc:
        raise _handle_error(exc) from exc


@router.get("/daily-plans/{plan_id}", response_model=DailyPlanRead)
def daily_plan_detail(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyPlanRead:
    try:
        return DailyPlanRead.model_validate(get_daily_plan(db, user, plan_id))
    except KeyError as exc:
        raise _handle_error(exc) from exc


@router.patch("/daily-plan-items/{item_id}/schedule", response_model=DailyPlanRead)
def daily_plan_item_schedule_update(
    item_id: int,
    request: DailyPlanMoveItemRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyPlanRead:
    try:
        return DailyPlanRead.model_validate(move_daily_plan_item(db, user, item_id, request))
    except (KeyError, ValueError) as exc:
        raise _handle_error(exc) from exc


@router.patch("/daily-plan-items/{item_id}/shift", response_model=DailyPlanRead)
def daily_plan_item_shift(
    item_id: int,
    request: DailyPlanShiftItemRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyPlanRead:
    try:
        return DailyPlanRead.model_validate(shift_daily_plan_item(db, user, item_id, request))
    except (KeyError, ValueError) as exc:
        raise _handle_error(exc) from exc


@router.patch("/daily-plan-items/{item_id}/reorder", response_model=DailyPlanRead)
def daily_plan_item_reorder(
    item_id: int,
    request: DailyPlanReorderItemRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyPlanRead:
    try:
        return DailyPlanRead.model_validate(reorder_daily_plan_item(db, user, item_id, request))
    except (KeyError, ValueError) as exc:
        raise _handle_error(exc) from exc


@router.post("/daily-plans/{plan_id}/coach", response_model=DailyPlanCoachResponse)
def daily_plan_coach(
    plan_id: int,
    request: DailyPlanCoachRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DailyPlanCoachResponse:
    try:
        return coach_daily_plan(db, user, plan_id, request)
    except (KeyError, ValueError, LLMConfigurationError, LLMResponseError) as exc:
        raise _handle_error(exc) from exc
