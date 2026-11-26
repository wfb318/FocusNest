from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.schedule import ScheduleException, ScheduleWeekPlan, WeeklySchedule
from app.models.task import Task
from app.models.user import User, utcnow
from app.repositories.focus import lock_user
from app.schemas.focus import FocusCreate
from app.schemas.schedule import (
    Occurrence,
    ScheduleCreate,
    ScheduleEdit,
    ScheduleFields,
    ScheduleRemove,
    ScheduleWeek,
)
from app.services import focus

FIELDS = tuple(ScheduleFields.model_fields)


def values(row) -> dict:
    return {name: getattr(row, name) for name in FIELDS}


def check_task(db: Session, user: User, task_id: str | None):
    if (
        task_id
        and db.scalar(select(Task.id).where(Task.id == task_id, Task.user_id == user.id)) is None
    ):
        raise AppError(404, 40401, "Task not found")


def local_time(day: date, minutes: int, zone: str) -> datetime | None:
    naive = datetime.combine(day, time()) + timedelta(minutes=minutes)
    aware = naive.replace(tzinfo=ZoneInfo(zone), fold=0)
    utc = aware.astimezone(timezone.utc)
    # Nonexistent DST wall times are shown with a warning and never auto-started.
    if utc.astimezone(ZoneInfo(zone)).replace(tzinfo=None) != naive:
        return None
    return utc


def occurs(row: WeeklySchedule, day: date) -> bool:
    return (
        day.weekday() == row.weekday
        and day >= row.effective_from
        and (row.effective_until is None or day <= row.effective_until)
    )


def occurrence(row: WeeklySchedule, day: date, exception: ScheduleException | None) -> Occurrence:
    fields = values(exception or row)
    start = local_time(day, fields["start_minute"], row.timezone)
    end = local_time(day, fields["end_minute"], row.timezone)
    warning = start is None or end is None or end <= start
    if not warning and fields["timer_enabled"]:
        warning = not 60 <= (end - start).total_seconds() <= 86400
    return Occurrence(
        **fields,
        schedule_id=row.id,
        key=f"{row.id}:{day.isoformat()}",
        occurrence_date=day,
        weekday=row.weekday,
        timezone=row.timezone,
        starts_at=start,
        ends_at=end,
        time_warning=warning,
        skipped=bool(exception and exception.skipped),
        overridden=exception is not None,
        revision=row.revision,
        repeats=row.effective_from != row.effective_until,
    )


def rows_in_range(db: Session, user: User, start: date, end: date, *, lock: bool = False):
    if end < start or (end - start).days > 31:
        raise AppError(422, 42208, "Range must be at most 32 days")
    rows = select(WeeklySchedule).where(
        WeeklySchedule.user_id == user.id,
        WeeklySchedule.effective_from <= end,
        (WeeklySchedule.effective_until.is_(None) | (WeeklySchedule.effective_until >= start)),
    )
    exceptions = (
        select(ScheduleException)
        .join(WeeklySchedule)
        .where(
            WeeklySchedule.user_id == user.id,
            ScheduleException.occurrence_date.between(start, end),
        )
    )
    schedules = db.scalars(rows.with_for_update() if lock else rows).all()
    overrides = db.scalars(exceptions.with_for_update() if lock else exceptions).all()
    lookup = {(e.schedule_id, e.occurrence_date): e for e in overrides}
    for row in schedules:
        for offset in range((end - start).days + 1):
            day = start + timedelta(days=offset)
            if occurs(row, day):
                yield row, day, lookup.get((row.id, day))


def list_week(db: Session, user: User, start: date, end: date) -> ScheduleWeek:
    items = []
    for row, day, exception in rows_in_range(db, user, start, end):
        if not (exception and exception.replaced):
            items.append(occurrence(row, day, exception))
    items.sort(key=lambda item: (item.occurrence_date, item.start_minute, item.key))
    plan = (
        db.get(ScheduleWeekPlan, (user.id, start))
        if start.weekday() == 0 and (end - start).days == 6
        else None
    )
    return ScheduleWeek(
        items=items,
        server_now=utcnow().replace(tzinfo=timezone.utc),
        template_id=plan.template_id if plan else None,
    )


def create(db: Session, user: User, payload: ScheduleCreate):
    lock_user(db, user.id)
    today = utcnow().replace(tzinfo=timezone.utc).astimezone(ZoneInfo(payload.timezone)).date()
    if payload.effective_from < today:
        raise AppError(422, 42208, "Cannot create a plan in the past")
    if not payload.repeat_weekly and payload.effective_from.weekday() != payload.weekday:
        raise AppError(422, 42208, "Date and weekday must match for a single occurrence")
    week_start = payload.effective_from - timedelta(days=payload.effective_from.weekday())
    week_end = week_start + timedelta(days=6)
    if payload.repeat_weekly:
        count = db.scalar(
            select(func.count())
            .select_from(WeeklySchedule)
            .where(
                WeeklySchedule.user_id == user.id,
                (WeeklySchedule.effective_from != WeeklySchedule.effective_until)
                | WeeklySchedule.effective_until.is_(None),
                WeeklySchedule.effective_until.is_(None)
                | (WeeklySchedule.effective_until >= today),
            )
        )
    else:
        count = sum(
            not (exception and exception.replaced)
            for _, _, exception in rows_in_range(db, user, week_start, week_end, lock=True)
        )
    if count >= 500:
        raise AppError(422, 42208, "At most 500 active weekly schedules")
    check_task(db, user, payload.task_id)
    row = WeeklySchedule(
        user_id=user.id,
        effective_until=None if payload.repeat_weekly else payload.effective_from,
        **payload.model_dump(exclude={"repeat_weekly"}),
    )
    db.add(row)
    db.commit()
    return {"id": row.id}


def owned(db: Session, user: User, schedule_id: str) -> WeeklySchedule:
    row = db.scalar(
        select(WeeklySchedule)
        .where(WeeklySchedule.id == schedule_id, WeeklySchedule.user_id == user.id)
        .with_for_update()
    )
    if row is None:
        raise AppError(404, 40407, "Schedule not found")
    return row


def check_edit(row: WeeklySchedule, payload):
    if row.revision != payload.revision:
        raise AppError(409, 40910, "Schedule changed; reload")
    today = utcnow().replace(tzinfo=timezone.utc).astimezone(ZoneInfo(row.timezone)).date()
    if not occurs(row, payload.occurrence_date) or payload.occurrence_date < today:
        raise AppError(422, 42208, "Choose an existing occurrence today or later")


def edit(
    db: Session, user: User, schedule_id: str, payload: ScheduleEdit | ScheduleRemove, remove=False
):
    lock_user(db, user.id)
    row = owned(db, user, schedule_id)
    check_edit(row, payload)
    if not remove:
        check_task(db, user, payload.task_id)
    if row.effective_from == row.effective_until and payload.scope != "single":
        raise AppError(422, 42208, "One-time schedules can only change this occurrence")
    if payload.scope == "single":
        ex = db.scalar(
            select(ScheduleException)
            .where(
                ScheduleException.schedule_id == row.id,
                ScheduleException.occurrence_date == payload.occurrence_date,
            )
            .with_for_update()
        )
        if ex and ex.replaced:
            raise AppError(409, 40910, "Schedule changed; reload")
        if ex is None:
            ex = ScheduleException(
                schedule_id=row.id, occurrence_date=payload.occurrence_date, **values(row)
            )
            db.add(ex)
        if not remove:
            for name in FIELDS:
                setattr(ex, name, getattr(payload, name))
        ex.skipped = remove
    else:
        old_until = row.effective_until
        row.effective_until = payload.occurrence_date - timedelta(days=1)
        # Exceptions before this boundary remain attached to historical version.
        if not remove:
            db.add(
                WeeklySchedule(
                    user_id=user.id,
                    **{name: getattr(payload, name) for name in FIELDS},
                    weekday=payload.weekday,
                    timezone=row.timezone,
                    effective_from=payload.occurrence_date,
                    effective_until=old_until,
                )
            )
    row.revision += 1
    db.commit()
    return {"updated": True}


def start_occurrence(db: Session, user: User, schedule_id: str, day: date):
    lock_user(db, user.id)
    row = owned(db, user, schedule_id)
    if not occurs(row, day):
        raise AppError(404, 40407, "Occurrence not found")
    ex = db.scalar(
        select(ScheduleException)
        .where(ScheduleException.schedule_id == row.id, ScheduleException.occurrence_date == day)
        .with_for_update()
    )
    item = occurrence(row, day, ex)
    now = utcnow().replace(tzinfo=timezone.utc)
    if (
        (ex and ex.replaced)
        or item.skipped
        or item.time_warning
        or not item.timer_enabled
        or not (item.starts_at <= now < item.ends_at)
    ):
        raise AppError(409, 40911, "This occurrence cannot start now")
    # The original planned interval is retained; elapsed starts at activation time.
    return focus.start(
        db,
        user,
        FocusCreate(
            mode="scheduled",
            title=item.title,
            task_id=item.task_id,
            window_start=item.starts_at,
            window_end=item.ends_at,
        ),
        occurrence_key=item.key,
    )
