from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.common import ApiResponse
from app.schemas.health import HealthStatus
from app.services.health import check_health

router = APIRouter(tags=["health"])


@router.get("/health", response_model=ApiResponse[HealthStatus])
def health(
    db: Annotated[Session, Depends(get_db)],
    check_database: bool = False,
) -> ApiResponse[HealthStatus]:
    return ApiResponse(data=check_health(db, check_database))
