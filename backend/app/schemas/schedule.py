from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ScheduleFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    notes: str = Field(default="", max_length=10000)
    start_minute: int = Field(ge=0, le=1439, strict=True)
    end_minute: int = Field(ge=1, le=1440, strict=True)
    task_id: str | None = Field(default=None, min_length=1, max_length=36)
    timer_enabled: bool = False
    remind_start: bool = True
    remind_end: bool = True

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title cannot be blank")
        return value.strip()

    @model_validator(mode="after")
    def valid_times(self):
        if self.start_minute >= self.end_minute:
            raise ValueError("End must be later than start within the same day")
        return self


class ScheduleCreate(ScheduleFields):
    weekday: int = Field(ge=0, le=6, strict=True)
    effective_from: date
    timezone: str = Field(max_length=64)
    repeat_weekly: bool = True

    @field_validator("timezone")
    @classmethod
    def valid_zone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Unknown timezone") from None
        return value


class ScheduleEdit(ScheduleFields):
    scope: Literal["single", "future"]
    occurrence_date: date
    revision: int = Field(ge=1, strict=True)
    weekday: int = Field(ge=0, le=6, strict=True)


class ScheduleRemove(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scope: Literal["single", "future"]
    occurrence_date: date
    revision: int = Field(ge=1, strict=True)


class Occurrence(ScheduleFields):
    schedule_id: str
    key: str
    occurrence_date: date
    weekday: int
    timezone: str
    starts_at: datetime | None
    ends_at: datetime | None
    skipped: bool
    time_warning: bool = False
    overridden: bool
    revision: int
    repeats: bool


class ScheduleWeek(BaseModel):
    items: list[Occurrence]
    server_now: datetime
    template_id: str | None = None


class ScheduleTemplateSave(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=80)
    week_start: date


class ScheduleTemplateApply(BaseModel):
    model_config = ConfigDict(extra="forbid")
    week_start: date
    expected_template_id: str | None = Field(max_length=36)


class ScheduleTemplateRead(BaseModel):
    id: str
    name: str
    entry_count: int


class ScheduleTemplateReview(BaseModel):
    week_start: date
    current_template_id: str | None
    planned_template_id: str | None
