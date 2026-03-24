"""add candidate entity tables"""

from alembic import op
import sqlalchemy as sa


revision = "1f7c6d8e9b10"
down_revision = "8edeaf901b1c"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "candidate_profiles",
        sa.Column("profile_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone", sa.String(length=100), nullable=True),
        sa.Column("location_raw", sa.String(length=255), nullable=True),
        sa.Column("linkedin_url", sa.String(length=500), nullable=True),
        sa.Column("github_url", sa.String(length=500), nullable=True),
        sa.Column("portfolio_url", sa.String(length=500), nullable=True),
        sa.Column("headline", sa.String(length=255), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("current_title_raw", sa.String(length=255), nullable=True),
        sa.Column("current_title_normalized", sa.String(length=255), nullable=True),
        sa.Column("seniority_normalized", sa.String(length=100), nullable=True),
        sa.Column("total_experience_months", sa.Integer(), nullable=True),
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.candidate_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["candidate_documents.document_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("profile_id"),
        sa.UniqueConstraint("document_id", name="uq_candidate_profile_document_id"),
    )
    op.create_index("idx_candidate_profile_candidate_id", "candidate_profiles", ["candidate_id"], unique=False)
    op.create_index(op.f("ix_candidate_profiles_profile_id"), "candidate_profiles", ["profile_id"], unique=False)

    op.create_table(
        "candidate_languages",
        sa.Column("language_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("language_raw", sa.String(length=255), nullable=True),
        sa.Column("language_normalized", sa.String(length=255), nullable=True),
        sa.Column("proficiency_raw", sa.String(length=255), nullable=True),
        sa.Column("proficiency_normalized", sa.String(length=100), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.candidate_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["candidate_documents.document_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("language_id"),
    )
    op.create_index("idx_candidate_language_candidate_id", "candidate_languages", ["candidate_id"], unique=False)
    op.create_index("idx_candidate_language_document_id", "candidate_languages", ["document_id"], unique=False)
    op.create_index("idx_candidate_language_name", "candidate_languages", ["language_normalized"], unique=False)
    op.create_index(op.f("ix_candidate_languages_language_id"), "candidate_languages", ["language_id"], unique=False)

    op.create_table(
        "candidate_experiences",
        sa.Column("experience_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("position_order", sa.Integer(), nullable=False),
        sa.Column("company_name_raw", sa.String(length=255), nullable=True),
        sa.Column("job_title_raw", sa.String(length=255), nullable=True),
        sa.Column("job_title_normalized", sa.String(length=255), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False),
        sa.Column("duration_months", sa.Integer(), nullable=True),
        sa.Column("location_raw", sa.String(length=255), nullable=True),
        sa.Column("responsibilities_text", sa.Text(), nullable=True),
        sa.Column("technologies_text", sa.Text(), nullable=True),
        sa.Column("domain_hint", sa.String(length=255), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.candidate_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["candidate_documents.document_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("experience_id"),
    )
    op.create_index("idx_candidate_experience_candidate_id", "candidate_experiences", ["candidate_id"], unique=False)
    op.create_index("idx_candidate_experience_document_id", "candidate_experiences", ["document_id"], unique=False)
    op.create_index("idx_candidate_experience_title", "candidate_experiences", ["job_title_normalized"], unique=False)
    op.create_index(op.f("ix_candidate_experiences_experience_id"), "candidate_experiences", ["experience_id"], unique=False)

    op.create_table(
        "candidate_skills",
        sa.Column("skill_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("raw_skill", sa.String(length=255), nullable=True),
        sa.Column("normalized_skill", sa.String(length=255), nullable=True),
        sa.Column("skill_category", sa.String(length=100), nullable=True),
        sa.Column("source_type", sa.String(length=100), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.candidate_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["candidate_documents.document_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("skill_id"),
    )
    op.create_index("idx_candidate_skill_candidate_id", "candidate_skills", ["candidate_id"], unique=False)
    op.create_index("idx_candidate_skill_document_id", "candidate_skills", ["document_id"], unique=False)
    op.create_index("idx_candidate_skill_name", "candidate_skills", ["normalized_skill"], unique=False)
    op.create_index(op.f("ix_candidate_skills_skill_id"), "candidate_skills", ["skill_id"], unique=False)

    op.create_table(
        "candidate_education",
        sa.Column("education_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("position_order", sa.Integer(), nullable=False),
        sa.Column("institution_raw", sa.String(length=255), nullable=True),
        sa.Column("degree_raw", sa.String(length=255), nullable=True),
        sa.Column("degree_normalized", sa.String(length=255), nullable=True),
        sa.Column("field_of_study", sa.String(length=255), nullable=True),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.candidate_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["candidate_documents.document_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("education_id"),
    )
    op.create_index("idx_candidate_education_candidate_id", "candidate_education", ["candidate_id"], unique=False)
    op.create_index("idx_candidate_education_document_id", "candidate_education", ["document_id"], unique=False)
    op.create_index(op.f("ix_candidate_education_education_id"), "candidate_education", ["education_id"], unique=False)

    op.create_table(
        "candidate_certifications",
        sa.Column("certification_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("certification_name_raw", sa.String(length=255), nullable=True),
        sa.Column("certification_name_normalized", sa.String(length=255), nullable=True),
        sa.Column("issuer", sa.String(length=255), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.candidate_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["candidate_documents.document_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("certification_id"),
    )
    op.create_index("idx_candidate_certification_candidate_id", "candidate_certifications", ["candidate_id"], unique=False)
    op.create_index("idx_candidate_certification_document_id", "candidate_certifications", ["document_id"], unique=False)
    op.create_index(op.f("ix_candidate_certifications_certification_id"), "candidate_certifications", ["certification_id"], unique=False)

    op.create_table(
        "document_processing_runs",
        sa.Column("processing_run_id", sa.String(length=36), nullable=False),
        sa.Column("document_id", sa.String(length=36), nullable=False),
        sa.Column("candidate_id", sa.String(length=36), nullable=True),
        sa.Column("processing_stage", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=100), nullable=False),
        sa.Column("pipeline_version", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=255), nullable=True),
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidates.candidate_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["candidate_documents.document_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("processing_run_id"),
        sa.UniqueConstraint("document_id", "processing_stage", name="uq_document_processing_run_document_stage"),
    )
    op.create_index("idx_document_processing_run_candidate_id", "document_processing_runs", ["candidate_id"], unique=False)
    op.create_index("idx_document_processing_run_document_id", "document_processing_runs", ["document_id"], unique=False)
    op.create_index("idx_document_processing_run_stage", "document_processing_runs", ["processing_stage"], unique=False)
    op.create_index("idx_document_processing_run_status", "document_processing_runs", ["status"], unique=False)
    op.create_index(op.f("ix_document_processing_runs_processing_run_id"), "document_processing_runs", ["processing_run_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_document_processing_runs_processing_run_id"), table_name="document_processing_runs")
    op.drop_index("idx_document_processing_run_status", table_name="document_processing_runs")
    op.drop_index("idx_document_processing_run_stage", table_name="document_processing_runs")
    op.drop_index("idx_document_processing_run_document_id", table_name="document_processing_runs")
    op.drop_index("idx_document_processing_run_candidate_id", table_name="document_processing_runs")
    op.drop_table("document_processing_runs")

    op.drop_index(op.f("ix_candidate_certifications_certification_id"), table_name="candidate_certifications")
    op.drop_index("idx_candidate_certification_document_id", table_name="candidate_certifications")
    op.drop_index("idx_candidate_certification_candidate_id", table_name="candidate_certifications")
    op.drop_table("candidate_certifications")

    op.drop_index(op.f("ix_candidate_education_education_id"), table_name="candidate_education")
    op.drop_index("idx_candidate_education_document_id", table_name="candidate_education")
    op.drop_index("idx_candidate_education_candidate_id", table_name="candidate_education")
    op.drop_table("candidate_education")

    op.drop_index(op.f("ix_candidate_skills_skill_id"), table_name="candidate_skills")
    op.drop_index("idx_candidate_skill_name", table_name="candidate_skills")
    op.drop_index("idx_candidate_skill_document_id", table_name="candidate_skills")
    op.drop_index("idx_candidate_skill_candidate_id", table_name="candidate_skills")
    op.drop_table("candidate_skills")

    op.drop_index(op.f("ix_candidate_experiences_experience_id"), table_name="candidate_experiences")
    op.drop_index("idx_candidate_experience_title", table_name="candidate_experiences")
    op.drop_index("idx_candidate_experience_document_id", table_name="candidate_experiences")
    op.drop_index("idx_candidate_experience_candidate_id", table_name="candidate_experiences")
    op.drop_table("candidate_experiences")

    op.drop_index(op.f("ix_candidate_languages_language_id"), table_name="candidate_languages")
    op.drop_index("idx_candidate_language_name", table_name="candidate_languages")
    op.drop_index("idx_candidate_language_document_id", table_name="candidate_languages")
    op.drop_index("idx_candidate_language_candidate_id", table_name="candidate_languages")
    op.drop_table("candidate_languages")

    op.drop_index(op.f("ix_candidate_profiles_profile_id"), table_name="candidate_profiles")
    op.drop_index("idx_candidate_profile_candidate_id", table_name="candidate_profiles")
    op.drop_table("candidate_profiles")
