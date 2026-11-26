from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "FocusNest"
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]
    mysql_host: str = "127.0.0.1"
    mysql_port: int = Field(default=3306, ge=1, le=65535)
    mysql_database: str = "focusnest"
    mysql_user: str = "focusnest"
    mysql_password: SecretStr = SecretStr("")

    jwt_secret: SecretStr = SecretStr("")
    access_token_minutes: int = Field(default=15, ge=1, le=60)
    refresh_token_days: int = Field(default=7, ge=1, le=30)
    cookie_secure: bool = False

    # Only the location is configured here; content keys never belong in .env.
    content_keyring_file: Path | None = Field(default=None, repr=False)

    @field_validator("content_keyring_file", mode="before")
    @classmethod
    def empty_keyring_path(cls, value):
        return None if isinstance(value, str) and not value.strip() else value

    @property
    def database_url(self) -> URL:
        # URL.create safely handles passwords containing @, %, / and other symbols.
        return URL.create(
            "mysql+pymysql",
            username=self.mysql_user,
            password=self.mysql_password.get_secret_value(),
            host=self.mysql_host,
            port=self.mysql_port,
            database=self.mysql_database,
            query={"charset": "utf8mb4"},
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
