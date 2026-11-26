"""Phase 6: original Markdown and TXT resources."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME, MEDIUMBLOB

from alembic import op

revision = "0009_documents"
down_revision = "0008_note_folders"
branch_labels = None
depends_on = None


def upgrade():
    precise = sa.DateTime().with_variant(DATETIME(fsp=6), "mysql")
    op.create_table(
        "documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "raw_content", sa.LargeBinary().with_variant(MEDIUMBLOB(), "mysql"), nullable=False
        ),
        sa.Column("revision", sa.String(36), nullable=False),
        sa.Column("created_at", precise, nullable=False),
        sa.Column("updated_at", precise, nullable=False),
        sa.CheckConstraint("kind IN ('markdown', 'text')", name="ck_documents_kind"),
        sa.CheckConstraint("size_bytes > 0 AND size_bytes <= 524288", name="ck_documents_size"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_documents_user_created", "documents", ["user_id", "created_at", "id"])


def downgrade():
    op.drop_table("documents")
