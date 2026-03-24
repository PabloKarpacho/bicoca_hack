"""add hh skill normalization fields

Revision ID: 2c4a9e7b1d11
Revises: 1f7c6d8e9b10
Create Date: 2026-03-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "2c4a9e7b1d11"
down_revision = "1f7c6d8e9b10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "candidate_skills",
        sa.Column("normalization_source", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "candidate_skills",
        sa.Column("normalization_external_id", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "candidate_skills",
        sa.Column("normalization_status", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "candidate_skills",
        sa.Column("normalization_confidence", sa.Float(), nullable=True),
    )
    op.add_column(
        "candidate_skills",
        sa.Column("normalization_metadata_json", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("candidate_skills", "normalization_metadata_json")
    op.drop_column("candidate_skills", "normalization_confidence")
    op.drop_column("candidate_skills", "normalization_status")
    op.drop_column("candidate_skills", "normalization_external_id")
    op.drop_column("candidate_skills", "normalization_source")
