from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer

from app.schemas.note import NoteStorageMode


class DashboardTask(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    status: Literal["todo", "doing", "done"]
    priority: Literal["low", "medium", "high"]
    scheduled_date: date | None
    due_date: date | None


class RecentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    updated_at: datetime

    @field_serializer("updated_at")
    def serialize_time(self, value: datetime) -> str:
        return value.replace(tzinfo=timezone.utc).isoformat()


class RecentNote(RecentItem):
    pinned: bool
    storage_mode: NoteStorageMode


class RecentDocument(RecentItem):
    kind: str


class DashboardRead(BaseModel):
    today: date
    timezone: str
    server_now: datetime
    task_total: int
    task_done: int
    overdue_tasks: int
    tasks: list[DashboardTask]
    focus_seconds: float
    focus_completed: int
    active_focus_id: str | None
    active_focus_seconds: float
    journal_source: Literal["local"] = "local"
    journal_written: bool | None
    journal_title: str | None
    recent_notes: list[RecentNote]
    recent_documents: list[RecentDocument]

    @field_serializer("server_now")
    def serialize_time(self, value: datetime) -> str:
        return value.replace(tzinfo=timezone.utc).isoformat()
