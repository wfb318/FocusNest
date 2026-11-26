from datetime import date, datetime, timezone
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

TaskStatus = Literal["todo", "doing", "done"]
TaskPriority = Literal["low", "medium", "high"]


class TaskFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("title", check_fields=False)
    @classmethod
    def clean_title(cls, value: str | None) -> str | None:
        if value is not None:
            value = value.strip()
            if not value:
                raise ValueError("Title must not be blank")
        return value


class TaskCreate(TaskFields):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    status: TaskStatus = "todo"
    priority: TaskPriority = "medium"
    scheduled_date: date | None = None
    due_date: date | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=10080, strict=True)


class TaskUpdate(TaskFields):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    scheduled_date: date | None = None
    due_date: date | None = None
    estimated_minutes: int | None = Field(default=None, ge=1, le=10080, strict=True)

    @model_validator(mode="after")
    def reject_null_required_fields(self) -> "TaskUpdate":
        for name in ("title", "status", "priority"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    description: str | None
    status: TaskStatus
    priority: TaskPriority
    scheduled_date: date | None
    due_date: date | None
    estimated_minutes: int | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    @field_serializer("completed_at", "created_at", "updated_at")
    def serialize_time(self, value: datetime | None) -> str | None:
        return value.replace(tzinfo=timezone.utc).isoformat() if value is not None else None


class TaskPage(BaseModel):
    items: list[TaskRead]
    total: int
    page: int
    page_size: int
