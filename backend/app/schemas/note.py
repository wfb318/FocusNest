from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

NoteStorageMode = Literal["cloud", "cloud_encrypted"]


class NoteBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=100000)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title cannot be blank")
        return value.strip()

    @field_validator("content")
    @classmethod
    def nonblank_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Content cannot be blank")
        return value


class NoteCreate(NoteBody):
    pinned: bool = Field(default=False, strict=True)
    folder_id: str | None = Field(default=None, min_length=36, max_length=36)
    problem_id: str | None = Field(default=None, min_length=36, max_length=36)
    storage_mode: NoteStorageMode = "cloud"


class NoteUpdate(NoteCreate):
    expected_revision: str = Field(min_length=36, max_length=36)


class NoteStorageChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    storage_mode: NoteStorageMode
    expected_revision: str = Field(min_length=36, max_length=36)


class NoteSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    storage_mode: NoteStorageMode
    pinned: bool
    folder_id: str | None
    problem_id: str | None
    revision: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_time(self, value: datetime) -> str:
        return value.replace(tzinfo=timezone.utc).isoformat()


class NoteRead(NoteSummary):
    content: str


class NotePage(BaseModel):
    items: list[NoteSummary]
    total: int
    page: int
    page_size: int
