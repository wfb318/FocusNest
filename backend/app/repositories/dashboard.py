from datetime import date, datetime

from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.models import Document, FocusSession, Journal, Note, Task
from app.repositories.documents import summary_title as document_summary_title
from app.repositories.notes import summary_title


def task_overview(db: Session, user_id: str, today: date):
    owned = Task.user_id == user_id
    day = or_(Task.scheduled_date == today, Task.due_date == today)
    total, done = db.execute(
        select(func.count(), func.coalesce(func.sum(case((Task.status == "done", 1), else_=0)), 0))
        .select_from(Task)
        .where(owned, day)
    ).one()
    overdue = (
        db.scalar(
            select(func.count())
            .select_from(Task)
            .where(owned, Task.status != "done", Task.due_date < today)
        )
        or 0
    )
    items = (
        db.execute(
            select(
                Task.id, Task.title, Task.status, Task.priority, Task.scheduled_date, Task.due_date
            )
            .where(owned, day, Task.status != "done")
            .order_by(
                case((Task.status == "doing", 0), else_=1),
                case((Task.priority == "high", 0), (Task.priority == "medium", 1), else_=2),
                Task.created_at,
                Task.id,
            )
            .limit(5)
        )
        .mappings()
        .all()
    )
    return total, done, overdue, items


def focus_overview(db: Session, user_id: str, start: datetime, end: datetime, now: datetime):
    filters = [
        FocusSession.user_id == user_id,
        FocusSession.kind == "focus",
        FocusSession.started_at >= start,
        FocusSession.started_at < end,
        FocusSession.started_at <= now,
    ]
    seconds, completed = db.execute(
        select(
            func.coalesce(func.sum(FocusSession.elapsed_seconds), 0),
            func.coalesce(func.sum(case((FocusSession.status == "completed", 1), else_=0)), 0),
        ).where(*filters, FocusSession.status == "completed")
    ).one()
    active = db.scalar(
        select(FocusSession).where(
            *filters,
            FocusSession.status.in_(("running", "scheduled", "paused")),
            FocusSession.active_user_id == user_id,
        )
    )
    return float(seconds), int(completed), active


def journal_title(db: Session, user_id: str, today: date):
    return db.execute(
        select(Journal.title).where(Journal.user_id == user_id, Journal.entry_date == today)
    ).first()


def recent_notes(db: Session, user_id: str):
    return (
        db.execute(
            select(Note.id, summary_title, Note.storage_mode, Note.pinned, Note.updated_at)
            .where(Note.user_id == user_id)
            .order_by(Note.updated_at.desc(), Note.id.desc())
            .limit(3)
        )
        .mappings()
        .all()
    )


def recent_documents(db: Session, user_id: str):
    return (
        db.execute(
            select(Document.id, document_summary_title, Document.kind, Document.updated_at)
            .where(Document.user_id == user_id)
            .order_by(Document.updated_at.desc(), Document.id.desc())
            .limit(3)
        )
        .mappings()
        .all()
    )
