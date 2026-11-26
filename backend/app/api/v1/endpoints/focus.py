from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DBSession
from app.schemas.common import ApiResponse
from app.schemas.focus import FocusCreate, FocusPage, FocusRead
from app.services import focus

router = APIRouter(prefix="/focus", tags=["focus"])


@router.get("/current", response_model=ApiResponse[FocusRead | None])
def current(user: CurrentUser, db: DBSession):
    return ApiResponse(data=focus.current(db, user))


@router.get("/sessions", response_model=ApiResponse[FocusPage])
def history(
    user: CurrentUser,
    db: DBSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 10,
):
    return ApiResponse(data=focus.list_sessions(db, user, page, page_size))


@router.post("/sessions", status_code=201, response_model=ApiResponse[FocusRead])
def start(payload: FocusCreate, user: CurrentUser, db: DBSession):
    return ApiResponse(data=focus.start(db, user, payload))


@router.post("/sessions/{session_id}/{action}", response_model=ApiResponse[FocusRead])
def transition(
    session_id: str,
    action: Literal["pause", "resume", "finish", "cancel"],
    user: CurrentUser,
    db: DBSession,
):
    return ApiResponse(data=focus.transition(db, user, session_id, action))
