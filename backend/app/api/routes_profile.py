from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas import ProfileDialogueResponse, ProfileRequest
from app.services.ai_workflow import create_profile
from app.services.llm_client import LLMConfigurationError, LLMResponseError
from app.services.persistence_service import build_profile_dialogue_response

router = APIRouter(prefix="/profile", tags=["profile"])


def _extract_features(message: str, profile) -> dict:
    return {
        "message_length": len(message),
        "knowledge_base": profile.knowledge_base,
        "learning_goal": profile.learning_goal,
        "cognitive_style": profile.cognitive_style,
        "weak_points": profile.weak_points,
        "practice_level": profile.practice_level,
        "resource_preference": profile.resource_preference,
        "learning_pace": profile.learning_pace,
        "interest_direction": profile.interest_direction,
        "mastery": profile.mastery,
    }


@router.post("/dialogue", response_model=ProfileDialogueResponse)
def dialogue_profile(
    request: ProfileRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProfileDialogueResponse:
    try:
        profile = create_profile(request.message)
    except LLMConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except LLMResponseError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    update_reason = (
        "已通过千问模型从本次自然语言对话中实时抽取画像维度，并生成新的动态画像版本。"
    )
    return build_profile_dialogue_response(
        db=db,
        user=user,
        profile=profile,
        update_reason=update_reason,
        extracted_features=_extract_features(request.message, profile),
    )
