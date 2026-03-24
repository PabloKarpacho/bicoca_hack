"""add entity normalizations table

Revision ID: 6b7c8d9e0f11
Revises: 5a6c7e8f9d10
Create Date: 2026-03-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "6b7c8d9e0f11"
down_revision = "5a6c7e8f9d10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "entity_normalizations",
        sa.Column("entity_normalization_id", sa.String(length=36), nullable=False),
        sa.Column("normalization_class", sa.String(length=100), nullable=False),
        sa.Column("original_value", sa.String(length=255), nullable=False),
        sa.Column("original_value_lookup", sa.String(length=255), nullable=False),
        sa.Column("normalized_value", sa.String(length=255), nullable=True),
        sa.Column("normalized_value_canonical", sa.String(length=255), nullable=True),
        sa.Column("normalization_status", sa.String(length=50), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=255), nullable=True),
        sa.Column("pipeline_version", sa.String(length=100), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("entity_normalization_id"),
        sa.UniqueConstraint(
            "normalization_class",
            "original_value_lookup",
            name="uq_entity_normalization_class_lookup",
        ),
    )
    op.create_index(
        "idx_entity_normalization_class",
        "entity_normalizations",
        ["normalization_class"],
        unique=False,
    )
    op.create_index(
        "idx_entity_normalization_status",
        "entity_normalizations",
        ["normalization_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_entity_normalizations_entity_normalization_id"),
        "entity_normalizations",
        ["entity_normalization_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_entity_normalizations_entity_normalization_id"),
        table_name="entity_normalizations",
    )
    op.drop_index("idx_entity_normalization_status", table_name="entity_normalizations")
    op.drop_index("idx_entity_normalization_class", table_name="entity_normalizations")
    op.drop_table("entity_normalizations")
