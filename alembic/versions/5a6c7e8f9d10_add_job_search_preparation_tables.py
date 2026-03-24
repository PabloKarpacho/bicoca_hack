"""add job search preparation tables

Revision ID: 5a6c7e8f9d10
Revises: 4b5d7e2a9c31
Create Date: 2026-03-20 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "5a6c7e8f9d10"
down_revision = "4b5d7e2a9c31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_search_profiles",
        sa.Column("job_search_profile_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=100), nullable=False),
        sa.Column("source_document_id", sa.String(length=100), nullable=True),
        sa.Column("raw_title", sa.String(length=255), nullable=True),
        sa.Column("normalized_title", sa.String(length=255), nullable=True),
        sa.Column("seniority_normalized", sa.String(length=100), nullable=True),
        sa.Column("location_raw", sa.String(length=255), nullable=True),
        sa.Column("location_normalized", sa.String(length=255), nullable=True),
        sa.Column("remote_policy", sa.String(length=100), nullable=True),
        sa.Column("employment_type", sa.String(length=100), nullable=True),
        sa.Column("min_experience_months", sa.Integer(), nullable=True),
        sa.Column("education_requirements", sa.Text(), nullable=True),
        sa.Column("certification_requirements", sa.Text(), nullable=True),
        sa.Column("semantic_query_text_main", sa.Text(), nullable=False),
        sa.Column("semantic_query_text_responsibilities", sa.Text(), nullable=True),
        sa.Column("semantic_query_text_skills", sa.Text(), nullable=True),
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column("pipeline_version", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=255), nullable=True),
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
        sa.PrimaryKeyConstraint("job_search_profile_id"),
        sa.UniqueConstraint("job_id", name="uq_job_search_profile_job_id"),
    )
    op.create_index(
        "idx_job_search_profile_job_id",
        "job_search_profiles",
        ["job_id"],
        unique=False,
    )
    op.create_index(
        "idx_job_search_profile_title",
        "job_search_profiles",
        ["normalized_title"],
        unique=False,
    )
    op.create_index(
        "idx_job_search_profile_seniority",
        "job_search_profiles",
        ["seniority_normalized"],
        unique=False,
    )
    op.create_index(
        op.f("ix_job_search_profiles_job_search_profile_id"),
        "job_search_profiles",
        ["job_search_profile_id"],
        unique=False,
    )

    op.create_table(
        "job_required_languages",
        sa.Column("job_required_language_id", sa.String(length=36), nullable=False),
        sa.Column("job_search_profile_id", sa.String(length=36), nullable=False),
        sa.Column("language_normalized", sa.String(length=255), nullable=False),
        sa.Column("min_proficiency_normalized", sa.String(length=100), nullable=True),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["job_search_profile_id"],
            ["job_search_profiles.job_search_profile_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("job_required_language_id"),
    )
    op.create_index(
        "idx_job_required_language_profile_id",
        "job_required_languages",
        ["job_search_profile_id"],
        unique=False,
    )
    op.create_index(
        "idx_job_required_language_name",
        "job_required_languages",
        ["language_normalized"],
        unique=False,
    )
    op.create_index(
        op.f("ix_job_required_languages_job_required_language_id"),
        "job_required_languages",
        ["job_required_language_id"],
        unique=False,
    )

    op.create_table(
        "job_required_skills",
        sa.Column("job_required_skill_id", sa.String(length=36), nullable=False),
        sa.Column("job_search_profile_id", sa.String(length=36), nullable=False),
        sa.Column("normalized_skill", sa.String(length=255), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("source_type", sa.String(length=100), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["job_search_profile_id"],
            ["job_search_profiles.job_search_profile_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("job_required_skill_id"),
    )
    op.create_index(
        "idx_job_required_skill_profile_id",
        "job_required_skills",
        ["job_search_profile_id"],
        unique=False,
    )
    op.create_index(
        "idx_job_required_skill_name",
        "job_required_skills",
        ["normalized_skill"],
        unique=False,
    )
    op.create_index(
        op.f("ix_job_required_skills_job_required_skill_id"),
        "job_required_skills",
        ["job_required_skill_id"],
        unique=False,
    )

    op.create_table(
        "job_domains",
        sa.Column("job_domain_id", sa.String(length=36), nullable=False),
        sa.Column("job_search_profile_id", sa.String(length=36), nullable=False),
        sa.Column("domain_normalized", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["job_search_profile_id"],
            ["job_search_profiles.job_search_profile_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("job_domain_id"),
    )
    op.create_index(
        "idx_job_domain_profile_id",
        "job_domains",
        ["job_search_profile_id"],
        unique=False,
    )
    op.create_index(
        "idx_job_domain_name",
        "job_domains",
        ["domain_normalized"],
        unique=False,
    )
    op.create_index(
        op.f("ix_job_domains_job_domain_id"),
        "job_domains",
        ["job_domain_id"],
        unique=False,
    )

    op.create_table(
        "job_processing_runs",
        sa.Column("job_processing_run_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=100), nullable=False),
        sa.Column("source_document_id", sa.String(length=100), nullable=True),
        sa.Column("pipeline_stage", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=100), nullable=False),
        sa.Column("pipeline_version", sa.String(length=100), nullable=False),
        sa.Column("model_version", sa.String(length=255), nullable=True),
        sa.Column("extraction_confidence", sa.Float(), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("job_processing_run_id"),
        sa.UniqueConstraint("job_id", "pipeline_stage", name="uq_job_processing_run_job_stage"),
    )
    op.create_index(
        "idx_job_processing_run_job_id",
        "job_processing_runs",
        ["job_id"],
        unique=False,
    )
    op.create_index(
        "idx_job_processing_run_stage",
        "job_processing_runs",
        ["pipeline_stage"],
        unique=False,
    )
    op.create_index(
        "idx_job_processing_run_status",
        "job_processing_runs",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_job_processing_runs_job_processing_run_id"),
        "job_processing_runs",
        ["job_processing_run_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_job_processing_runs_job_processing_run_id"),
        table_name="job_processing_runs",
    )
    op.drop_index("idx_job_processing_run_status", table_name="job_processing_runs")
    op.drop_index("idx_job_processing_run_stage", table_name="job_processing_runs")
    op.drop_index("idx_job_processing_run_job_id", table_name="job_processing_runs")
    op.drop_table("job_processing_runs")

    op.drop_index(op.f("ix_job_domains_job_domain_id"), table_name="job_domains")
    op.drop_index("idx_job_domain_name", table_name="job_domains")
    op.drop_index("idx_job_domain_profile_id", table_name="job_domains")
    op.drop_table("job_domains")

    op.drop_index(
        op.f("ix_job_required_skills_job_required_skill_id"),
        table_name="job_required_skills",
    )
    op.drop_index("idx_job_required_skill_name", table_name="job_required_skills")
    op.drop_index("idx_job_required_skill_profile_id", table_name="job_required_skills")
    op.drop_table("job_required_skills")

    op.drop_index(
        op.f("ix_job_required_languages_job_required_language_id"),
        table_name="job_required_languages",
    )
    op.drop_index("idx_job_required_language_name", table_name="job_required_languages")
    op.drop_index(
        "idx_job_required_language_profile_id",
        table_name="job_required_languages",
    )
    op.drop_table("job_required_languages")

    op.drop_index(
        op.f("ix_job_search_profiles_job_search_profile_id"),
        table_name="job_search_profiles",
    )
    op.drop_index("idx_job_search_profile_seniority", table_name="job_search_profiles")
    op.drop_index("idx_job_search_profile_title", table_name="job_search_profiles")
    op.drop_index("idx_job_search_profile_job_id", table_name="job_search_profiles")
    op.drop_table("job_search_profiles")
