from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.task import Task


def find_owned(db: Session, user_id: str, task_id: str) -> Task | None:
    return db.scalar(select(Task).where(Task.id == task_id, Task.user_id == user_id))


def list_owned(
    db: Session,
    user_id: str,
    *,
    page: int,
    page_size: int,
    status: str | None,
    priority: str | None,
    scheduled_date: date | None,
    due_date: date | None,
    today_date: date | None,
) -> tuple[list[Task], int]:
    filters = [Task.user_id == user_id]
    if status is not None:
        filters.append(Task.status == status)
    if priority is not None:
        filters.append(Task.priority == priority)
    if scheduled_date is not None:
        filters.append(Task.scheduled_date == scheduled_date)
    if due_date is not None:
        filters.append(Task.due_date == due_date)
    if today_date is not None:
        filters.append(or_(Task.scheduled_date == today_date, Task.due_date == today_date))
    total = db.scalar(select(func.count()).select_from(Task).where(*filters)) or 0
    items = db.scalars(
        select(Task)
        .where(*filters)
        .order_by(Task.created_at.desc(), Task.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return list(items), total


def add(db: Session, user_id: str, values: dict) -> Task:
    task = Task(user_id=user_id, **values)
    db.add(task)
    db.flush()
    return task


def remove(db: Session, task: Task) -> None:
    db.delete(task)
