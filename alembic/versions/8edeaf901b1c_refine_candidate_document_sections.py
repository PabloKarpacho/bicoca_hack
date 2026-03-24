"""refine candidate document sections"""

from alembic import op
import sqlalchemy as sa


revision = "8edeaf901b1c"
down_revision = "183b2c5ef4f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "candidate_document_sections",
        "document_section_id",
        existing_type=sa.String(length=36),
        new_column_name="id",
        existing_nullable=False,
    )
    op.alter_column(
        "candidate_document_sections",
        "section_order",
        existing_type=sa.Integer(),
        new_column_name="position_order",
        existing_nullable=False,
    )
    op.alter_column(
        "candidate_document_sections",
        "title",
        existing_type=sa.String(length=255),
        new_column_name="title_raw",
        existing_nullable=True,
    )
    op.alter_column(
        "candidate_document_sections",
        "raw_text",
        existing_type=sa.Text(),
        new_column_name="content",
        existing_nullable=False,
    )
    op.alter_column(
        "candidate_document_sections",
        "start_char_index",
        existing_type=sa.Integer(),
        new_column_name="char_start",
        existing_nullable=True,
    )
    op.alter_column(
        "candidate_document_sections",
        "end_char_index",
        existing_type=sa.Integer(),
        new_column_name="char_end",
        existing_nullable=True,
    )

    op.add_column(
        "candidate_document_sections",
        sa.Column("title_normalized", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "candidate_document_sections",
        sa.Column("page_start", sa.Integer(), nullable=True),
    )
    op.add_column(
        "candidate_document_sections",
        sa.Column("page_end", sa.Integer(), nullable=True),
    )
    op.add_column(
        "candidate_document_sections",
        sa.Column("confidence", sa.Float(), nullable=True),
    )

    op.execute(
        sa.text(
            """
            UPDATE candidate_document_sections
            SET title_normalized = CASE
                    WHEN title_raw IS NULL THEN NULL
                    ELSE lower(regexp_replace(title_raw, '[:\\-\\s]+$', ''))
                END,
                confidence = CASE
                    WHEN title_raw IS NULL THEN 0.7
                    ELSE 1.0
                END
            """
        )
    )

    op.drop_constraint(
        "uq_candidate_document_section_document_order",
        "candidate_document_sections",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_candidate_document_section_document_position_order",
        "candidate_document_sections",
        ["document_id", "position_order"],
    )

    op.drop_index(
        "ix_candidate_document_sections_document_section_id",
        table_name="candidate_document_sections",
    )
    op.create_index(
        "ix_candidate_document_sections_id",
        "candidate_document_sections",
        ["id"],
        unique=False,
    )
    op.create_index(
        "idx_candidate_document_section_title_normalized",
        "candidate_document_sections",
        ["title_normalized"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "idx_candidate_document_section_title_normalized",
        table_name="candidate_document_sections",
    )
    op.drop_index(
        "ix_candidate_document_sections_id",
        table_name="candidate_document_sections",
    )
    op.create_index(
        "ix_candidate_document_sections_document_section_id",
        "candidate_document_sections",
        ["id"],
        unique=False,
    )

    op.drop_constraint(
        "uq_candidate_document_section_document_position_order",
        "candidate_document_sections",
        type_="unique",
    )
    op.create_unique_constraint(
        "uq_candidate_document_section_document_order",
        "candidate_document_sections",
        ["document_id", "position_order"],
    )

    op.drop_column("candidate_document_sections", "confidence")
    op.drop_column("candidate_document_sections", "page_end")
    op.drop_column("candidate_document_sections", "page_start")
    op.drop_column("candidate_document_sections", "title_normalized")

    op.alter_column(
        "candidate_document_sections",
        "char_end",
        existing_type=sa.Integer(),
        new_column_name="end_char_index",
        existing_nullable=True,
    )
    op.alter_column(
        "candidate_document_sections",
        "char_start",
        existing_type=sa.Integer(),
        new_column_name="start_char_index",
        existing_nullable=True,
    )
    op.alter_column(
        "candidate_document_sections",
        "content",
        existing_type=sa.Text(),
        new_column_name="raw_text",
        existing_nullable=False,
    )
    op.alter_column(
        "candidate_document_sections",
        "title_raw",
        existing_type=sa.String(length=255),
        new_column_name="title",
        existing_nullable=True,
    )
    op.alter_column(
        "candidate_document_sections",
        "position_order",
        existing_type=sa.Integer(),
        new_column_name="section_order",
        existing_nullable=False,
    )
    op.alter_column(
        "candidate_document_sections",
        "id",
        existing_type=sa.String(length=36),
        new_column_name="document_section_id",
        existing_nullable=False,
    )
