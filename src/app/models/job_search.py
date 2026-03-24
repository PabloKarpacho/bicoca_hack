from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.entity_extraction import JobSearchExtractionLLMOutput


class JobSearchPreparationRequest(BaseModel):
    job_id: str | None = None
    source_document_id: str | None = None
    raw_text: str

class PreparedJobLanguageRequirement(BaseModel):
    language_normalized: str
    min_proficiency_normalized: str | None = None
    is_required: bool = True


class PreparedJobSkillRequirement(BaseModel):
    normalized_skill: str
    is_required: bool
    source_type: str | None = None


class PreparedJobRuleFilters(BaseModel):
    title_raw: str | None = None
    title_normalized: str | None = None
    seniority_normalized: str | None = None
    location_raw: str | None = None
    location_normalized: str | None = None
    remote_policies: list[str] | None = None
    employment_types: list[str] | None = None
    required_languages: list[PreparedJobLanguageRequirement] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    optional_skills: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    min_experience_months: int | None = None
    education_requirements: list[str] = Field(default_factory=list)
    certification_requirements: list[str] = Field(default_factory=list)

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
    main_query_text: str
    responsibilities_query_text: str | None = None
    skills_query_text: str | None = None


class PreparedJobSearchData(BaseModel):
    rule_filters: PreparedJobRuleFilters
    vector_queries: PreparedJobVectorQueries
    extraction_confidence: float | None = None


class JobSearchProcessingMetadata(BaseModel):
    status: str
    pipeline_version: str
    model_version: str | None = None
    extraction_confidence: float | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class JobSearchPreparedQuery(BaseModel):
    job_id: str
    source_document_id: str | None = None
    rule_filters: PreparedJobRuleFilters
    vector_queries: PreparedJobVectorQueries
    processing_metadata: JobSearchProcessingMetadata | None = None


class JobSearchPreparationRunResponse(BaseModel):
    job_id: str
    source_document_id: str | None = None
    status: str
    pipeline_version: str
    model_version: str | None = None
    extraction_confidence: float | None = None


class JobSearchProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    job_search_profile_id: str
    job_id: str
    source_document_id: str | None = None
    raw_title: str | None = None
    normalized_title: str | None = None
    seniority_normalized: str | None = None
    location_raw: str | None = None
    location_normalized: str | None = None
    remote_policies_json: str | None = None
    employment_type: str | None = None
    min_experience_months: int | None = None
    education_requirements: str | None = None
    certification_requirements: str | None = None
    semantic_query_text_main: str
    semantic_query_text_responsibilities: str | None = None
    semantic_query_text_skills: str | None = None
    extraction_confidence: float | None = None
    pipeline_version: str
    model_version: str | None = None
    created_at: datetime
    updated_at: datetime
