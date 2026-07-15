import json

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import SessionLocal, get_db
from app.models.user import User
from app.schemas import (
    DirectionAnalyzeRequest,
    DirectionAnalyzeResponse,
    DirectionCreateRequest,
    DirectionDashboardResponse,
    DirectionReviewRequest,
    DirectionTemplateCreateRequest,
    DirectionTemplateRead,
    LearningProjectCreateRequest,
    LearningProjectExportResponse,
    LearningProjectHomeResponse,
    LearningProjectRead,
    LearningProjectUpdateRequest,
    ProjectPlanAdjustRequest,
    ProjectPlanBuildResponse,
    ProjectPlanRead,
    ProjectPlanRequest,
    ResearchDirectionRead,
)
from app.services.direction_service import (
    analyze_direction,
    archive_project,
    build_direction_dashboard,
    copy_project,
    create_direction,
    create_direction_template,
    create_project,
    export_project,
    get_direction_or_404,
    get_project_or_404,
    list_direction_templates,
    list_directions,
    list_projects,
    pause_project,
    project_home,
    regenerate_direction,
    request_project_syllabus_regeneration,
    review_direction,
    resume_project,
    share_project,
    update_project,
)
from app.services.llm_client import LLMConfigurationError, LLMResponseError
from app.services.attachment_service import AttachmentParseError, ParsedAttachment, parse_project_plan_attachment
from app.services.project_plan_service import (
    adjust_project_plan,
    build_project_from_plan,
    create_project_plan,
    stream_adjust_project_plan,
    stream_create_project_plan,
)

router = APIRouter(tags=["directions"])


def _handle_ai_error(exc: Exception) -> HTTPException:
    if isinstance(exc, LLMConfigurationError):
        return HTTPException(status_code=503, detail=str(exc))
    if isinstance(exc, LLMResponseError):
        return HTTPException(status_code=502, detail=str(exc))
    return HTTPException(status_code=500, detail=str(exc))


@router.get("/direction-templates", response_model=list[DirectionTemplateRead])
def direction_templates(db: Session = Depends(get_db)) -> list[DirectionTemplateRead]:
    return list_direction_templates(db)


@router.post("/directions/analyze", response_model=DirectionAnalyzeResponse)
def direction_analyze(
    request: DirectionAnalyzeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DirectionAnalyzeResponse:
    try:
        return analyze_direction(db, request, user)
    except (LLMConfigurationError, LLMResponseError) as exc:
        raise _handle_ai_error(exc) from exc


@router.post("/project-plans", response_model=ProjectPlanRead)
def project_plan_create(
    request: ProjectPlanRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectPlanRead:
    try:
        return create_project_plan(db, user, request)
    except (LLMConfigurationError, LLMResponseError) as exc:
        raise _handle_ai_error(exc) from exc


@router.post("/project-plans/attachments/parse", response_model=ParsedAttachment)
async def project_plan_attachment_parse(
    file: UploadFile,
    user: User = Depends(get_current_user),
) -> ParsedAttachment:
    try:
        return await parse_project_plan_attachment(file)
    except AttachmentParseError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/project-plans/stream")
def project_plan_stream(
    request: ProjectPlanRequest,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    def event_stream():
        stream_db = SessionLocal()
        try:
            for item in stream_create_project_plan(stream_db, user, request):
                yield f"event: {item['event']}\n"
                yield f"data: {json.dumps(item['data'], ensure_ascii=False)}\n\n"
        except LLMConfigurationError as exc:
            yield "event: error\n"
            yield f"data: {json.dumps({'status': 503, 'detail': str(exc)}, ensure_ascii=False)}\n\n"
        except LLMResponseError as exc:
            yield "event: error\n"
            yield f"data: {json.dumps({'status': 502, 'detail': str(exc)}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield "event: error\n"
            yield f"data: {json.dumps({'status': 500, 'detail': str(exc)}, ensure_ascii=False)}\n\n"
        finally:
            stream_db.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/project-plans/{plan_id}/messages", response_model=ProjectPlanRead)
def project_plan_adjust(
    plan_id: int,
    request: ProjectPlanAdjustRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectPlanRead:
    try:
        return adjust_project_plan(db, user, plan_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project plan not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (LLMConfigurationError, LLMResponseError) as exc:
        raise _handle_ai_error(exc) from exc


@router.post("/project-plans/{plan_id}/messages/stream")
def project_plan_adjust_stream(
    plan_id: int,
    request: ProjectPlanAdjustRequest,
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    def event_stream():
        stream_db = SessionLocal()
        try:
            for item in stream_adjust_project_plan(stream_db, user, plan_id, request):
                yield f"event: {item['event']}\n"
                yield f"data: {json.dumps(item['data'], ensure_ascii=False)}\n\n"
        except KeyError:
            yield "event: error\n"
            yield f"data: {json.dumps({'status': 404, 'detail': 'project plan not found'}, ensure_ascii=False)}\n\n"
        except ValueError as exc:
            yield "event: error\n"
            yield f"data: {json.dumps({'status': 409, 'detail': str(exc)}, ensure_ascii=False)}\n\n"
        except LLMConfigurationError as exc:
            yield "event: error\n"
            yield f"data: {json.dumps({'status': 503, 'detail': str(exc)}, ensure_ascii=False)}\n\n"
        except LLMResponseError as exc:
            yield "event: error\n"
            yield f"data: {json.dumps({'status': 502, 'detail': str(exc)}, ensure_ascii=False)}\n\n"
        except Exception as exc:
            yield "event: error\n"
            yield f"data: {json.dumps({'status': 500, 'detail': str(exc)}, ensure_ascii=False)}\n\n"
        finally:
            stream_db.close()

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/project-plans/{plan_id}/build", response_model=ProjectPlanBuildResponse)
def project_plan_build(
    plan_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProjectPlanBuildResponse:
    try:
        return build_project_from_plan(db, user, plan_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/direction-templates", response_model=DirectionTemplateRead)
def direction_template_create(
    request: DirectionTemplateCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DirectionTemplateRead:
    if user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="teacher or admin role required")
    try:
        return create_direction_template(db, user, request)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/directions", response_model=ResearchDirectionRead)
def direction_create(
    request: DirectionCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchDirectionRead:
    try:
        direction = create_direction(db, user, DirectionAnalyzeRequest(**request.model_dump()))
        return ResearchDirectionRead.model_validate(direction)
    except (LLMConfigurationError, LLMResponseError) as exc:
        raise _handle_ai_error(exc) from exc


@router.get("/directions", response_model=list[ResearchDirectionRead])
def directions(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ResearchDirectionRead]:
    return list_directions(db, user)


@router.get("/directions/{direction_id}", response_model=ResearchDirectionRead)
def direction_detail(
    direction_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchDirectionRead:
    try:
        return ResearchDirectionRead.model_validate(get_direction_or_404(db, user, direction_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="direction not found") from exc


@router.post("/directions/{direction_id}/regenerate", response_model=ResearchDirectionRead)
def direction_regenerate(
    direction_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchDirectionRead:
    try:
        return ResearchDirectionRead.model_validate(regenerate_direction(db, user, direction_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="direction not found") from exc
    except (LLMConfigurationError, LLMResponseError) as exc:
        raise _handle_ai_error(exc) from exc


@router.post("/directions/{direction_id}/review", response_model=ResearchDirectionRead)
def direction_review(
    direction_id: int,
    request: DirectionReviewRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchDirectionRead:
    if user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="teacher or admin role required")
    try:
        return ResearchDirectionRead.model_validate(review_direction(db, user, direction_id, request))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="direction not found") from exc


@router.post("/learning-projects", response_model=LearningProjectRead)
def learning_project_create(
    request: LearningProjectCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningProjectRead:
    try:
        return LearningProjectRead.model_validate(create_project(db, user, request))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="direction not found") from exc


@router.get("/learning-projects", response_model=list[LearningProjectRead])
def learning_projects(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[LearningProjectRead]:
    return list_projects(db, user)


@router.get("/learning-projects/{project_id}", response_model=LearningProjectRead)
def learning_project_detail(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningProjectRead:
    try:
        return LearningProjectRead.model_validate(get_project_or_404(db, user, project_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project not found") from exc


@router.get("/learning-projects/{project_id}/home", response_model=LearningProjectHomeResponse)
def learning_project_home(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningProjectHomeResponse:
    try:
        return project_home(db, user, project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project not found") from exc


@router.patch("/learning-projects/{project_id}", response_model=LearningProjectRead)
def learning_project_update(
    project_id: int,
    request: LearningProjectUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningProjectRead:
    try:
        return LearningProjectRead.model_validate(update_project(db, user, project_id, request))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project not found") from exc


@router.post("/learning-projects/{project_id}/archive", response_model=LearningProjectRead)
def learning_project_archive(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningProjectRead:
    try:
        return LearningProjectRead.model_validate(archive_project(db, user, project_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project not found") from exc


@router.post("/learning-projects/{project_id}/pause", response_model=LearningProjectRead)
def learning_project_pause(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningProjectRead:
    try:
        return LearningProjectRead.model_validate(pause_project(db, user, project_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project not found") from exc


@router.post("/learning-projects/{project_id}/resume", response_model=LearningProjectRead)
def learning_project_resume(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningProjectRead:
    try:
        return LearningProjectRead.model_validate(resume_project(db, user, project_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project not found") from exc


@router.post("/learning-projects/{project_id}/request-syllabus-regeneration", response_model=LearningProjectRead)
def learning_project_request_syllabus_regeneration(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningProjectRead:
    try:
        return LearningProjectRead.model_validate(request_project_syllabus_regeneration(db, user, project_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project not found") from exc


@router.post("/learning-projects/{project_id}/copy", response_model=LearningProjectRead)
def learning_project_copy(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningProjectRead:
    try:
        return LearningProjectRead.model_validate(copy_project(db, user, project_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project not found") from exc


@router.get("/teacher/direction-dashboard", response_model=DirectionDashboardResponse)
def teacher_direction_dashboard(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DirectionDashboardResponse:
    if user.role not in {"teacher", "admin"}:
        raise HTTPException(status_code=403, detail="teacher or admin role required")
    return build_direction_dashboard(db)


@router.post("/learning-projects/{project_id}/share", response_model=LearningProjectRead)
def learning_project_share(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningProjectRead:
    try:
        return LearningProjectRead.model_validate(share_project(db, user, project_id))
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project not found") from exc


@router.get("/learning-projects/{project_id}/export", response_model=LearningProjectExportResponse)
def learning_project_export(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LearningProjectExportResponse:
    try:
        return export_project(db, user, project_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="project not found") from exc
