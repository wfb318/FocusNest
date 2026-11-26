from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator


class JournalBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="", max_length=200)
    content: str = Field(min_length=1, max_length=100000)

    @field_validator("content")
    @classmethod
    def nonblank_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Content cannot be blank")
        # Preserve Markdown indentation and trailing spaces exactly.
        return value


class JournalSave(JournalBody):
    expected_revision: str | None = Field(default=None, min_length=36, max_length=36)


class EncryptedJournalBody(JournalBody):
    entry_date: date


class JournalMigrationCleanup(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: str = Field(min_length=36, max_length=36)
    verified_source_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    local_revision: str = Field(pattern=r"^[a-f0-9]{64}$")
    confirmation: Literal["DELETE_CLOUD_COPY"]


class JournalSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    entry_date: date
    title: str
    revision: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_time(self, value: datetime) -> str:
        return value.replace(tzinfo=timezone.utc).isoformat()


class JournalRead(JournalSummary):
    content: str


class JournalDay(BaseModel):
    entry_date: date
    entry: JournalRead | None


class JournalPage(BaseModel):
    items: list[JournalSummary]
    total: int
    page: int
    page_size: int
