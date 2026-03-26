"""add job search employment types json

Revision ID: a1b2c3d4e5f6
Revises: 9c1d2e3f4a5b
Create Date: 2026-03-26 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "9c1d2e3f4a5b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_search_profiles",
        sa.Column("employment_types_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("job_search_profiles", "employment_types_json")
