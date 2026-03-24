"""add rule search indexes

Revision ID: 39c1a8d4b2f0
Revises: 2c4a9e7b1d11
Create Date: 2026-03-20 00:00:00.000000
"""

from alembic import op


revision = "39c1a8d4b2f0"
down_revision = "2c4a9e7b1d11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "idx_candidate_profile_current_title",
        "candidate_profiles",
        ["current_title_normalized"],
        unique=False,
    )
    op.create_index(
        "idx_candidate_profile_seniority",
        "candidate_profiles",
        ["seniority_normalized"],
        unique=False,
    )
    op.create_index(
        "idx_candidate_profile_total_experience",
        "candidate_profiles",
        ["total_experience_months"],
        unique=False,
    )
    op.create_index(
        "idx_candidate_language_proficiency",
        "candidate_languages",
        ["proficiency_normalized"],
        unique=False,
    )
    op.create_index(
        "idx_candidate_experience_domain",
        "candidate_experiences",
        ["domain_hint"],
        unique=False,
    )
    op.create_index(
        "idx_candidate_education_degree",
        "candidate_education",
        ["degree_normalized"],
        unique=False,
    )
    op.create_index(
        "idx_candidate_certification_name",
        "candidate_certifications",
        ["certification_name_normalized"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_candidate_certification_name", table_name="candidate_certifications")
    op.drop_index("idx_candidate_education_degree", table_name="candidate_education")
    op.drop_index("idx_candidate_experience_domain", table_name="candidate_experiences")
    op.drop_index("idx_candidate_language_proficiency", table_name="candidate_languages")
    op.drop_index("idx_candidate_profile_total_experience", table_name="candidate_profiles")
    op.drop_index("idx_candidate_profile_seniority", table_name="candidate_profiles")
    op.drop_index("idx_candidate_profile_current_title", table_name="candidate_profiles")
