from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas import UserModelSettingsRead, UserModelSettingsUpdate
from app.services.llm_client import LLMConfigurationError, LLMResponseError
from app.services.system_settings_service import (
    get_user_model_settings,
    update_user_model_settings,
    verify_user_model_settings,
)

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/model-settings", response_model=UserModelSettingsRead)
def model_settings(user: User = Depends(get_current_user)) -> UserModelSettingsRead:
    return get_user_model_settings(user)


@router.put("/model-settings", response_model=UserModelSettingsRead)
def model_settings_update(
    request: UserModelSettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserModelSettingsRead:
    try:
        return update_user_model_settings(db, user, request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/model-settings/verify")
def model_settings_verify(user: User = Depends(get_current_user)) -> dict[str, str | bool]:
    try:
        return verify_user_model_settings(user)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
