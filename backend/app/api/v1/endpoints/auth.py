from fastapi import APIRouter, Depends, Request, Response

from app.api.deps import DBSession, require_trusted_origin
from app.core.config import get_settings
from app.schemas.auth import Login, TokenResponse
from app.schemas.common import ApiResponse
from app.schemas.user import Registration, UserRead
from app.services import auth

router = APIRouter(prefix="/auth", tags=["auth"], dependencies=[Depends(require_trusted_origin)])
COOKIE_NAME = "focusnest_refresh"
COOKIE_PATH = "/api/v1/auth"


def set_refresh_cookie(response: Response, token: str, max_age: int) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=max_age,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="strict",
        path=COOKIE_PATH,
    )
    response.headers["Cache-Control"] = "no-store"


@router.post("/register", status_code=201, response_model=ApiResponse[UserRead])
def register(payload: Registration, db: DBSession) -> ApiResponse[UserRead]:
    return ApiResponse(data=UserRead.model_validate(auth.register(db, payload)))


@router.post("/login", response_model=ApiResponse[TokenResponse])
def login(payload: Login, response: Response, db: DBSession) -> ApiResponse[TokenResponse]:
    result, refresh_token = auth.login(db, payload)
    set_refresh_cookie(response, refresh_token, get_settings().refresh_token_days * 86400)
    return ApiResponse(data=result)


@router.post("/refresh", response_model=ApiResponse[TokenResponse])
def refresh(request: Request, response: Response, db: DBSession) -> ApiResponse[TokenResponse]:
    result, refresh_token, remaining = auth.refresh(db, request.cookies.get(COOKIE_NAME))
    set_refresh_cookie(response, refresh_token, remaining)
    return ApiResponse(data=result)


@router.post("/logout", response_model=ApiResponse[None])
def logout(request: Request, response: Response, db: DBSession) -> ApiResponse[None]:
    auth.logout(db, request.cookies.get(COOKIE_NAME))
    response.delete_cookie(
        COOKIE_NAME,
        path=COOKIE_PATH,
        httponly=True,
        secure=get_settings().cookie_secure,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
    return ApiResponse(message="Logged out")
