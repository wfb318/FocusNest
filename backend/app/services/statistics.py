from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.user import User, utcnow
from app.repositories import statistics as repository
from app.schemas.statistics import (
    DailyFocus,
    FocusModeSummary,
    FocusSummary,
    StatisticsRead,
    TaskSummary,
)
from app.services.focus import elapsed


def overview(db: Session, user: User, start: date | None, end: date | None) -> StatisticsRead:
    now = utcnow()
    zone = ZoneInfo(user.timezone)
    today = now.replace(tzinfo=timezone.utc).astimezone(zone).date()
    if start is None and end is None:
        start = today - timedelta(days=today.weekday())
        end = start + timedelta(days=6)
    if start is None or end is None or not date(1900, 1, 1) <= start <= end <= date(9998, 12, 31):
        raise AppError(422, 42210, "Provide both dates in a valid range")
    if (end - start).days >= 366:
        raise AppError(422, 42210, "Select at most 366 days")

    # Construct each local midnight separately to account for DST.
    start_utc = datetime.combine(start, time(), zone).astimezone(timezone.utc).replace(tzinfo=None)
    end_utc = (
        datetime.combine(end + timedelta(days=1), time(), zone)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )
    days = {
        start + timedelta(days=offset): DailyFocus(date=start + timedelta(days=offset))
        for offset in range((end - start).days + 1)
    }
    modes = {
        mode: FocusModeSummary(mode=mode)
        for mode in ("pomodoro", "countdown", "stopwatch", "scheduled")
    }
    total = FocusSummary()
    for session in repository.focus_sessions(db, user.id, start_utc, end_utc, now):
        seconds = elapsed(session, now)
        finished = (
            session.status == "completed"
            or (session.mode == "scheduled" and session.window_end <= now)
            or (
                session.status == "running"
                and session.duration_seconds is not None
                and seconds >= session.duration_seconds
            )
        )
        day = session.started_at.replace(tzinfo=timezone.utc).astimezone(zone).date()
        for bucket in (total, days[day], modes[session.mode]):
            bucket.seconds += seconds
            bucket.completed += int(finished)
            bucket.active += int(not finished)
    tasks = repository.task_counts(db, user.id, start_utc, end_utc, now, today)
    tasks["completion_rate"] = (
        round(tasks["done"] * 100 / tasks["total"], 1) if tasks["total"] else None
    )
    return StatisticsRead(
        start_date=start,
        end_date=end,
        timezone=user.timezone,
        today=today,
        server_now=now,
        focus=total,
        tasks=TaskSummary(**tasks),
        daily=list(days.values()),
        modes=list(modes.values()),
    )
