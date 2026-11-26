from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

ProblemBucket = Literal["today", "history", "resolved", "all"]


class ProblemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: str = Field(min_length=1, max_length=10000)

    @field_validator("content")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Problem cannot be blank")
        return value


class ProblemEdit(ProblemCreate):
    expected_revision: str = Field(min_length=36, max_length=36)


class ProblemStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_resolved: bool = Field(strict=True)
    expected_revision: str = Field(min_length=36, max_length=36)


class ProblemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    content: str
    is_resolved: bool
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime
    revision: str

    @field_serializer("resolved_at", "created_at", "updated_at")
    def serialize_time(self, value: datetime | None) -> str | None:
        return value.replace(tzinfo=timezone.utc).isoformat() if value else None


class ProblemPage(BaseModel):
    items: list[ProblemRead]
    total: int
    page: int
    page_size: int
    counts: dict[str, int]
    today: date
    timezone: str
