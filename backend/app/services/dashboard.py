from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.models.user import User, utcnow
from app.repositories import dashboard as repository
from app.schemas.dashboard import DashboardRead
from app.services.focus import elapsed


def overview(db: Session, user: User, *, include_journal: bool = False) -> DashboardRead:
    now = utcnow()
    zone = ZoneInfo(user.timezone)
    today = now.replace(tzinfo=timezone.utc).astimezone(zone).date()
    # Construct both local midnights: DST days are not always 24 UTC hours long.
    start = datetime.combine(today, time(), zone).astimezone(timezone.utc).replace(tzinfo=None)
    end = (
        datetime.combine(today + timedelta(days=1), time(), zone)
        .astimezone(timezone.utc)
        .replace(tzinfo=None)
    )
    total, done, overdue, tasks = repository.task_overview(db, user.id, today)
    seconds, completed, active = repository.focus_overview(db, user.id, start, end, now)
    active_seconds = elapsed(active, now) if active else 0
    if active:
        seconds += active_seconds
        if (active.mode == "scheduled" and now >= active.window_end) or (
            active.duration_seconds and elapsed(active, now) >= active.duration_seconds
        ):
            completed += 1
    # Local-mode clients must not read legacy metadata, even as part of a dashboard.
    return DashboardRead(
        today=today,
        timezone=user.timezone,
        server_now=now,
        task_total=total,
        task_done=done,
        overdue_tasks=overdue,
        tasks=tasks,
        focus_seconds=seconds,
        focus_completed=completed,
        active_focus_id=active.id if active else None,
        active_focus_seconds=active_seconds,
        journal_written=None,
        journal_title=None,
        recent_notes=repository.recent_notes(db, user.id),
        recent_documents=repository.recent_documents(db, user.id),
    )
