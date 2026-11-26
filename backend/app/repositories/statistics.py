from datetime import date, datetime

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session, load_only

from app.models.focus_session import FocusSession
from app.models.task import Task


def focus_sessions(db: Session, user_id: str, start: datetime, end: datetime, now: datetime):
    query = (
        select(FocusSession)
        .options(
            load_only(
                FocusSession.mode,
                FocusSession.status,
                FocusSession.elapsed_seconds,
                FocusSession.duration_seconds,
                FocusSession.started_at,
                FocusSession.segment_started_at,
                FocusSession.window_end,
            )
        )
        .where(
            FocusSession.user_id == user_id,
            FocusSession.kind == "focus",
            FocusSession.status.in_(("running", "paused", "scheduled", "completed")),
            FocusSession.started_at >= start,
            FocusSession.started_at < end,
            FocusSession.started_at <= now,
        )
        .execution_options(yield_per=500)
    )
    return db.scalars(query)


def task_counts(
    db: Session,
    user_id: str,
    start: datetime,
    end: datetime,
    now: datetime,
    today: date,
) -> dict:
    columns = [
        func.count().label("total"),
        *[
            func.coalesce(func.sum(case((Task.status == status, 1), else_=0)), 0).label(status)
            for status in ("todo", "doing", "done")
        ],
        func.coalesce(
            func.sum(case(((Task.status != "done") & (Task.due_date < today), 1), else_=0)),
            0,
        ).label("overdue"),
    ]
    return dict(
        db.execute(
            select(*columns)
            .select_from(Task)
            .where(
                Task.user_id == user_id,
                Task.created_at >= start,
                Task.created_at < end,
                Task.created_at <= now,
            )
        )
        .mappings()
        .one()
    )
