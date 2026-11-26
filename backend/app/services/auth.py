from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.security import (
    create_access_token,
    decode_access_token,
    dummy_password_hash,
    hash_refresh_token,
    new_refresh_token,
    password_hasher,
    signing_key,
)
from app.models.auth_session import AuthSession
from app.models.user import User, utcnow
from app.repositories import auth as sessions
from app.repositories import users
from app.schemas.auth import Login, TokenResponse
from app.schemas.user import Registration, UserRead


def unauthorized() -> AppError:
    return AppError(401, 40101, "Invalid or expired authentication")


def register(db: Session, payload: Registration) -> User:
    if users.find_duplicate(db, payload.username, str(payload.email)):
        raise AppError(409, 40901, "Username or email already registered")
    try:
        user = users.add_user(
            db,
            username=payload.username,
            email=str(payload.email),
            password_hash=password_hasher.hash(payload.password),
        )
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        db.rollback()
        raise AppError(409, 40901, "Username or email already registered") from None


def token_response(user: User, session_id: str) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(user.id, session_id),
        expires_in=get_settings().access_token_minutes * 60,
        user=UserRead.model_validate(user),
    )


def login(db: Session, payload: Login) -> tuple[TokenResponse, str]:
    signing_key()
    user = users.find_identity(db, payload.username.strip().lower())
    stored_hash = user.password_hash if user else dummy_password_hash()
    valid = password_hasher.verify(payload.password, stored_hash)
    if user is None or not valid:
        raise AppError(401, 40102, "Invalid username or password")
    raw_token = new_refresh_token()
    session = sessions.add_session(
        db,
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(raw_token),
        expires_at=utcnow() + timedelta(days=get_settings().refresh_token_days),
        last_seen_at=utcnow(),
    )
    result = token_response(user, session.id)
    db.commit()
    return result, raw_token


def refresh(db: Session, raw_token: str | None) -> tuple[TokenResponse, str, int]:
    signing_key()
    if not raw_token or len(raw_token) > 256:
        raise unauthorized()
    replacement = new_refresh_token()
    session = sessions.rotate_session(
        db, hash_refresh_token(raw_token), hash_refresh_token(replacement)
    )
    if session is None:
        db.rollback()
        raise unauthorized()
    user = users.get_user(db, session.user_id)
    if user is None:
        db.rollback()
        raise unauthorized()
    result = token_response(user, session.id)
    remaining = max(0, int((session.expires_at - utcnow()).total_seconds()))
    db.commit()
    return result, replacement, remaining


def logout(db: Session, raw_token: str | None) -> None:
    if raw_token and len(raw_token) <= 256:
        sessions.revoke_session(db, hash_refresh_token(raw_token))
        db.commit()


@dataclass(frozen=True)
class AuthIdentity:
    user: User
    session: AuthSession


def current_identity(db: Session, token: str) -> AuthIdentity:
    claims = decode_access_token(token)
    session = sessions.get_session(db, claims["sid"])
    if (
        session is None
        or session.user_id != claims["sub"]
        or session.revoked_at is not None
        or session.expires_at <= utcnow()
    ):
        raise unauthorized()
    user = users.get_user(db, claims["sub"])
    if user is None:
        raise unauthorized()
    return AuthIdentity(user, session)


def current_user(db: Session, token: str) -> User:
    return current_identity(db, token).user
