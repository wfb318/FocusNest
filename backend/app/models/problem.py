from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.mysql import DATETIME
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.user import utcnow

PRECISE_TIME = DateTime().with_variant(DATETIME(fsp=6), "mysql")


class Problem(Base):
    __tablename__ = "problems"
    __table_args__ = (
        CheckConstraint(
            "(is_resolved = 0 AND resolved_at IS NULL) OR "
            "(is_resolved = 1 AND resolved_at IS NOT NULL)",
            name="problem_resolution",
        ),
        Index("ix_problems_user_status_created", "user_id", "is_resolved", "created_at", "id"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    content: Mapped[str] = mapped_column(Text)
    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[datetime | None] = mapped_column(PRECISE_TIME)
    revision: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(PRECISE_TIME, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(PRECISE_TIME, default=utcnow, onupdate=utcnow)
