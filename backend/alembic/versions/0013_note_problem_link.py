"""Optional problem association for notes."""

import sqlalchemy as sa

from alembic import op

revision = "0013_note_problem_link"
down_revision = "0012_problem_memos"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("notes", sa.Column("problem_id", sa.String(36), nullable=True))
    op.create_index("ix_notes_problem_id", "notes", ["problem_id"])
    op.create_foreign_key(
        "fk_notes_problem", "notes", "problems", ["problem_id"], ["id"], ondelete="SET NULL"
    )


def downgrade():
    if op.get_bind().scalar(sa.text("SELECT COUNT(*) FROM notes WHERE problem_id IS NOT NULL")):
        raise RuntimeError("Unlink note problems before downgrading")
    op.drop_constraint("fk_notes_problem", "notes", type_="foreignkey")
    op.drop_index("ix_notes_problem_id", table_name="notes")
    op.drop_column("notes", "problem_id")
