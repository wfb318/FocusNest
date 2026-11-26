from typing import Annotated, Literal

from fastapi import APIRouter, Query

from app.api.deps import AdminUser, DBSession
from app.schemas.admin import AdminOverview, AdminUserPage
from app.schemas.common import ApiResponse
from app.services import admin as service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/overview", response_model=ApiResponse[AdminOverview])
def overview(user: AdminUser, db: DBSession):
    return ApiResponse(data=service.overview(db, user))


@router.get("/users", response_model=ApiResponse[AdminUserPage])
def list_users(
    user: AdminUser,
    db: DBSession,
    page: Annotated[int, Query(ge=1, le=100000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    search: Annotated[str, Query(max_length=100)] = "",
    role: Literal["user", "admin"] | None = None,
    online: bool | None = None,
):
    return ApiResponse(data=service.list_users(db, page, page_size, search, role, online))
