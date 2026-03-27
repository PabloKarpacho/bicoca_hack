from __future__ import annotations

import re
from typing import TYPE_CHECKING

from app.config.enums.normalization_class import NormalizationClass
from app.models.entity_extraction import JobSearchExtractionLLMOutput
from app.models.job_search import (
    PreparedJobLanguageRequirement,
    PreparedJobRuleFilters,
    PreparedJobSearchData,
    PreparedJobVectorQueries,
)
from app.service.normalization.primitives import (
    extract_remote_policies,
    infer_seniority,
    normalize_language_level,
    normalize_job_title,
)
from app.service.normalization.skill_utils import normalize_skill_value
from app.service.skills.hh_skill_normalizer import HHSkillNormalizerService

if TYPE_CHECKING:
    from app.service.normalization.service import EntityNormalizationService


async def normalize_job_search_requirements(
    *,
    raw_text: str,
    extracted: JobSearchExtractionLLMOutput,
    normalization_service: EntityNormalizationService | None = None,
    skill_normalizer: HHSkillNormalizerService | None = None,
) -> PreparedJobSearchData:
    profile = extracted.profile

    normalized_title = normalize_job_title(profile.title_normalized or profile.title_raw)
    if normalization_service is not None and (profile.title_normalized or profile.title_raw):
        title_result = await normalization_service.normalize(
            original_value=profile.title_normalized or profile.title_raw,
            normalization_class=NormalizationClass.PROFESSIONS,
        )
        normalized_title = title_result.normalized_value or normalized_title
    seniority_normalized = _normalize_seniority(
        profile.seniority_normalized,
        profile.title_raw,
    )
    if normalization_service is not None:
        seniority_result = await normalization_service.normalize(
            original_value=seniority_normalized or profile.seniority_normalized or profile.title_raw,
            normalization_class=NormalizationClass.SENIORITY_LEVELS,
        )
        seniority_normalized = seniority_result.normalized_value or seniority_normalized
    location_raw = _clean_text(profile.location_raw)
    location_normalized = await _normalize_location(
        location_raw,
        normalization_service=normalization_service,
    )
    remote_policies = await _normalize_remote_policies(
        profile.remote_policies,
        normalization_service=normalization_service,
    )
    employment_types = await _normalize_employment_types(
        profile.employment_types,
        normalization_service=normalization_service,
    )
    min_experience_months = _normalize_min_experience_months(
        profile.min_experience_months,
        profile.min_years_experience,
    )
    languages = await _normalize_languages(
        extracted.languages,
        normalization_service=normalization_service,
    )
    skill_lists = await _normalize_skills(
        skills=extracted.skills,
        title_normalized=normalized_title,
        title_raw=profile.title_raw,
        normalization_service=normalization_service,
        skill_normalizer=skill_normalizer,
    )
    domains = _normalize_domains(extracted.domains)
    responsibilities_summary = _clean_text(extracted.responsibilities_summary)

    rule_filters = PreparedJobRuleFilters(
        title_raw=_clean_text(profile.title_raw),
        title_normalized=normalized_title,
        seniority_normalized=seniority_normalized,
        location_raw=location_raw,
        location_normalized=location_normalized,
        remote_policies=remote_policies,
        employment_types=employment_types,
        required_languages=languages,
        required_skills=skill_lists["required_skills"],
        optional_skills=skill_lists["optional_skills"],
        domains=domains,
        min_experience_months=min_experience_months,
        education_requirements=await _normalize_education_requirements(
            extracted.education,
            normalization_service=normalization_service,
        ),
        certification_requirements=_normalize_certification_requirements(
            extracted.certifications
        ),
    )
    vector_queries = _build_vector_queries(
        raw_text=raw_text,
        rule_filters=rule_filters,
        responsibilities_summary=responsibilities_summary,
        semantic_skill_signals=skill_lists["semantic_skill_signals"],
    )
    return PreparedJobSearchData(
        rule_filters=rule_filters,
        vector_queries=vector_queries,
        extraction_confidence=extracted.extraction_confidence,
    )


def _normalize_seniority(extracted_seniority: str | None, title_raw: str | None) -> str | None:
    value = _clean_text(extracted_seniority)
    if value:
        normalized = infer_seniority(value)
        if normalized:
            return normalized
    inferred = infer_seniority(title_raw or extracted_seniority)
    return inferred


async def _normalize_languages(items, *, normalization_service: EntityNormalizationService | None) -> list[PreparedJobLanguageRequirement]:
    normalized_items: list[PreparedJobLanguageRequirement] = []
    seen: set[tuple[str, str | None, bool]] = set()
    for item in items:
        language = _clean_text(item.language_normalized or item.language_raw)
        if language is None:
            continue
        raw_proficiency = _clean_text(
            item.min_proficiency_normalized
            or item.proficiency_normalized
            or item.proficiency_raw
        )
        proficiency = normalize_language_level(raw_proficiency)
        if normalization_service is not None:
            language_result = await normalization_service.normalize(
                original_value=language,
                normalization_class=NormalizationClass.LANGUAGES,
            )
            language = language_result.normalized_value or language
        if normalization_service is not None and raw_proficiency is not None:
            proficiency_result = await normalization_service.normalize(
                original_value=raw_proficiency,
                normalization_class=NormalizationClass.PROFICIENCY_LEVELS,
            )
            proficiency = proficiency_result.normalized_value or proficiency
        key = (language, proficiency, item.required)
        if key in seen:
            continue
        seen.add(key)
        normalized_items.append(
            PreparedJobLanguageRequirement(
                language_normalized=language,
                min_proficiency_normalized=proficiency,
                is_required=item.required,
            )
        )
    return normalized_items


async def _normalize_skills(
    *,
    skills,
    title_normalized: str | None,
    title_raw: str | None,
    normalization_service: EntityNormalizationService | None,
    skill_normalizer: HHSkillNormalizerService | None,
) -> dict[str, list[str]]:
    required_skills = [
        item for item in skills if _is_required_job_skill(item.source_type)
    ]
    optional_skills = [
        item for item in skills if not _is_required_job_skill(item.source_type)
    ]
    normalized_required = await _normalize_skill_list(
        required_skills,
        normalization_service=normalization_service,
        skill_normalizer=skill_normalizer,
    )
    normalized_optional = await _normalize_skill_list(
        optional_skills,
        normalization_service=normalization_service,
        skill_normalizer=skill_normalizer,
    )
    managerial_role = _is_managerial_role(
        title_normalized=title_normalized,
        title_raw=title_raw,
    )
    filtered_required, semantic_required = _split_filter_and_semantic_skills(
        normalized_required,
        managerial_role=managerial_role,
    )
    filtered_optional, semantic_optional = _split_filter_and_semantic_skills(
        normalized_optional,
        managerial_role=managerial_role,
    )
    semantic_skill_signals = _dedupe_preserve_order(
        [*semantic_required, *semantic_optional]
    )
    required_set = set(filtered_required)
    return {
        "required_skills": filtered_required,
        "optional_skills": [item for item in filtered_optional if item not in required_set],
        "semantic_skill_signals": semantic_skill_signals,
    }


def _is_required_job_skill(source_type: str | None) -> bool:
    return source_type not in {"nice_to_have", "optional"}


def _is_managerial_role(*, title_normalized: str | None, title_raw: str | None) -> bool:
    normalized = _clean_text(title_normalized)
    raw = _clean_text(title_raw)
    if normalized in {
        "project_manager",
        "product_manager",
        "program_manager",
        "delivery_manager",
        "scrum_master",
    }:
        return True
    haystack = " ".join(part for part in [normalized, raw] if part).lower()
    return any(
        marker in haystack
        for marker in [
            "project manager",
            "product manager",
            "program manager",
            "delivery manager",
            "project coordinator",
            "scrum master",
            "delivery lead",
        ]
    )


def _split_filter_and_semantic_skills(
    values: list[str],
    *,
    managerial_role: bool,
) -> tuple[list[str], list[str]]:
    filter_skills: list[str] = []
    semantic_only_skills: list[str] = []
    for value in values:
        if managerial_role and _is_semantic_only_managerial_skill(value):
            semantic_only_skills.append(value)
            continue
        filter_skills.append(value)
    return filter_skills, semantic_only_skills


def _is_semantic_only_managerial_skill(value: str) -> bool:
    normalized = normalize_skill_value_for_matching(value)
    semantic_only_values = {
        "retrospective",
        "retrospectives",
        "sprint planning",
        "two week sprints",
        "2 week sprints",
        "scrum ceremonies",
        "weekly updates",
        "cashflow control",
        "project cashflow",
        "cashflow planning",
        "delivery reporting",
        "internal syncs",
    }
    if normalized in semantic_only_values:
        return True
    return (
        "sprint" in normalized
        and ("week" in normalized or "ceremon" in normalized or "retro" in normalized)
    )


def normalize_skill_value_for_matching(value: str | None) -> str:
    cleaned = _clean_text(value) or ""
    cleaned = cleaned.replace("-", " ").replace("/", " ").replace("_", " ")
    return re.sub(r"\s+", " ", cleaned).strip().lower()


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


async def _normalize_skill_list(
    values,
    *,
    normalization_service: EntityNormalizationService | None,
    skill_normalizer: HHSkillNormalizerService | None,
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        raw_value = value.normalized_skill or value.raw_skill
        cleaned = _clean_text(raw_value)
        if cleaned is None:
            continue
        best_value = None
        if normalization_service is not None:
            normalization_result = await normalization_service.normalize(
                original_value=cleaned,
                normalization_class=NormalizationClass.SKILLS,
            )
            best_value = normalization_result.normalized_value
        if best_value is None:
            best_value = await normalize_skill_value(
                cleaned,
                skill_normalizer=skill_normalizer,
            )
        if not best_value or best_value in seen:
            continue
        seen.add(best_value)
        normalized.append(best_value)
    return normalized


def _normalize_domains(values: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean_text(value)
        if cleaned is None:
            continue
        canonical = re.sub(r"\s+", " ", cleaned.strip().lower())
        if canonical in seen:
            continue
        seen.add(canonical)
        normalized.append(canonical)
    return normalized


def _build_vector_queries(
    *,
    raw_text: str,
    rule_filters: PreparedJobRuleFilters,
    responsibilities_summary: str | None,
    semantic_skill_signals: list[str] | None = None,
) -> PreparedJobVectorQueries:
    main_parts: list[str] = []
    if rule_filters.title_normalized:
        main_parts.append(f"Role: {rule_filters.title_normalized.replace('_', ' ')}.")
    elif rule_filters.title_raw:
        main_parts.append(f"Role: {rule_filters.title_raw}.")
    if rule_filters.seniority_normalized and rule_filters.seniority_normalized != "unknown":
        main_parts.append(f"Seniority: {rule_filters.seniority_normalized}.")
    if rule_filters.min_experience_months:
        main_parts.append(f"Minimum experience: {rule_filters.min_experience_months} months.")
    if rule_filters.required_skills:
        main_parts.append("Must-have skills: " + ", ".join(rule_filters.required_skills) + ".")
    if rule_filters.optional_skills:
        main_parts.append("Nice-to-have skills: " + ", ".join(rule_filters.optional_skills) + ".")
    if rule_filters.required_languages:
        language_fragments = []
        for item in rule_filters.required_languages:
            fragment = item.language_normalized
            if item.min_proficiency_normalized:
                fragment = f"{fragment} ({item.min_proficiency_normalized})"
            language_fragments.append(fragment)
        if language_fragments:
            main_parts.append("Languages: " + ", ".join(language_fragments) + ".")
    if rule_filters.domains:
        main_parts.append("Domains: " + ", ".join(rule_filters.domains) + ".")
    if responsibilities_summary:
        main_parts.append("Responsibilities: " + responsibilities_summary + ".")
    if not main_parts:
        main_parts.append(_clean_text(raw_text) or "")

    responsibilities_query_text = (
        f"Responsibilities focus: {responsibilities_summary}."
        if responsibilities_summary
        else None
    )
    skills_query_text = None
    skill_parts: list[str] = []
    if rule_filters.required_skills:
        skill_parts.append("Required skills: " + ", ".join(rule_filters.required_skills) + ".")
    if rule_filters.optional_skills:
        skill_parts.append("Optional skills: " + ", ".join(rule_filters.optional_skills) + ".")
    if semantic_skill_signals:
        skill_parts.append("Delivery signals: " + ", ".join(semantic_skill_signals) + ".")
    if skill_parts:
        skills_query_text = " ".join(skill_parts)

    return PreparedJobVectorQueries(
        main_query_text=" ".join(part.strip() for part in main_parts if part.strip()),
        responsibilities_query_text=responsibilities_query_text,
        skills_query_text=skills_query_text,
    )


async def _normalize_remote_policies(
    value: str | list[str] | None,
    *,
    normalization_service: EntityNormalizationService | None,
) -> list[str] | None:
    extracted = extract_remote_policies(value)
    if extracted is None:
        return None
    if normalization_service is None:
        return extracted
    normalized_values: list[str] = []
    for item in extracted:
        result = await normalization_service.normalize(
            original_value=item,
            normalization_class=NormalizationClass.REMOTE_POLICY,
        )
        value = result.normalized_value or item
        if value not in normalized_values:
            normalized_values.append(value)
    return normalized_values or None


async def _normalize_employment_types(
    value: str | list[str] | None,
    *,
    normalization_service: EntityNormalizationService | None,
) -> list[str] | None:
    raw_values = value if isinstance(value, list) else [value]
    normalized_values: list[str] = []
    seen: set[str] = set()

    for raw_value in raw_values:
        cleaned = _clean_text(raw_value)
        if cleaned is None:
            continue
        if normalization_service is None:
            from app.service.normalization.primitives import normalize_employment_type

            normalized = normalize_employment_type(cleaned)
        else:
            result = await normalization_service.normalize(
                original_value=cleaned,
                normalization_class=NormalizationClass.EMPLOYMENT_TYPE,
            )
            normalized = result.normalized_value
        if normalized and normalized not in seen:
            seen.add(normalized)
            normalized_values.append(normalized)
    return normalized_values or None


async def _normalize_location(
    value: str | None,
    *,
    normalization_service: EntityNormalizationService | None,
) -> str | None:
    cleaned = _clean_text(value)
    if cleaned is None:
        return None
    if normalization_service is None:
        return re.sub(r"\s+", " ", cleaned.strip().lower())
    parts = [part.strip() for part in cleaned.split(",") if part.strip()]
    if not parts:
        return None
    if len(parts) == 1:
        city_result = await normalization_service.normalize(
            original_value=parts[0],
            normalization_class=NormalizationClass.CITIES,
        )
        country_result = await normalization_service.normalize(
            original_value=parts[0],
            normalization_class=NormalizationClass.COUNTRIES,
        )
        resolved = (
            city_result.normalized_value
            or country_result.normalized_value
            or re.sub(r"\s+", " ", cleaned.strip().lower())
        )
        return re.sub(r"\s+", " ", resolved.strip().lower())
    city_result = await normalization_service.normalize(
        original_value=parts[0],
        normalization_class=NormalizationClass.CITIES,
    )
    country_result = await normalization_service.normalize(
        original_value=parts[-1],
        normalization_class=NormalizationClass.COUNTRIES,
    )
    values = [value for value in [city_result.normalized_value, country_result.normalized_value] if value]
    resolved = ", ".join(values) if values else re.sub(r"\s+", " ", cleaned.strip().lower())
    return re.sub(r"\s+", " ", resolved.strip().lower())


def _normalize_min_experience_months(months: int | None, years: int | None) -> int | None:
    if months is not None and months >= 0:
        return months
    if years is not None and years >= 0:
        return years * 12
    return None


async def _normalize_education_requirements(
    values,
    *,
    normalization_service: EntityNormalizationService | None,
) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean_text(
            value.degree_normalized or value.degree_raw or value.field_of_study
        )
        if cleaned is None:
            continue
        best_value = cleaned
        if normalization_service is not None:
            result = await normalization_service.normalize(
                original_value=cleaned,
                normalization_class=NormalizationClass.EDUCATION,
            )
            best_value = result.normalized_value or best_value
        if best_value in seen:
            continue
        seen.add(best_value)
        normalized.append(best_value)
    return normalized


def _normalize_certification_requirements(values) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = _clean_text(
            value.certification_name_normalized or value.certification_name_raw
        )
        if cleaned is None or cleaned in seen:
            continue
        seen.add(cleaned)
        normalized.append(cleaned)
    return normalized


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    return cleaned or None
