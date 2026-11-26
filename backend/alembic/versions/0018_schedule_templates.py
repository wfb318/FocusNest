"""Add reusable schedule templates and week choices."""

import sqlalchemy as sa

from alembic import op

revision = "0018_schedule_templates"
down_revision = "0017_content_migration_receipts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "schedule_exceptions",
        sa.Column("replaced", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.create_table(
        "schedule_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("entries", sa.JSON(), nullable=False),
        sa.UniqueConstraint("user_id", "name", name="uq_schedule_template_name"),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_table(
        "schedule_week_plans",
        sa.Column(
            "user_id",
            sa.String(36),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("week_start", sa.Date(), primary_key=True),
        sa.Column(
            "template_id",
            sa.String(36),
            sa.ForeignKey("schedule_templates.id", ondelete="SET NULL"),
        ),
        sa.Column("reviewed", sa.Boolean(), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text("SELECT 1 FROM schedule_week_plans LIMIT 1")
    ) or op.get_bind().scalar(sa.text("SELECT 1 FROM schedule_templates LIMIT 1")):
        raise RuntimeError("Cannot downgrade while schedule template data exists")
    op.drop_table("schedule_week_plans")
    op.drop_table("schedule_templates")
    op.drop_column("schedule_exceptions", "replaced")
