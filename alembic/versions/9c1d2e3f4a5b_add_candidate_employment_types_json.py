"""add candidate employment types json

Revision ID: 9c1d2e3f4a5b
Revises: 7a8b9c0d1e2f
Create Date: 2026-03-24 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "9c1d2e3f4a5b"
down_revision = "7a8b9c0d1e2f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column("employment_types_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candidate_profiles", "employment_types_json")
