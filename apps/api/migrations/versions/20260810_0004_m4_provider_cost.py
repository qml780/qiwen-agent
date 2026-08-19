"""Track provider cost in the shared monthly budget.

Revision ID: 20260810_0004
Revises: 20260810_0003
"""
from alembic import op
import sqlalchemy as sa

revision = "20260810_0004"
down_revision = "20260810_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("provider_jobs", sa.Column("cost_cny", sa.Numeric(12,6), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("provider_jobs", "cost_cny")
