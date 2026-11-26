from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DBSession
from app.schemas.common import ApiResponse
from app.schemas.task import TaskCreate, TaskPage, TaskPriority, TaskRead, TaskStatus, TaskUpdate
from app.services import tasks

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=ApiResponse[TaskPage])
def list_tasks(
    user: CurrentUser,
    db: DBSession,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: TaskStatus | None = None,
    priority: TaskPriority | None = None,
    scheduled_date: date | None = None,
    due_date: date | None = None,
    today: bool = False,
) -> ApiResponse[TaskPage]:
    return ApiResponse(
        data=tasks.list_tasks(
            db,
            user,
            page=page,
            page_size=page_size,
            status=status,
            priority=priority,
            scheduled_date=scheduled_date,
            due_date=due_date,
            today=today,
        )
    )


@router.post("", status_code=201, response_model=ApiResponse[TaskRead])
def create_task(payload: TaskCreate, user: CurrentUser, db: DBSession) -> ApiResponse[TaskRead]:
    return ApiResponse(data=TaskRead.model_validate(tasks.create_task(db, user, payload)))


@router.get("/{task_id}", response_model=ApiResponse[TaskRead])
def get_task(task_id: str, user: CurrentUser, db: DBSession) -> ApiResponse[TaskRead]:
    return ApiResponse(data=TaskRead.model_validate(tasks.get_task(db, user, task_id)))


@router.patch("/{task_id}", response_model=ApiResponse[TaskRead])
def update_task(
    task_id: str,
    payload: TaskUpdate,
    user: CurrentUser,
    db: DBSession,
) -> ApiResponse[TaskRead]:
    return ApiResponse(data=TaskRead.model_validate(tasks.update_task(db, user, task_id, payload)))


@router.post("/{task_id}/complete", response_model=ApiResponse[TaskRead])
def complete_task(task_id: str, user: CurrentUser, db: DBSession) -> ApiResponse[TaskRead]:
    return ApiResponse(data=TaskRead.model_validate(tasks.complete_task(db, user, task_id)))


@router.delete("/{task_id}", response_model=ApiResponse[None])
def delete_task(task_id: str, user: CurrentUser, db: DBSession) -> ApiResponse[None]:
    tasks.delete_task(db, user, task_id)
    return ApiResponse(message="Task deleted")
