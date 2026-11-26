from collections import Counter
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.focus_session import FocusSession
from app.models.schedule import (
    ScheduleException,
    ScheduleTemplate,
    ScheduleWeekPlan,
    WeeklySchedule,
)
from app.models.task import Task
from app.models.user import User
from app.repositories.focus import lock_user
from app.schemas.schedule import (
    ScheduleTemplateApply,
    ScheduleTemplateRead,
    ScheduleTemplateReview,
    ScheduleTemplateSave,
)
from app.services import schedules


def week_end(start: date) -> date:
    if start.weekday() != 0 or start > date.max - timedelta(days=6):
        raise AppError(422, 42208, "Select a Monday")
    return start + timedelta(days=6)


def local_today(user: User) -> date:
    return (
        schedules.utcnow().replace(tzinfo=timezone.utc).astimezone(ZoneInfo(user.timezone)).date()
    )


def summaries(db: Session, user: User, *, lock=False) -> list[ScheduleTemplateRead]:
    query = (
        select(ScheduleTemplate)
        .where(ScheduleTemplate.user_id == user.id)
        .order_by(ScheduleTemplate.name)
    )
    return [
        ScheduleTemplateRead(id=row.id, name=row.name, entry_count=len(row.entries))
        for row in db.scalars(query.with_for_update() if lock else query)
    ]


def save(db: Session, user: User, payload: ScheduleTemplateSave) -> ScheduleTemplateRead:
    end = week_end(payload.week_start)
    lock_user(db, user.id)
    existing = summaries(db, user, lock=True)
    if len(existing) >= 50:
        raise AppError(422, 42209, "At most 50 schedule templates")
    if any(item.name.casefold() == payload.name.casefold() for item in existing):
        raise AppError(409, 40913, "Template name already exists")
    entries = []
    for row, day, exception in schedules.rows_in_range(
        db, user, payload.week_start, end, lock=True
    ):
        if not (exception and (exception.skipped or exception.replaced)):
            entries.append(
                {
                    **schedules.values(exception or row),
                    "weekday": day.weekday(),
                    "timezone": row.timezone,
                }
            )
    if len(entries) > 500:
        raise AppError(422, 42209, "At most 500 entries per template")
    entries.sort(key=lambda item: (item["weekday"], item["start_minute"], item["title"]))
    row = ScheduleTemplate(user_id=user.id, name=payload.name, entries=entries)
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AppError(409, 40913, "Template name already exists") from None
    return ScheduleTemplateRead(id=row.id, name=row.name, entry_count=len(entries))


def get_plan(
    db: Session, user: User, start: date, *, lock: bool = False
) -> ScheduleWeekPlan | None:
    return db.get(ScheduleWeekPlan, (user.id, start), with_for_update=lock)


def review_due(db: Session, user: User) -> ScheduleTemplateReview | None:
    today = local_today(user)
    if today.weekday() != 6:
        return None
    target = today + timedelta(days=1)
    plan = get_plan(db, user, target)
    if plan and plan.reviewed:
        return None
    current = get_plan(db, user, target - timedelta(days=7))
    return ScheduleTemplateReview(
        week_start=target,
        current_template_id=current.template_id if current else None,
        planned_template_id=plan.template_id if plan else None,
    )


def keep_week(db: Session, user: User, start: date) -> None:
    lock_user(db, user.id)
    today = local_today(user)
    if today.weekday() != 6 or start != today + timedelta(days=1):
        raise AppError(422, 42209, "Only the upcoming Sunday review can be closed")
    plan = get_plan(db, user, start, lock=True)
    if plan is None:
        current = get_plan(db, user, start - timedelta(days=7), lock=True)
        if current and current.template_id:
            template = db.get(ScheduleTemplate, current.template_id, with_for_update=True)
            if template:
                now = schedules.utcnow().replace(tzinfo=timezone.utc)
                stage_week(db, user, template, start, now, automatic=True)
        db.add(
            ScheduleWeekPlan(
                user_id=user.id,
                week_start=start,
                reviewed=True,
                template_id=current.template_id if current else None,
            )
        )
    else:
        plan.reviewed = True
    db.commit()


def ensure_current_week(db: Session, user: User) -> bool:
    today = local_today(user)
    start = today - timedelta(days=today.weekday())
    if get_plan(db, user, start) is not None:
        return False
    previous = (
        select(ScheduleWeekPlan.template_id)
        .where(
            ScheduleWeekPlan.user_id == user.id,
            ScheduleWeekPlan.week_start < start,
            ScheduleWeekPlan.template_id.is_not(None),
        )
        .order_by(ScheduleWeekPlan.week_start.desc())
        .limit(1)
    )
    if db.scalar(previous) is None:
        return False
    lock_user(db, user.id)
    if get_plan(db, user, start, lock=True) is not None:
        return False
    template_id = db.scalar(previous.with_for_update())
    template = db.get(ScheduleTemplate, template_id, with_for_update=True) if template_id else None
    if template is None:
        return False
    now = schedules.utcnow().replace(tzinfo=timezone.utc)
    stage_week(db, user, template, start, now, automatic=True)
    db.add(
        ScheduleWeekPlan(user_id=user.id, week_start=start, template_id=template.id, reviewed=True)
    )
    db.commit()
    return True


def apply(db: Session, user: User, template_id: str, payload: ScheduleTemplateApply) -> None:
    end = week_end(payload.week_start)
    lock_user(db, user.id)
    template = db.scalar(
        select(ScheduleTemplate)
        .where(ScheduleTemplate.id == template_id, ScheduleTemplate.user_id == user.id)
        .with_for_update()
    )
    if template is None:
        raise AppError(404, 40409, "Schedule template not found")
    now = schedules.utcnow().replace(tzinfo=timezone.utc)
    if end < now.astimezone(ZoneInfo(user.timezone)).date():
        raise AppError(422, 42209, "Cannot apply a template to a past week")
    plan = get_plan(db, user, payload.week_start, lock=True)
    current_id = plan.template_id if plan else None
    today = now.astimezone(ZoneInfo(user.timezone)).date()
    confirming_review = today.weekday() == 6 and payload.week_start == today + timedelta(days=1)
    if current_id == template_id:
        if confirming_review and not plan.reviewed:
            plan.reviewed = True
            db.commit()
        return
    if current_id != payload.expected_template_id:
        raise AppError(409, 40914, "Week template changed")

    stage_week(db, user, template, payload.week_start, now)
    if plan is None:
        plan = ScheduleWeekPlan(user_id=user.id, week_start=payload.week_start)
        db.add(plan)
    plan.template_id = template_id
    plan.reviewed = plan.reviewed or confirming_review
    db.commit()


def stage_week(
    db: Session,
    user: User,
    template: ScheduleTemplate,
    start_day: date,
    now: datetime,
    *,
    automatic: bool = False,
) -> None:
    end = week_end(start_day)
    rows = list(schedules.rows_in_range(db, user, start_day, end, lock=True))
    protected = set()
    if automatic and rows:
        keys = [f"{row.id}:{day.isoformat()}" for row, day, _ in rows]
        protected = set(
            db.scalars(
                select(FocusSession.occurrence_key)
                .where(FocusSession.user_id == user.id, FocusSession.occurrence_key.in_(keys))
                .with_for_update()
            )
        )
    retained = Counter()
    # Keep changes already made in the target week when the carry is automatic.
    for row, day, exception in rows:
        if exception and exception.replaced:
            continue
        item = schedules.occurrence(row, day, exception)
        if automatic:
            if not item.repeats:
                continue
            if exception or item.key in protected:
                retained[tuple(schedules.values(row).values()) + (row.weekday, row.timezone)] += 1
                continue
        elif not upcoming(day, item.starts_at, item.timezone, now):
            continue
        if exception is None:
            exception = ScheduleException(
                schedule_id=row.id, occurrence_date=day, **schedules.values(row)
            )
            db.add(exception)
        exception.replaced = True
        row.revision += 1

    task_ids = {entry["task_id"] for entry in template.entries if entry["task_id"]}
    owned_tasks = (
        set(
            db.scalars(
                select(Task.id)
                .where(Task.user_id == user.id, Task.id.in_(task_ids))
                .with_for_update()
            )
        )
        if task_ids
        else set()
    )
    for entry in template.entries:
        fingerprint = tuple(entry[field] for field in schedules.FIELDS) + (
            entry["weekday"],
            entry["timezone"],
        )
        if retained[fingerprint]:
            retained[fingerprint] -= 1
            continue
        day = start_day + timedelta(days=entry["weekday"])
        start = schedules.local_time(day, entry["start_minute"], entry["timezone"])
        if automatic or upcoming(day, start, entry["timezone"], now):
            fields = {
                **entry,
                "task_id": entry["task_id"] if entry["task_id"] in owned_tasks else None,
            }
            db.add(
                WeeklySchedule(user_id=user.id, effective_from=day, effective_until=day, **fields)
            )


def upcoming(day: date, start: datetime | None, zone: str, now: datetime) -> bool:
    if start is not None:
        return start > now
    # Keep already elapsed dates, including entries with an invalid DST wall time.
    return day >= now.astimezone(ZoneInfo(zone)).date()
