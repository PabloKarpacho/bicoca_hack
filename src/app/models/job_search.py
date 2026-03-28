from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.common_types import (
    EducationLiteral,
    ExtractedSkillSourceLiteral,
    EmploymentTypeLiteral,
    ProficiencyLiteral,
    RemotePolicyLiteral,
    SeniorityLiteral,
)
from app.models.entity_extraction import JobSearchExtractionLLMOutput
from app.service.normalization.primitives import normalize_language_level


class JobSearchPreparationRequest(BaseModel):
    job_id: str | None = Field(
        default=None,
        description="Job identifier when the request is tied to a stored job record.",
    )
    source_document_id: str | None = Field(
        default=None,
        description="Source document identifier that contains the vacancy text, if any.",
    )
    raw_text: str = Field(
        description="Raw vacancy text that should be parsed into structured job search requirements."
    )


class PreparedJobLanguageRequirement(BaseModel):
    language_normalized: str = Field(
        description="Canonical language name required by the vacancy."
    )
    min_proficiency_normalized: ProficiencyLiteral | None = Field(
        default=None,
        description="Minimum acceptable proficiency level for the language requirement.",
    )
    is_required: bool = Field(
        default=True,
        description="Whether this language is mandatory for the role.",
    )

    @model_validator(mode="before")
    @classmethod
    def normalize_proficiency_literal(cls, data):
        """Coerce free-form proficiency values into the canonical literal set.

        Job preparation may still encounter raw phrases such as "Advanced" or noisy
        labels like "A plus". We normalize known variants to canonical values and
        gracefully demote unknown ones to `None` so that one bad language label does
        not fail the whole vacancy preparation pipeline.
        """
        if not isinstance(data, dict):
            return data
        proficiency = data.get("min_proficiency_normalized")
        if proficiency is not None:
            data["min_proficiency_normalized"] = normalize_language_level(proficiency)
        return data


class PreparedJobRuleFilters(BaseModel):
    title_raw: str | None = Field(
        default=None, description="Original vacancy title text."
    )
    title_normalized: str | None = Field(
        default=None, description="Normalized canonical vacancy title."
    )
    seniority_normalized: SeniorityLiteral | None = Field(
        default=None,
        description="Normalized seniority required by the vacancy.",
    )
    location_raw: str | None = Field(
        default=None, description="Original location text from the vacancy."
    )
    location_normalized: str | None = Field(
        default=None, description="Normalized vacancy location label."
    )
    remote_policies: list[RemotePolicyLiteral] | None = Field(
        default=None,
        description="Remote or onsite work arrangements extracted from the vacancy.",
    )
    employment_types: list[EmploymentTypeLiteral] | None = Field(
        default=None,
        description="Employment types extracted from the vacancy.",
    )
    required_languages: list[PreparedJobLanguageRequirement] = Field(
        default_factory=list,
        description="Structured language requirements for rule-based matching.",
    )
    required_skills: list[str] = Field(
        default_factory=list,
        description="Required normalized skills for rule-based matching.",
    )
    optional_skills: list[str] = Field(
        default_factory=list,
        description="Optional normalized skills for supportive matching.",
    )
    domains: list[str] = Field(
        default_factory=list,
        description="Business or industry domains extracted from the vacancy.",
    )
    min_experience_months: int | None = Field(
        default=None,
        description="Minimum professional experience requirement converted to months.",
    )
    education_requirements: list[EducationLiteral] = Field(
        default_factory=list,
        description="Normalized education levels requested by the vacancy.",
    )
    certification_requirements: list[str] = Field(
        default_factory=list,
        description="Certification requirements extracted from the vacancy.",
    )

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_remote_policy(cls, data):
        if not isinstance(data, dict):
            return data
        if data.get("remote_policies") in (None, []):
            remote_policy = data.get("remote_policy")
            if isinstance(remote_policy, list):
                data["remote_policies"] = remote_policy
            elif isinstance(remote_policy, str) and remote_policy.strip():
                data["remote_policies"] = [remote_policy]
        if data.get("employment_types") in (None, []):
            employment_type = data.get("employment_type")
            if isinstance(employment_type, list):
                data["employment_types"] = employment_type
            elif isinstance(employment_type, str) and employment_type.strip():
                data["employment_types"] = [employment_type]
        return data


class PreparedJobVectorQueries(BaseModel):
    main_query_text: str = Field(
        description="Main semantic query text used for candidate vector search."
    )
    responsibilities_query_text: str | None = Field(
        default=None,
        description="Optional responsibility-focused semantic query text.",
    )
    skills_query_text: str | None = Field(
        default=None,
        description="Optional skill-focused semantic query text.",
    )


class PreparedJobSearchData(BaseModel):
    rule_filters: PreparedJobRuleFilters = Field(
        description="Structured rule-based filters derived from the vacancy."
    )
    vector_queries: PreparedJobVectorQueries = Field(
        description="Semantic vector queries derived from the vacancy."
    )
    extraction_confidence: float | None = Field(
        default=None,
        description="Overall extraction confidence for the prepared vacancy search payload.",
    )


class JobSearchProcessingMetadata(BaseModel):
    status: str = Field(
        description="Processing status for the job preparation pipeline."
    )
    pipeline_version: str = Field(
        description="Pipeline version used for job preparation."
    )
    model_version: str | None = Field(
        default=None, description="Model version used for preparation, when available."
    )
    extraction_confidence: float | None = Field(
        default=None,
        description="Overall extraction confidence for the preparation run.",
    )
    error_message: str | None = Field(
        default=None, description="Error message if preparation failed."
    )
    started_at: datetime | None = Field(
        default=None, description="Timestamp when preparation started."
    )
    finished_at: datetime | None = Field(
        default=None, description="Timestamp when preparation finished."
    )
