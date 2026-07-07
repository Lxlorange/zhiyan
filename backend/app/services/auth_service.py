from datetime import datetime, timedelta
from typing import Optional

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.user import User
from app.schemas import UserCreate


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_user_by_identity(db: Session, identity: str) -> Optional[User]:
    stmt = select(User).where(or_(User.username == identity, User.email == identity))
    return db.execute(stmt).scalar_one_or_none()


def create_user(db: Session, payload: UserCreate) -> User:
    existing = get_user_by_identity(db, payload.username) or get_user_by_identity(db, payload.email)
    if existing:
        raise ValueError("username or email already exists")

    user = User(
        username=payload.username,
        email=str(payload.email),
        full_name=payload.full_name,
        role=payload.role,
        hashed_password=hash_password(payload.password),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    user = get_user_by_identity(db, username)
    if not user or not user.is_active:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(user: User) -> str:
    settings = get_settings()
    expire = datetime.utcnow() + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {
        "sub": str(user.id),
        "username": user.username,
        "role": user.role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.get(User, user_id)


def resolve_token_user(db: Session, token: str) -> Optional[User]:
    try:
        payload = decode_access_token(token)
        user_id = int(payload.get("sub", "0"))
    except (JWTError, ValueError):
        return None
    return get_user_by_id(db, user_id)
