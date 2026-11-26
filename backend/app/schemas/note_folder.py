from pydantic import BaseModel, ConfigDict, Field, field_validator


class FolderName(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=100)

    @field_validator("name")
    @classmethod
    def valid_name(cls, value: str) -> str:
        value = value.strip()
        if not value or value in (".", "..") or any(c in value for c in "/\\"):
            raise ValueError("Invalid folder name")
        if any(ord(c) < 32 for c in value):
            raise ValueError("Invalid folder name")
        return value


class FolderCreate(FolderName):
    parent_id: str | None = Field(default=None, min_length=36, max_length=36)


class FolderRename(FolderName):
    expected_revision: str = Field(min_length=36, max_length=36)


class FolderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    parent_id: str | None
    name: str
    revision: str
