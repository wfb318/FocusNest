from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.models.task import Task
from app.models.user import User, utcnow
from app.repositories import tasks
from app.schemas.task import TaskCreate, TaskPage, TaskRead, TaskUpdate


def local_today(user: User) -> date:
    return datetime.now(timezone.utc).astimezone(ZoneInfo(user.timezone)).date()


def get_task(db: Session, user: User, task_id: str) -> Task:
    task = tasks.find_owned(db, user.id, task_id)
    if task is None:
        raise AppError(404, 40401, "Task not found")
    return task


def list_tasks(db: Session, user: User, *, today: bool, **filters) -> TaskPage:
    items, total = tasks.list_owned(
        db, user.id, today_date=local_today(user) if today else None, **filters
    )
    return TaskPage(
        items=[TaskRead.model_validate(task) for task in items],
        total=total,
        page=filters["page"],
        page_size=filters["page_size"],
    )


def create_task(db: Session, user: User, payload: TaskCreate) -> Task:
    values = payload.model_dump()
    values["completed_at"] = utcnow() if payload.status == "done" else None
    task = tasks.add(db, user.id, values)
    db.commit()
    db.refresh(task)
    return task


def update_task(db: Session, user: User, task_id: str, payload: TaskUpdate) -> Task:
    task = get_task(db, user, task_id)
    values = payload.model_dump(exclude_unset=True)
    if "status" in values and values["status"] != task.status:
        task.completed_at = utcnow() if values["status"] == "done" else None
    for name, value in values.items():
        setattr(task, name, value)
    if values:
        task.updated_at = utcnow()
    db.commit()
    db.refresh(task)
    return task


def complete_task(db: Session, user: User, task_id: str) -> Task:
    return update_task(db, user, task_id, TaskUpdate(status="done"))


def delete_task(db: Session, user: User, task_id: str) -> None:
    tasks.remove(db, get_task(db, user, task_id))
    db.commit()
