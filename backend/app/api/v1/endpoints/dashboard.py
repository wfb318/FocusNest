from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession
from app.schemas.common import ApiResponse
from app.schemas.dashboard import DashboardRead
from app.services.dashboard import overview

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("", response_model=ApiResponse[DashboardRead])
def read_dashboard(user: CurrentUser, db: DBSession, include_journal: bool = False):
    return ApiResponse(data=overview(db, user, include_journal=include_journal))
