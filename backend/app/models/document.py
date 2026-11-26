from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
)
from sqlalchemy.dialects.mysql import DATETIME, MEDIUMBLOB, MEDIUMTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.user import utcnow


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("ix_documents_user_created", "user_id", "created_at", "id"),
        CheckConstraint(
            "kind IN ('markdown','text','pdf','word','presentation','spreadsheet')",
            name="ck_documents_kind",
        ),
        CheckConstraint("size_bytes > 0 AND size_bytes <= 10485760", name="ck_documents_size"),
        CheckConstraint(
            "(storage_mode = 'cloud' AND title IS NOT NULL AND filename IS NOT NULL "
            "AND raw_content IS NOT NULL AND encrypted_file IS NULL "
            "AND encrypted_metadata IS NULL) OR "
            "(storage_mode = 'cloud_encrypted' AND title IS NULL AND filename IS NULL "
            "AND raw_content IS NULL AND preview_data IS NULL "
            "AND encrypted_file IS NOT NULL AND encrypted_metadata IS NOT NULL)",
            name="ck_documents_storage_payload",
        ),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str | None] = mapped_column(String(200))
    filename: Mapped[str | None] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(16))
    size_bytes: Mapped[int] = mapped_column(Integer)
    raw_content: Mapped[bytes | None] = mapped_column(
        LargeBinary().with_variant(MEDIUMBLOB(), "mysql"), deferred=True
    )
    preview_data: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    storage_mode: Mapped[str] = mapped_column(String(24), server_default="cloud")
    encrypted_file: Mapped[str | None] = mapped_column(
        Text().with_variant(MEDIUMTEXT(), "mysql"), deferred=True
    )
    encrypted_metadata: Mapped[str | None] = mapped_column(
        Text().with_variant(MEDIUMTEXT(), "mysql"), deferred=True
    )
    revision: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid4()))
    created_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(DATETIME(fsp=6), "mysql"), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime().with_variant(DATETIME(fsp=6), "mysql"), default=utcnow, onupdate=utcnow
    )
