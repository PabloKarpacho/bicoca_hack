"""add candidate document chunks

Revision ID: 4b5d7e2a9c31
Revises: 39c1a8d4b2f0
Create Date: 2026-03-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "4b5d7e2a9c31"
down_revision = "39c1a8d4b2f0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_document_chunks",
        sa.Column("chunk_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("chunk_type", sa.String(length=100), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("chunk_hash", sa.String(length=64), nullable=False),
        sa.Column("source_entity_type", sa.String(length=100), nullable=True),
        sa.Column("source_entity_id", sa.String(length=36), nullable=True),
        sa.Column("chunk_metadata_json", sa.Text(), nullable=True),
        sa.Column("embedding_status", sa.String(length=50), nullable=False),
        sa.Column("embedding_model_version", sa.String(length=255), nullable=True),
        sa.Column("qdrant_point_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.candidate_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["candidate_documents.document_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("chunk_id"),
        sa.UniqueConstraint("document_id", "chunk_hash", name="uq_candidate_chunk_document_hash"),
    )
    op.create_index("idx_candidate_chunk_document_id", "candidate_document_chunks", ["document_id"], unique=False)
    op.create_index("idx_candidate_chunk_candidate_id", "candidate_document_chunks", ["candidate_id"], unique=False)
    op.create_index("idx_candidate_chunk_type", "candidate_document_chunks", ["chunk_type"], unique=False)
    op.create_index("idx_candidate_chunk_embedding_status", "candidate_document_chunks", ["embedding_status"], unique=False)
    op.create_index(op.f("ix_candidate_document_chunks_chunk_id"), "candidate_document_chunks", ["chunk_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_candidate_document_chunks_chunk_id"), table_name="candidate_document_chunks")
    op.drop_index("idx_candidate_chunk_embedding_status", table_name="candidate_document_chunks")
    op.drop_index("idx_candidate_chunk_type", table_name="candidate_document_chunks")
    op.drop_index("idx_candidate_chunk_candidate_id", table_name="candidate_document_chunks")
    op.drop_index("idx_candidate_chunk_document_id", table_name="candidate_document_chunks")
    op.drop_table("candidate_document_chunks")
