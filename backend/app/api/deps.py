from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.db.session import get_db
from app.models.user import User
from app.services.auth import AuthIdentity, current_identity, current_user, unauthorized

DBSession = Annotated[Session, Depends(get_db)]
bearer = HTTPBearer(auto_error=False)


def get_current_user(
    db: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if credentials is None:
        raise unauthorized()
    return current_user(db, credentials.credentials)


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_identity(
    db: DBSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AuthIdentity:
    if credentials is None:
        raise unauthorized()
    return current_identity(db, credentials.credentials)


CurrentIdentity = Annotated[AuthIdentity, Depends(get_current_identity)]


def get_admin_user(user: CurrentUser) -> User:
    if user.role != "admin":
        raise AppError(403, 40340, "Administrator access is required")
    return user


AdminUser = Annotated[User, Depends(get_admin_user)]


def require_trusted_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin not in {*get_settings().cors_origins, str(request.base_url).rstrip("/")}:
        raise AppError(403, 40301, "Untrusted request origin")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise AppError(403, 40301, "Cross-site authentication is not allowed")
