from __future__ import annotations

from typing import Any
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ExtractedCandidateProfile(BaseModel):
    full_name: str | None = None
    email: str | None = Field(
        default=None,
        description="Candidate email address exactly as stated in the CV.",
    )
    phone: str | None = Field(
        default=None,
        description=(
            "Real phone number only. Do not use years, date ranges, IDs, or arbitrary "
            "digit sequences. If no clear phone number is present, use null."
        ),
    )
    location_raw: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    headline: str | None = None
    summary: str | None = None
    current_title_raw: str | None = None
    current_title_normalized: str | None = None
    seniority_normalized: str | None = None
    remote_policies: list[str] = Field(default_factory=list)
    employment_types: list[str] = Field(default_factory=list)
    total_experience_months: int | None = None
    confidence: float | None = None


class ExtractedLanguage(BaseModel):
    language_raw: str | None = None
    language_normalized: str | None = None
    proficiency_raw: str | None = None
    proficiency_normalized: str | None = None
    confidence: float | None = None


class ExtractedExperience(BaseModel):
    company_name_raw: str | None = None
    job_title_raw: str | None = None
    job_title_normalized: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    is_current: bool | None = None
    duration_months: int | None = None
    location_raw: str | None = None
    responsibilities_text: str | None = None
    technologies_text: str | None = None
    domain_hint: str | None = None
    confidence: float | None = None


class ExtractedSkill(BaseModel):
    raw_skill: str | None = None
    normalized_skill: str | None = None
    skill_category: str | None = None
    source_type: str | None = None
    confidence: float | None = None


class ExtractedEducation(BaseModel):
    institution_raw: str | None = None
    degree_raw: str | None = None
    degree_normalized: str | None = Field(
        default=None,
        description=(
            "Canonical degree level only. Use one of: secondary, associate, "
            "bachelor, master, phd. Use null if unclear."
        ),
    )
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    confidence: float | None = None


class ExtractedCertification(BaseModel):
    certification_name_raw: str | None = None
    certification_name_normalized: str | None = None
    issuer: str | None = None
    issue_date: str | None = None
    expiry_date: str | None = None
    confidence: float | None = None


class ExtractedJobLanguageRequirement(ExtractedLanguage):
    min_proficiency_normalized: str | None = None
    required: bool = True


class ExtractedJobSearchProfile(BaseModel):
    title_raw: str | None = None
    title_normalized: str | None = None
    seniority_normalized: str | None = None
    location_raw: str | None = None
    remote_policies: list[str] = Field(default_factory=list)
    employment_type: str | None = None
    min_years_experience: int | None = None
    min_experience_months: int | None = None
    confidence: float | None = None


class CVEntityExtractionLLMOutput(BaseModel):
    profile: ExtractedCandidateProfile = Field(
        default_factory=ExtractedCandidateProfile,
        description="Top-level candidate profile information extracted from the CV.",
    )
    languages: list[ExtractedLanguage] = Field(default_factory=list)
    experiences: list[ExtractedExperience] = Field(default_factory=list)
    skills: list[ExtractedSkill] = Field(default_factory=list)
    education: list[ExtractedEducation] = Field(
        default_factory=list,
        description=(
            "All education stages from the CV. Keep sequential degrees as separate "
            "entries, even if they belong to the same university and field of study."
        ),
    )
    certifications: list[ExtractedCertification] = Field(default_factory=list)


class JobSearchExtractionLLMOutput(BaseModel):
    profile: ExtractedJobSearchProfile = Field(default_factory=ExtractedJobSearchProfile)
    languages: list[ExtractedJobLanguageRequirement] = Field(default_factory=list)
    skills: list[ExtractedSkill] = Field(default_factory=list)
    education: list[ExtractedEducation] = Field(default_factory=list)
    certifications: list[ExtractedCertification] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    responsibilities_summary: str | None = None
    extraction_confidence: float | None = None

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_shape(cls, data):
        if not isinstance(data, dict):
            return data

        profile = dict(data.get("profile") or {})
        for field_name in (
            "title_raw",
            "title_normalized",
            "seniority_normalized",
            "location_raw",
            "employment_type",
            "min_years_experience",
            "min_experience_months",
        ):
            if profile.get(field_name) is None and data.get(field_name) is not None:
                profile[field_name] = data.get(field_name)

        if profile.get("remote_policies") in (None, []):
            remote_policy = data.get("remote_policy")
            remote_policies = data.get("remote_policies")
            if isinstance(remote_policies, list):
                profile["remote_policies"] = remote_policies
            elif isinstance(remote_policy, list):
                profile["remote_policies"] = remote_policy
            elif isinstance(remote_policy, str) and remote_policy.strip():
                profile["remote_policies"] = [remote_policy]

        if "languages" not in data and data.get("required_languages") is not None:
            data["languages"] = data.get("required_languages")

        if "skills" not in data:
            skills: list[dict[str, Any]] = []
            for item in data.get("required_skills") or []:
                if isinstance(item, dict):
                    skill_item = dict(item)
                    skill_item["source_type"] = "must_have"
                    skills.append(skill_item)
            for item in data.get("optional_skills") or []:
                if isinstance(item, dict):
                    skill_item = dict(item)
                    skill_item["source_type"] = "nice_to_have"
                    skills.append(skill_item)
            data["skills"] = skills

        if "education" not in data and data.get("education_requirements") is not None:
            data["education"] = [
                {"degree_raw": item}
                for item in data.get("education_requirements") or []
                if isinstance(item, str)
            ]

        if "certifications" not in data and data.get("certification_requirements") is not None:
            data["certifications"] = [
                {"certification_name_raw": item}
                for item in data.get("certification_requirements") or []
                if isinstance(item, str)
            ]

        data["profile"] = profile
        return data


class CandidateProfileData(BaseModel):
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location_raw: str | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    headline: str | None = None
    summary: str | None = None
    current_title_raw: str | None = None
    current_title_normalized: str | None = None
    seniority_normalized: str | None = None
    remote_policies: list[str] | None = None
    employment_types: list[str] | None = None
    total_experience_months: int | None = None
    extraction_confidence: float | None = None


class CandidateLanguageData(BaseModel):
    language_raw: str | None = None
    language_normalized: str | None = None
    proficiency_raw: str | None = None
    proficiency_normalized: str | None = None
    confidence: float | None = None


class CandidateExperienceData(BaseModel):
    position_order: int
    company_name_raw: str | None = None
    job_title_raw: str | None = None
    job_title_normalized: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    is_current: bool = False
    duration_months: int | None = None
    location_raw: str | None = None
    responsibilities_text: str | None = None
    technologies_text: str | None = None
    domain_hint: str | None = None
    confidence: float | None = None


class CandidateSkillData(BaseModel):
    raw_skill: str | None = None
    normalized_skill: str | None = None
    skill_category: str | None = None
    source_type: str | None = None
    confidence: float | None = None
    normalization_source: str | None = None
    normalization_external_id: int | None = None
    normalization_status: str | None = None
    normalization_confidence: float | None = None
    normalization_metadata: dict[str, Any] | None = None


class CandidateEducationData(BaseModel):
    position_order: int
    institution_raw: str | None = None
    degree_raw: str | None = None
    degree_normalized: str | None = None
    field_of_study: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    confidence: float | None = None


class CandidateCertificationData(BaseModel):
    certification_name_raw: str | None = None
    certification_name_normalized: str | None = None
    issuer: str | None = None
    issue_date: date | None = None
    expiry_date: date | None = None
    confidence: float | None = None


class CandidateEntitiesData(BaseModel):
    profile: CandidateProfileData
    languages: list[CandidateLanguageData]
    experiences: list[CandidateExperienceData]
    skills: list[CandidateSkillData]
    education: list[CandidateEducationData]
    certifications: list[CandidateCertificationData]


class ProcessingRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    processing_run_id: str
    document_id: str
    candidate_id: str | None = None
    processing_stage: str
    status: str
    pipeline_version: str
    model_version: str | None = None
    extraction_confidence: float | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class EntityExtractionRunResponse(BaseModel):
    document_id: str
    candidate_id: str | None = None
    status: str
    pipeline_version: str
    model_version: str | None = None
    extraction_confidence: float | None = None


class CandidateEntitiesResponse(BaseModel):
    document_id: str
    candidate_id: str | None = None
    processing_run: ProcessingRunResponse | None = None
    profile: CandidateProfileData | None = None
    languages: list[CandidateLanguageData]
    experiences: list[CandidateExperienceData]
    skills: list[CandidateSkillData]
    education: list[CandidateEducationData]
    certifications: list[CandidateCertificationData]
