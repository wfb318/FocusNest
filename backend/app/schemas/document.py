from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, field_validator

DocumentKind = Literal["markdown", "text", "pdf", "word", "presentation", "spreadsheet"]
DocumentStorageMode = Literal["cloud", "cloud_encrypted"]


class PreviewSection(BaseModel):
    title: str
    paragraphs: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class DocumentPreview(BaseModel):
    sections: list[PreviewSection] = Field(default_factory=list)
    pages: int = 0
    truncated: bool = False


class DocumentRename(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    expected_revision: str = Field(min_length=36, max_length=36)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("Invalid title")
        return value


class DocumentStorageChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    storage_mode: DocumentStorageMode
    expected_revision: str = Field(min_length=36, max_length=36)


class DocumentMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    filename: str = Field(min_length=1, max_length=255)
    preview: DocumentPreview | None = None


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    title: str
    filename: str
    storage_mode: DocumentStorageMode
    kind: DocumentKind
    size_bytes: int
    revision: str
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_time(self, value: datetime) -> str:
        return value.replace(tzinfo=timezone.utc).isoformat()


class DocumentRead(DocumentSummary):
    content: str
    preview: DocumentPreview | None = None


class DocumentPage(BaseModel):
    items: list[DocumentSummary]
    total: int
    page: int
    page_size: int
