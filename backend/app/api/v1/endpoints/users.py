from fastapi import APIRouter

from app.api.deps import CurrentIdentity, CurrentUser, DBSession
from app.schemas.admin import PresenceInput, PresenceRead
from app.schemas.common import ApiResponse
from app.schemas.user import UserRead, UserUpdate
from app.services import admin as administration
from app.services.users import update_profile

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=ApiResponse[UserRead])
def me(user: CurrentUser) -> ApiResponse[UserRead]:
    return ApiResponse(data=UserRead.model_validate(user))


@router.patch("/me", response_model=ApiResponse[UserRead])
def update_me(payload: UserUpdate, user: CurrentUser, db: DBSession) -> ApiResponse[UserRead]:
    return ApiResponse(data=UserRead.model_validate(update_profile(db, user, payload)))


@router.post("/me/heartbeat", response_model=ApiResponse[PresenceRead])
def heartbeat(
    identity: CurrentIdentity, db: DBSession, payload: PresenceInput | None = None
) -> ApiResponse[PresenceRead]:
    return ApiResponse(data=administration.heartbeat(db, identity))
