"""Add an opt-in journal store without plaintext title or body columns."""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME, MEDIUMTEXT

from alembic import op

revision = "0015_encrypted_journals"
down_revision = "0014_note_encryption"
branch_labels = None
depends_on = None


def upgrade() -> None:
    timestamp = sa.DateTime().with_variant(DATETIME(fsp=6), "mysql")
    op.create_table(
        "encrypted_journals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("entry_date", sa.Date, nullable=False),
        sa.Column(
            "encrypted_payload", sa.Text().with_variant(MEDIUMTEXT(), "mysql"), nullable=False
        ),
        sa.Column("revision", sa.String(36), nullable=False),
        sa.Column("created_at", timestamp, nullable=False),
        sa.Column("updated_at", timestamp, nullable=False),
        sa.UniqueConstraint("user_id", "entry_date", name="uq_encrypted_journals_user_date"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )


def downgrade() -> None:
    if op.get_bind().scalar(sa.text("SELECT 1 FROM encrypted_journals LIMIT 1")):
        raise RuntimeError("Export and remove encrypted journals before downgrading")
    op.drop_table("encrypted_journals")
