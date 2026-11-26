from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.focus_session import FocusSession
from app.models.user import User


def lock_user(db: Session, user_id: str) -> None:
    # Lock an existing row even when no active session exists yet.
    db.execute(select(User.id).where(User.id == user_id).with_for_update()).one()


def active(db: Session, user_id: str) -> FocusSession | None:
    return db.scalar(
        select(FocusSession).where(FocusSession.active_user_id == user_id).with_for_update()
    )


def owned(db: Session, user_id: str, session_id: str) -> FocusSession | None:
    return db.scalar(
        select(FocusSession)
        .where(FocusSession.user_id == user_id, FocusSession.id == session_id)
        .with_for_update()
    )


def history(db: Session, user_id: str, page: int, page_size: int):
    condition = FocusSession.user_id == user_id
    total = db.scalar(select(func.count()).select_from(FocusSession).where(condition)) or 0
    items = db.scalars(
        select(FocusSession)
        .where(condition)
        .order_by(FocusSession.started_at.desc(), FocusSession.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return items, total
