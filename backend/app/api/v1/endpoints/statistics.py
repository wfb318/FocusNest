from datetime import date

from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession
from app.schemas.common import ApiResponse
from app.schemas.statistics import StatisticsRead
from app.services import statistics

router = APIRouter(prefix="/statistics", tags=["statistics"])


@router.get("", response_model=ApiResponse[StatisticsRead])
def overview(
    user: CurrentUser,
    db: DBSession,
    start_date: date | None = None,
    end_date: date | None = None,
):
    return ApiResponse(data=statistics.overview(db, user, start_date, end_date))
