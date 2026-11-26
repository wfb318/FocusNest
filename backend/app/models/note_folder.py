from uuid import uuid4

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class NoteFolder(Base):
    __tablename__ = "note_folders"
    __table_args__ = (
        Index("ix_note_folders_user_parent", "user_id", "parent_id"),
        {"mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"},
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    parent_id: Mapped[str | None] = mapped_column(
        ForeignKey("note_folders.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(100))
    revision: Mapped[str] = mapped_column(String(36), default=lambda: str(uuid4()))
