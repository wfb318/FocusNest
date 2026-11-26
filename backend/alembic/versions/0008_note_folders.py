"""Hierarchical note folders; existing notes remain unfiled."""

import sqlalchemy as sa

from alembic import op

revision = "0008_note_folders"
down_revision = "0007_notes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "note_folders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "parent_id", sa.String(36), sa.ForeignKey("note_folders.id", ondelete="RESTRICT")
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("revision", sa.String(36), nullable=False),
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("ix_note_folders_user_parent", "note_folders", ["user_id", "parent_id"])
    op.add_column("notes", sa.Column("folder_id", sa.String(36), nullable=True))
    op.create_index("ix_notes_folder_id", "notes", ["folder_id"])
    op.create_foreign_key(
        "fk_notes_folder", "notes", "note_folders", ["folder_id"], ["id"], ondelete="SET NULL"
    )


def downgrade():
    op.drop_constraint("fk_notes_folder", "notes", type_="foreignkey")
    op.drop_index("ix_notes_folder_id", table_name="notes")
    op.drop_column("notes", "folder_id")
    op.drop_table("note_folders")
