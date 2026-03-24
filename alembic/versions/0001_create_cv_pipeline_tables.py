"""create cv pipeline tables"""

from alembic import op
import sqlalchemy as sa


revision = "0001_create_cv_pipeline_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidates",
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("external_id", sa.String(length=100), nullable=True),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("candidate_id"),
    )
    op.create_index("idx_candidate_created_at", "candidates", ["created_at"])
    op.create_index("idx_candidate_email", "candidates", ["email"])
    op.create_index("idx_candidate_external_id", "candidates", ["external_id"])

    op.create_table(
        "candidate_documents",
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("file_extension", sa.String(length=20), nullable=False),
        sa.Column("content_type", sa.String(length=100), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_bucket", sa.String(length=100), nullable=True),
        sa.Column("storage_key", sa.String(length=512), nullable=True),
        sa.Column("processing_status", sa.String(length=32), nullable=False),
        sa.Column("indexing_status", sa.String(length=32), nullable=False, server_default="pending"),
        sa.Column("extractor_name", sa.String(length=100), nullable=True),
        sa.Column("extracted_char_count", sa.BigInteger(), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.candidate_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_id"),
        sa.UniqueConstraint("candidate_id", "checksum_sha256", name="uq_candidate_document_candidate_checksum"),
    )
    op.create_index("idx_candidate_document_candidate_id", "candidate_documents", ["candidate_id"])
    op.create_index("idx_candidate_document_checksum", "candidate_documents", ["checksum_sha256"])
    op.create_index("idx_candidate_document_status", "candidate_documents", ["processing_status"])

    op.create_table(
        "candidate_document_texts",
        sa.Column("document_text_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["candidate_documents.document_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("document_text_id"),
        sa.UniqueConstraint("document_id", name="uq_candidate_document_text_document_id"),
    )


def downgrade() -> None:
    op.drop_table("candidate_document_texts")
    op.drop_index("idx_candidate_document_status", table_name="candidate_documents")
    op.drop_index("idx_candidate_document_checksum", table_name="candidate_documents")
    op.drop_index("idx_candidate_document_candidate_id", table_name="candidate_documents")
    op.drop_table("candidate_documents")
    op.drop_index("idx_candidate_external_id", table_name="candidates")
    op.drop_index("idx_candidate_email", table_name="candidates")
    op.drop_index("idx_candidate_created_at", table_name="candidates")
    op.drop_table("candidates")
