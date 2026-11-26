from datetime import datetime, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.focus_session import FocusSession
from app.models.task import Task
from app.models.user import User, utcnow
from app.repositories import focus as repository
from app.schemas.focus import FocusCreate, FocusPage, FocusRead


def elapsed(session: FocusSession, now: datetime) -> float:
    if session.mode == "scheduled":
        if session.status in ("completed", "cancelled"):
            return session.elapsed_seconds
        end = min(now, session.window_end)
        return max(0, (end - session.started_at).total_seconds())
    seconds = session.elapsed_seconds
    if session.status == "running" and session.segment_started_at:
        seconds += max(0, (now - session.segment_started_at).total_seconds())
    return min(seconds, session.duration_seconds) if session.duration_seconds else seconds


def reconcile(session: FocusSession | None, now: datetime) -> None:
    if session is not None and session.mode == "scheduled" and session.active_user_id:
        if now >= session.window_end:
            session.elapsed_seconds = elapsed(session, now)
            session.ended_at = session.window_end
            session.status = "completed"
            session.active_user_id = None
            session.segment_started_at = None
            session.updated_at = now
        elif now >= session.window_start and session.status == "scheduled":
            session.status = "running"
            session.updated_at = now
        return
    if (
        session is not None
        and session.status == "running"
        and session.duration_seconds
        and elapsed(session, now) >= session.duration_seconds
    ):
        session.ended_at = session.segment_started_at + timedelta(
            seconds=session.duration_seconds - session.elapsed_seconds
        )
        session.elapsed_seconds = float(session.duration_seconds)
        session.segment_started_at = None
        session.status = "completed"
        session.active_user_id = None
        session.updated_at = now


def read(session: FocusSession, now: datetime) -> FocusRead:
    return FocusRead(
        id=session.id,
        task_id=session.task_id,
        title=session.title,
        window_start=session.window_start,
        window_end=session.window_end,
        occurrence_key=session.occurrence_key,
        mode=session.mode,
        kind=session.kind,
        status=session.status,
        duration_seconds=session.duration_seconds,
        elapsed_seconds=elapsed(session, now),
        started_at=session.started_at,
        ended_at=session.ended_at,
        updated_at=session.updated_at,
        server_now=now,
    )


def current(db: Session, user: User) -> FocusRead | None:
    repository.lock_user(db, user.id)
    session = repository.active(db, user.id)
    now = utcnow()
    reconcile(session, now)
    result = read(session, now) if session and session.active_user_id else None
    db.commit()
    return result


def list_sessions(db: Session, user: User, page: int, page_size: int) -> FocusPage:
    repository.lock_user(db, user.id)
    now = utcnow()
    reconcile(repository.active(db, user.id), now)
    db.flush()
    items, total = repository.history(db, user.id, page, page_size)
    result = FocusPage(
        items=[read(item, now) for item in items], total=total, page=page, page_size=page_size
    )
    db.commit()
    return result


def start(
    db: Session, user: User, payload: FocusCreate, *, occurrence_key: str | None = None
) -> FocusRead:
    repository.lock_user(db, user.id)
    now = utcnow()
    if occurrence_key:
        existing = db.scalar(
            select(FocusSession)
            .where(FocusSession.user_id == user.id, FocusSession.occurrence_key == occurrence_key)
            .with_for_update()
        )
        if existing:
            reconcile(existing, now)
            result = read(existing, now)
            db.commit()
            return result
    if payload.mode == "scheduled":
        if payload.window_end <= now or payload.window_start > now + timedelta(days=31):
            raise AppError(422, 42208, "End must be in the future; start within 31 days")
    previous = repository.active(db, user.id)
    reconcile(previous, now)
    if previous and previous.active_user_id:
        raise AppError(409, 40902, "A timer is already active")
    task = None
    if payload.task_id:
        task = db.scalar(
            select(Task)
            .where(Task.id == payload.task_id, Task.user_id == user.id)
            .with_for_update()
        )
        if task is None:
            raise AppError(404, 40401, "Task not found")
    db.flush()
    fields = payload.model_dump()
    fields["title"] = payload.title.strip() or (task.title if task else "")
    session = FocusSession(
        user_id=user.id,
        active_user_id=user.id,
        **fields,
        occurrence_key=occurrence_key,
        status="scheduled"
        if payload.mode == "scheduled" and payload.window_start > now
        else "running",
        elapsed_seconds=0,
        # A late activation records only the remaining window, never backfills attendance.
        started_at=max(now, payload.window_start) if payload.mode == "scheduled" else now,
        segment_started_at=now,
        updated_at=now,
    )
    db.add(session)
    try:
        db.flush()
        result = read(session, now)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, 40902, "Timer or linked task changed; reload and retry") from None
    return result


def transition(
    db: Session, user: User, session_id: str, action: Literal["pause", "resume", "finish", "cancel"]
) -> FocusRead:
    repository.lock_user(db, user.id)
    session = repository.owned(db, user.id, session_id)
    if session is None:
        raise AppError(404, 40402, "Focus session not found")
    now = utcnow()
    reconcile(session, now)
    target = {"pause": "paused", "resume": "running", "finish": "completed", "cancel": "cancelled"}[
        action
    ]
    if session.status in ("completed", "cancelled"):
        # A delayed command must never resurrect or overwrite a finished timer.
        result = read(session, now)
        db.commit()
        return result
    if session.mode == "scheduled" and action in ("pause", "resume"):
        raise AppError(409, 40909, "Fixed-time timers cannot be paused")
    if session.status == "scheduled" and action == "finish":
        raise AppError(409, 40909, "Cancel a timer that has not started")
    if session.status != target:
        session.elapsed_seconds = elapsed(session, now)
        session.segment_started_at = now if action == "resume" else None
        session.status = target
        session.updated_at = now
        if action in ("finish", "cancel"):
            session.ended_at = now
            session.active_user_id = None
    result = read(session, now)
    db.commit()
    return result
