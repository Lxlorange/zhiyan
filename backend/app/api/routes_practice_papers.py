from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas import (
    PracticeKnowledgeNodeRead,
    PracticePaperCreateRequest,
    PracticePaperRead,
    PracticePaperSubmitRequest,
    PracticePaperSubmitResponse,
)
from app.services.llm_client import LLMConfigurationError, LLMResponseError
from app.services.practice_paper_service import (
    create_practice_paper,
    delete_practice_paper,
    get_practice_paper,
    list_practice_knowledge_nodes,
    list_practice_papers,
    submit_practice_paper,
)

router = APIRouter(prefix="/practice-papers", tags=["practice-papers"])


@router.get("", response_model=list[PracticePaperRead])
def practice_paper_list(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PracticePaperRead]:
    return list_practice_papers(db, user)


@router.get("/knowledge-nodes", response_model=list[PracticeKnowledgeNodeRead])
def practice_knowledge_nodes(
    project_id: Optional[int] = Query(default=None),
    query: str = Query(default=""),
    limit: int = Query(default=120, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[PracticeKnowledgeNodeRead]:
    return list_practice_knowledge_nodes(db, user, project_id=project_id, query=query, limit=limit)


@router.post("", response_model=PracticePaperRead)
def practice_paper_create(
    request: PracticePaperCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PracticePaperRead:
    try:
        return create_practice_paper(db, user, request)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/{paper_id}", response_model=PracticePaperRead)
def practice_paper_detail(
    paper_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PracticePaperRead:
    try:
        return get_practice_paper(db, user, paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{paper_id}/submit", response_model=PracticePaperSubmitResponse)
def practice_paper_submit(
    paper_id: int,
    request: PracticePaperSubmitRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PracticePaperSubmitResponse:
    try:
        return submit_practice_paper(db, user, paper_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.delete("/{paper_id}", response_model=None)
def practice_paper_delete(
    paper_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    try:
        delete_practice_paper(db, user, paper_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
