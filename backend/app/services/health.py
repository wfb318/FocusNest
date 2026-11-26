from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.repositories.health import ping_database
from app.schemas.health import HealthStatus


def check_health(db: Session, check_database: bool = False) -> HealthStatus:
    if check_database:
        try:
            ping_database(db)
        except SQLAlchemyError:
            raise AppError(503, 50301, "Database unavailable") from None
    return HealthStatus(database="connected" if check_database else "not_checked")
