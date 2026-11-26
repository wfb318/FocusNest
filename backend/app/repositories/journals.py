from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.journal import Journal
from app.models.user import User


def lock_user(db: Session, user_id: str) -> None:
    db.execute(select(User.id).where(User.id == user_id).with_for_update()).one()


def find_day(db: Session, user_id: str, entry_date: date, *, lock: bool = False):
    query = select(Journal).where(Journal.user_id == user_id, Journal.entry_date == entry_date)
    return db.scalar(query.with_for_update() if lock else query)


def list_owned(
    db: Session,
    user_id: str,
    *,
    page: int,
    page_size: int,
    start_date: date | None,
    end_date: date | None,
    q: str | None,
):
    filters = [Journal.user_id == user_id]
    if start_date:
        filters.append(Journal.entry_date >= start_date)
    if end_date:
        filters.append(Journal.entry_date <= end_date)
    if q:
        filters.append(
            or_(
                Journal.title.contains(q, autoescape=True),
                Journal.content.contains(q, autoescape=True),
            )
        )
    total = db.scalar(select(func.count()).select_from(Journal).where(*filters)) or 0
    # List summaries deliberately omit full private bodies.
    query = select(
        Journal.id,
        Journal.entry_date,
        Journal.title,
        Journal.revision,
        Journal.created_at,
        Journal.updated_at,
    ).where(*filters)
    items = db.execute(
        query.order_by(Journal.entry_date.desc()).offset((page - 1) * page_size).limit(page_size)
    ).all()
    return items, total
