from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas import TokenResponse, UserCreate, UserLogin, UserRead, UserUpdate
from app.services.auth_service import authenticate_user, create_access_token, create_user, update_user_profile

router = APIRouter(prefix="/auth", tags=["auth"])

AVATAR_UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads" / "avatars"
MAX_AVATAR_BYTES = 5 * 1024 * 1024
ALLOWED_AVATAR_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


@router.post("/register", response_model=TokenResponse)
def register(payload: UserCreate, db: Session = Depends(get_db)) -> TokenResponse:
    try:
        user = create_user(db, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return TokenResponse(access_token=create_access_token(user), user=UserRead.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.username, payload.password)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid username or password")
    return TokenResponse(access_token=create_access_token(user), user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead)
def me(current_user: User = Depends(get_current_user)) -> UserRead:
    return UserRead.model_validate(current_user)


@router.patch("/me", response_model=UserRead)
def update_me(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserRead:
    try:
        user = update_user_profile(db, current_user, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return UserRead.model_validate(user)


@router.post("/me/avatar", response_model=UserRead)
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> UserRead:
    content_type = (file.content_type or "").lower()
    extension = ALLOWED_AVATAR_TYPES.get(content_type)
    if extension is None:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="仅支持 JPG、PNG 或 WebP 图片。")

    content = await file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="头像文件为空。")
    if len(content) > MAX_AVATAR_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="头像图片不能超过 5MB。")

    AVATAR_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"user-{current_user.id}-{uuid4().hex}{extension}"
    target = AVATAR_UPLOAD_DIR / filename
    target.write_bytes(content)

    current_user.avatar_url = f"/uploads/avatars/{filename}"
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return UserRead.model_validate(current_user)
