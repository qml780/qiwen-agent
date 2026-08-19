"""Persist playtest, feedback and revision loops.

Revision ID: 20260810_0006
Revises: 20260810_0005
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260810_0006"
down_revision = "20260810_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "playtest_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("build_job_id", sa.String(36)),
        sa.Column("logic_version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("initial_feedback", sa.Text()),
        sa.Column("initial_rating", sa.Integer()),
        sa.Column("revision_change_id", sa.String(36), sa.ForeignKey("unity_changes.id", ondelete="SET NULL")),
        sa.Column("final_feedback", sa.Text()),
        sa.Column("final_rating", sa.Integer()),
        sa.Column("evidence", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_playtest_sessions_project_id", "playtest_sessions", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_playtest_sessions_project_id", table_name="playtest_sessions")
    op.drop_table("playtest_sessions")
