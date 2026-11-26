from typing import Literal

from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: Literal["ok"] = "ok"
    database: Literal["not_checked", "connected"] = "not_checked"
