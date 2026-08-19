"""Persist approved Unity co-creation previews, checkpoints and receipts.

Revision ID: 20260810_0005
Revises: 20260810_0004
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260810_0005"
down_revision = "20260810_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "unity_changes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.String(80)),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("request_payload", postgresql.JSONB(), nullable=False),
        sa.Column("preview_payload", postgresql.JSONB(), nullable=False),
        sa.Column("receipt_payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("checkpoint_path", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("undone_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_unity_changes_project_id", "unity_changes", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_unity_changes_project_id", table_name="unity_changes")
    op.drop_table("unity_changes")
