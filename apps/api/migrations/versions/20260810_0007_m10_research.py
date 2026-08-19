"""Complete approval metadata and persist anonymous research exports.

Revision ID: 20260810_0007
Revises: 20260810_0006
"""
from alembic import op
import sqlalchemy as sa

revision = "20260810_0007"
down_revision = "20260810_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("approvals", sa.Column("stage", sa.String(40), nullable=False, server_default=""))
    op.add_column("approvals", sa.Column("status", sa.String(24), nullable=False, server_default="approved"))
    op.add_column("approvals", sa.Column("approved_by", sa.String(40), nullable=False, server_default="player"))
    op.add_column("approvals", sa.Column("comment", sa.Text(), nullable=False, server_default=""))
    op.execute("UPDATE approvals SET stage = artifact WHERE stage = ''")
    op.create_table(
        "research_exports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("project_id", sa.String(36), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("format", sa.String(8), nullable=False),
        sa.Column("anonymized_project_id", sa.String(32), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_research_exports_project_id", "research_exports", ["project_id"])


def downgrade() -> None:
    op.drop_index("ix_research_exports_project_id", table_name="research_exports")
    op.drop_table("research_exports")
    op.drop_column("approvals", "comment")
    op.drop_column("approvals", "approved_by")
    op.drop_column("approvals", "status")
    op.drop_column("approvals", "stage")
