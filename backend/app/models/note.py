from datetime import datetime
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.dialects.mysql import DATETIME, MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.user import utcnow


class Note(Base):
    __tablename__ = "notes"
    __table_args__ = (
        CheckConstraint(
            "(storage_mode = 'cloud' AND title IS NOT NULL AND content IS NOT NULL "
            "AND encrypted_payload IS NULL AND content_revision IS NULL) OR "
            "(storage_mode = 'cloud_encrypted' AND title IS NULL AND content IS NULL "
            "AND encrypted_payload IS NOT NULL AND content_revision IS NOT NULL)",
            name="ck_notes_storage_payload",
        ),
        Index("ix_notes_user_pinned_updated", "user_id", "pinned", "updated_at", "id"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    folder_id: Mapped[str | None] = mapped_column(
        ForeignKey("note_folders.id", name="fk_notes_folder", ondelete="SET NULL"), index=True
    )
    title: Mapped[str | None] = mapped_column(String(200))
    problem_id: Mapped[str | None] = mapped_column(
        ForeignKey("problems.id", name="fk_notes_problem", ondelete="SET NULL"), index=True
    )
    content: Mapped[str | None] = mapped_column(Text().with_variant(MEDIUMTEXT(), "mysql"))
    storage_mode: Mapped[str] = mapped_column(String(24), server_default="cloud")
    encrypted_payload: Mapped[str | None] = mapped_column(
        Text().with_variant(MEDIUMTEXT(), "mysql")
    )
    # Metadata moves can change the edit revision without changing the protected content.
    content_revision: Mapped[str | None] = mapped_column(String(36))
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(DATETIME(fsp=6), "mysql"), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(DATETIME(fsp=6), "mysql"), default=utcnow, onupdate=utcnow
    )
