from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas import (
    LiteraturePaperCreateRequest,
    LiteraturePaperRead,
    LiteraturePaperSuggestRequest,
    LiteraturePaperSuggestResponse,
    LiteraturePaperUpdateRequest,
    ProfileCenterResponse,
    ProfileEntryUpdateRequest,
    ResearchToolRunRead,
    ResearchToolRunRequest,
    WorkspaceOverviewResponse,
)
from app.services.llm_client import LLMConfigurationError, LLMResponseError
from app.services.workspace_service import (
    create_literature,
    delete_profile_entry,
    get_profile_center,
    get_workspace_overview,
    list_literature,
    list_tool_runs,
    suggest_literature_metadata,
    run_research_tool,
    update_literature,
    update_profile_entry,
)

router = APIRouter(prefix="/workspace", tags=["workspace"])


@router.get("/overview", response_model=WorkspaceOverviewResponse)
def workspace_overview(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkspaceOverviewResponse:
    return get_workspace_overview(db, user)


@router.get("/profile", response_model=ProfileCenterResponse)
def profile_center(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileCenterResponse:
    return get_profile_center(db, user)


@router.patch("/profile/entries", response_model=ProfileCenterResponse)
def profile_entry_update(
    request: ProfileEntryUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileCenterResponse:
    return update_profile_entry(db, user, request)


@router.delete("/profile/entries/{key}", response_model=ProfileCenterResponse)
def profile_entry_delete(
    key: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileCenterResponse:
    try:
        return delete_profile_entry(db, user, key)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/literature", response_model=list[LiteraturePaperRead])
def literature_list(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[LiteraturePaperRead]:
    return list_literature(db, user)


@router.post("/literature", response_model=LiteraturePaperRead)
def literature_create(
    request: LiteraturePaperCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LiteraturePaperRead:
    return create_literature(db, user, request)


@router.post("/literature/suggest", response_model=LiteraturePaperSuggestResponse)
def literature_suggest(
    request: LiteraturePaperSuggestRequest,
) -> LiteraturePaperSuggestResponse:
    return suggest_literature_metadata(request)


@router.patch("/literature/{paper_id}", response_model=LiteraturePaperRead)
def literature_update(
    paper_id: int,
    request: LiteraturePaperUpdateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LiteraturePaperRead:
    try:
        return update_literature(db, user, paper_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/research-tools/runs", response_model=list[ResearchToolRunRead])
def research_tool_runs(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ResearchToolRunRead]:
    return list_tool_runs(db, user)


@router.post("/research-tools/run", response_model=ResearchToolRunRead)
def research_tool_run(
    request: ResearchToolRunRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ResearchToolRunRead:
    try:
        return run_research_tool(db, user, request)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
