"""add remote policies json fields

Revision ID: 7a8b9c0d1e2f
Revises: 6b7c8d9e0f11
Create Date: 2026-03-21 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "7a8b9c0d1e2f"
down_revision = "6b7c8d9e0f11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_profiles",
        sa.Column("remote_policies_json", sa.Text(), nullable=True),
    )
    op.add_column(
        "job_search_profiles",
        sa.Column("remote_policies_json", sa.Text(), nullable=True),
    )
    op.execute(
        """
        UPDATE job_search_profiles
        SET remote_policies_json = CASE
            WHEN remote_policy IS NULL OR btrim(remote_policy) = '' THEN NULL
            ELSE '["' || replace(remote_policy, '"', '\\"') || '"]'
        END
        WHERE remote_policies_json IS NULL
        """
    )


def downgrade() -> None:
    op.drop_column("job_search_profiles", "remote_policies_json")
    op.drop_column("candidate_profiles", "remote_policies_json")
