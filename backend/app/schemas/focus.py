from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

FocusMode = Literal["pomodoro", "countdown", "stopwatch", "scheduled"]
FocusStatus = Literal["scheduled", "running", "paused", "completed", "cancelled"]


class FocusCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: FocusMode = "pomodoro"
    kind: Literal["focus", "break"] = "focus"
    duration_seconds: int | None = Field(default=None, ge=60, le=86400, strict=True)
    task_id: str | None = Field(default=None, min_length=1, max_length=36)
    title: str = Field(default="", max_length=200)
    window_start: datetime | None = None
    window_end: datetime | None = None

    @model_validator(mode="after")
    def valid_timer(self) -> "FocusCreate":
        if self.mode == "scheduled":
            if self.kind != "focus" or self.duration_seconds is not None:
                raise ValueError("Scheduled timer cannot have duration or break kind")
            if not self.window_start or not self.window_end:
                raise ValueError("Start and end are required")
            if self.window_start.tzinfo is None or self.window_end.tzinfo is None:
                raise ValueError("Times must include timezone")
            self.window_start = self.window_start.astimezone(timezone.utc).replace(tzinfo=None)
            self.window_end = self.window_end.astimezone(timezone.utc).replace(tzinfo=None)
            seconds = (self.window_end - self.window_start).total_seconds()
            if seconds < 60 or seconds > 86400:
                raise ValueError("Window must be 1 minute to 24 hours")
            return self
        if self.window_start is not None or self.window_end is not None:
            raise ValueError("Only scheduled timers accept fixed times")
        if self.mode == "stopwatch":
            if self.duration_seconds is not None:
                raise ValueError("Stopwatch has no target duration")
        elif self.duration_seconds is None:
            self.duration_seconds = 300 if self.kind == "break" else 1500
        if self.kind == "break" and (self.mode != "pomodoro" or self.task_id is not None):
            raise ValueError("Breaks belong to Pomodoro and cannot link a task")
        return self


class FocusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    task_id: str | None
    title: str
    window_start: datetime | None
    window_end: datetime | None
    occurrence_key: str | None
    mode: FocusMode
    kind: Literal["focus", "break"]
    status: FocusStatus
    duration_seconds: int | None
    elapsed_seconds: float
    started_at: datetime
    ended_at: datetime | None
    updated_at: datetime
    server_now: datetime

    @field_serializer(
        "started_at", "ended_at", "updated_at", "server_now", "window_start", "window_end"
    )
    def serialize_time(self, value: datetime | None) -> str | None:
        return value.replace(tzinfo=timezone.utc).isoformat() if value else None


class FocusPage(BaseModel):
    items: list[FocusRead]
    total: int
    page: int
    page_size: int
