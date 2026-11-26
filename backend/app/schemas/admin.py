from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_serializer


class AdminOverview(BaseModel):
    registered_total: int
    registered_today: int
    registered_week: int
    registered_month: int
    administrators: int
    online_users: int
    timezone: str
    today: date
    server_now: datetime
    online_window_seconds: int

    @field_serializer("server_now")
    def serialize_time(self, value: datetime) -> str:
        return value.replace(tzinfo=timezone.utc).isoformat()


class AdminUserRead(BaseModel):
    id: str
    username: str
    email: str
    nickname: str | None
    role: Literal["user", "admin"]
    created_at: datetime
    last_login_at: datetime | None
    last_seen_at: datetime | None
    online: bool

    @field_serializer("created_at", "last_login_at", "last_seen_at")
    def serialize_time(self, value: datetime | None) -> str | None:
        return value.replace(tzinfo=timezone.utc).isoformat() if value is not None else None


class AdminUserPage(BaseModel):
    items: list[AdminUserRead]
    total: int
    page: int
    page_size: int
    server_now: datetime
    online_window_seconds: int

    @field_serializer("server_now")
    def serialize_time(self, value: datetime) -> str:
        return value.replace(tzinfo=timezone.utc).isoformat()


class PresenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PresenceRead(BaseModel):
    server_now: datetime
    online_window_seconds: int

    @field_serializer("server_now")
    def serialize_time(self, value: datetime) -> str:
        return value.replace(tzinfo=timezone.utc).isoformat()
