from __future__ import annotations

from app.models.skill_normalization import HHSkillNormalizationResult
from app.service.normalization.primitives import normalize_skill_name
from app.service.skills.hh_skill_normalizer import HHSkillNormalizerService


async def normalize_skill_with_hh(
    raw_skill: str | None,
    *,
    skill_normalizer: HHSkillNormalizerService | None,
) -> HHSkillNormalizationResult | None:
    if skill_normalizer is None:
        return None
    return await skill_normalizer.normalize_skill(raw_skill)


def resolve_normalized_skill(
    *,
    fallback_value: str | None,
    normalization_result: HHSkillNormalizationResult | None,
) -> str | None:
    if normalization_result and normalization_result.normalized_skill_text:
        return normalize_skill_name(normalization_result.normalized_skill_text)
    return normalize_skill_name(fallback_value)


async def normalize_skill_value(
    value: str | None,
    *,
    skill_normalizer: HHSkillNormalizerService | None,
) -> str | None:
    normalization_result = await normalize_skill_with_hh(
        value,
        skill_normalizer=skill_normalizer,
    )
    return resolve_normalized_skill(
        fallback_value=value,
        normalization_result=normalization_result,
    )


def skill_normalization_source(
    *,
    normalization_result: HHSkillNormalizationResult | None,
) -> str | None:
    if normalization_result is None:
        return "local"
    if normalization_result.match_type in {"exact", "prefix", "top_result"}:
        return normalization_result.provider
    return "local"


def skill_normalization_status(
    *,
    normalization_result: HHSkillNormalizationResult | None,
) -> str | None:
    if normalization_result is None:
        return "local_only"
    if normalization_result.match_type == "error":
        return "error"
    if normalization_result.match_type == "disabled":
        return "skipped"
    if normalization_result.match_type == "no_match":
        return "no_match"
    return "matched"


def skill_normalization_metadata(
    *,
    normalization_result: HHSkillNormalizationResult | None,
) -> dict | None:
    if normalization_result is None:
        return None
    return {
        "provider": normalization_result.provider,
        "provider_skill_text": normalization_result.normalized_skill_text,
        "provider_skill_external_id": normalization_result.normalized_skill_external_id,
        "match_type": normalization_result.match_type,
        "alternatives": [
            {"id": item.id, "text": item.text}
            for item in normalization_result.alternatives
        ],
        "error": normalization_result.error,
    }


def registry_skill_normalization_source(registry_result) -> str | None:
    if registry_result is None:
        return None
    metadata = registry_result.metadata or {}
    if registry_result.provider == "hh":
        return "hh"
    if metadata.get("hh_match_type") == "error" or metadata.get("hh_error"):
        return "local"
    return "local"


def registry_skill_normalization_status(registry_result) -> str | None:
    if registry_result is None:
        return None
    metadata = registry_result.metadata or {}
    if registry_result.provider == "hh":
        return "matched"
    hh_match_type = metadata.get("hh_match_type")
    if hh_match_type == "error" or metadata.get("hh_error"):
        return "error"
    if hh_match_type == "disabled":
        return "skipped"
    if hh_match_type == "no_match":
        return "no_match"
    return "local_only"


def registry_skill_normalization_metadata(registry_result) -> dict | None:
    if registry_result is None:
        return None
    metadata = dict(registry_result.metadata or {})
    if registry_result.provider == "hh":
        metadata.setdefault("provider", "hh")
        metadata.setdefault("provider_skill_external_id", metadata.get("external_id"))
        metadata.setdefault("match_type", metadata.get("match_type"))
    return metadata or None
