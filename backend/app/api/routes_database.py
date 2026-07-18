from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas import DatabaseAskRequest, DatabaseAskResponse, DatabaseGraphResponse, DatabaseNodeDetailResponse, KnowledgeLinkGraphResponse
from app.services.database_service import (
    ask_database,
    build_database_graph,
    get_chunk_review,
    get_database_node_detail,
    get_document_review,
)
from app.services.knowledge_ingestion_service import KnowledgeIngestionError
from app.services.llm_client import LLMConfigurationError, LLMResponseError
from app.services.taxonomy_service import build_knowledge_link_graph

router = APIRouter(prefix="/database", tags=["database"])


@router.post("/ask", response_model=DatabaseAskResponse)
def database_ask(
    request: DatabaseAskRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DatabaseAskResponse:
    try:
        return ask_database(db, user, request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except KnowledgeIngestionError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/graph", response_model=DatabaseGraphResponse)
def database_graph(
    project_id: Optional[int] = Query(default=None),
    scope: str = Query(default="all", pattern="^(all|project)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DatabaseGraphResponse:
    try:
        return build_database_graph(db, user, project_id=project_id, scope=scope)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/knowledge-links", response_model=KnowledgeLinkGraphResponse)
def database_knowledge_links(
    project_id: Optional[int] = Query(default=None),
    query: str = Query(default=""),
    limit: int = Query(default=140, ge=40, le=220),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> KnowledgeLinkGraphResponse:
    try:
        return build_knowledge_link_graph(db, user, project_id=project_id, query=query, limit=limit)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/nodes/{name}", response_model=DatabaseNodeDetailResponse)
def database_node_detail(
    name: str,
    project_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DatabaseNodeDetailResponse:
    try:
        return get_database_node_detail(db, user, name, project_id=project_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/documents/{document_id}/review")
def database_document_review(
    document_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        return get_document_review(db, user, document_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/chunks/{chunk_id}/review")
def database_chunk_review(
    chunk_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        return get_chunk_review(db, user, chunk_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
