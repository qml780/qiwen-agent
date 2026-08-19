"""Link assistant messages to structured suggestions.

Revision ID: 20260810_0003
Revises: 20260810_0002
"""
from alembic import op
import sqlalchemy as sa

revision = "20260810_0003"
down_revision = "20260810_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("conversation_messages", sa.Column("suggestion_id", sa.String(36)))


def downgrade() -> None:
    op.drop_column("conversation_messages", "suggestion_id")
