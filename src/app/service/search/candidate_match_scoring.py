from __future__ import annotations

from typing import Iterable

from app.models.candidate_search import (
    CandidateSearchFilters,
    CandidateSearchMatchMetadata,
    CandidateSearchScoreBreakdown,
)
from app.service.normalization.primitives import (
    normalize_job_title,
    normalize_skill_name,
)

COMPONENT_WEIGHTS = {
    "vector_semantic_score": 0.55,
    "role_match_score": 0.15,
    "skills_match_score": 0.15,
    "experience_match_score": 0.10,
    "language_match_score": 0.05,
}


def calculate_candidate_match_score(
    *,
    filters: CandidateSearchFilters,
    current_title_normalized: str | None,
    total_experience_months: int | None,
    match_metadata: CandidateSearchMatchMetadata | None,
    vector_semantic_score: float | None = None,
) -> tuple[int | None, CandidateSearchScoreBreakdown | None]:
    """Calculate a user-facing candidate match score as an explainable 0..100 percentage.

    This function intentionally does *not* expose raw vector similarity as "percentage match".
    Raw Qdrant/OpenAI similarity scores are useful for ranking, but they are not directly
    interpretable as a recruiter-facing measure of fit. Instead, we build a calibrated
    match score from several explainable signals and then convert the weighted result into
    an integer percent.

    The score is composed from up to five components:
    - vector semantic score: semantic proximity of the candidate chunks to the vacancy query
    - role match score: overlap between requested role and the candidate's current role
    - skills match score: overlap between requested skills and explicitly matched skills
    - experience match score: how well total experience satisfies the requested threshold
    - language match score: coverage of requested languages already satisfied by the candidate

    The weighted average is normalized across *active* components only. This avoids
    penalizing candidates when the user simply did not specify a certain type of signal.

    Returns:
        tuple[int | None, CandidateSearchScoreBreakdown | None]:
            - integer 0..100 percent intended for UI display
            - structured breakdown with per-component scores in the 0..1 range
    """

    breakdown = CandidateSearchScoreBreakdown(
        vector_semantic_score=_clamp_01(vector_semantic_score),
        role_match_score=_calculate_role_match_score(
            filters=filters,
            current_title_normalized=current_title_normalized,
        ),
        skills_match_score=_calculate_skills_match_score(
            filters=filters,
            match_metadata=match_metadata,
        ),
        experience_match_score=_calculate_experience_match_score(
            filters=filters,
            total_experience_months=total_experience_months,
        ),
        language_match_score=_calculate_language_match_score(
            filters=filters,
            match_metadata=match_metadata,
        ),
    )
    overall_score = _combine_score_components(breakdown)
    if overall_score is None:
        return None, None
    breakdown.overall_score = overall_score
    return round(overall_score * 100), breakdown


def _calculate_role_match_score(
    *,
    filters: CandidateSearchFilters,
    current_title_normalized: str | None,
) -> float | None:
    """Estimate role fit from normalized titles.

    Design intent:
    - exact normalized title match should be a strong positive signal
    - the score should still work when the vacancy comes through `title_raw`
      instead of `current_title_normalized`
    - if the user did not supply any role signal, return `None` so the role
      component is excluded from the weighted average

    Current heuristic:
    - 1.0 for exact normalized match
    - 0.85 for token-level containment (for example "project manager" vs
      "senior project manager")
    - 0.0 when role evidence exists but the candidate title does not match
    """

    candidate_title = _normalize_title_token(current_title_normalized)
    requested_titles = [
        title
        for title in (
            *(_normalize_title_tokens(filters.current_title_normalized)),
            *(_normalize_title_tokens(filters.current_or_past_titles)),
        )
        if title
    ]
    if filters.title_raw:
        normalized_title = _normalize_title_token(
            normalize_job_title(filters.title_raw)
        )
        if normalized_title:
            requested_titles.append(normalized_title)

    requested_titles = _dedupe_strings(requested_titles)
    if not requested_titles:
        return None
    if candidate_title is None:
        return 0.0
    if candidate_title in requested_titles:
        return 1.0

    candidate_tokens = set(candidate_title.split())
    for title in requested_titles:
        requested_tokens = set(title.split())
        if not requested_tokens:
            continue
        if candidate_tokens.issuperset(requested_tokens) or requested_tokens.issuperset(
            candidate_tokens
        ):
            return 0.85
    return 0.0


def _calculate_skills_match_score(
    *,
    filters: CandidateSearchFilters,
    match_metadata: CandidateSearchMatchMetadata | None,
) -> float | None:
    """Calculate skill fit from overlap between requested and matched skills.

    Skills are intentionally treated as a *supportive* matching signal in the current
    product. They are no longer hard filters, so this function measures coverage rather
    than strict acceptance/rejection.

    Weighting policy:
    - required skills count with weight 1.0
    - optional skills count with weight 0.5
    - final score = matched weighted total / requested weighted total

    Returning `None` means the user did not request any skills, so the final weighted
    score should not be penalized for an absent skills dimension.
    """

    required_skills = _normalize_skill_tokens(filters.include_skills)
    optional_skills = _normalize_skill_tokens(filters.optional_skills)
    if not required_skills and not optional_skills:
        return None

    matched_skills = set(
        _normalize_skill_tokens(match_metadata.matched_skills if match_metadata else [])
    )
    required_weight = float(len(required_skills))
    optional_weight = float(len(optional_skills)) * 0.5
    denominator = required_weight + optional_weight
    if denominator <= 0:
        return None

    matched_required = sum(1.0 for skill in required_skills if skill in matched_skills)
    matched_optional = sum(0.5 for skill in optional_skills if skill in matched_skills)
    return _clamp_01((matched_required + matched_optional) / denominator)


def _calculate_experience_match_score(
    *,
    filters: CandidateSearchFilters,
    total_experience_months: int | None,
) -> float | None:
    """Score how well the candidate satisfies requested total experience.

    We treat experience as a saturating requirement:
    - if no minimum is requested, the component is not active
    - if the candidate meets or exceeds the minimum, score = 1.0
    - otherwise score grows proportionally to requested coverage

    This keeps the function easy to reason about and makes the resulting percentage
    intuitive for recruiters: someone with half the requested experience gets roughly
    half of the experience component.
    """

    if filters.min_total_experience_months is None:
        return None
    required = max(filters.min_total_experience_months, 1)
    candidate = max(total_experience_months or 0, 0)
    return _clamp_01(candidate / required)


def _calculate_language_match_score(
    *,
    filters: CandidateSearchFilters,
    match_metadata: CandidateSearchMatchMetadata | None,
) -> float | None:
    """Measure language coverage from already matched language entities.

    The rule-search layer already resolves language proficiency constraints. We reuse
    that evidence here instead of trying to infer a second language score from raw
    strings. The resulting value is simply:

        matched requested languages / total requested languages

    Returning `None` again means the user did not request any language constraints.
    """

    if not filters.languages:
        return None
    requested_languages = {
        language_filter.language_normalized.strip().lower()
        for language_filter in filters.languages
        if language_filter.language_normalized.strip()
    }
    if not requested_languages:
        return None
    matched_languages = {
        language.strip().lower()
        for language in (match_metadata.matched_languages if match_metadata else [])
        if language.strip()
    }
    return _clamp_01(
        len(requested_languages & matched_languages) / len(requested_languages)
    )


def _combine_score_components(
    breakdown: CandidateSearchScoreBreakdown,
) -> float | None:
    """Combine active score components into one calibrated 0..1 overall score.

    Important detail:
    The function normalizes by the sum of weights of *active* components only.
    This makes the score stable across different search modes:
    - pure rule-based searches usually do not have `vector_semantic_score`
    - vector-only searches may not have explicit skills/languages metadata
    - hybrid searches can activate nearly all components

    This behavior is preferable to hardcoding a denominator of 1.0, because a candidate
    should not lose points simply because the user did not provide skills or language
    constraints for that particular search.
    """

    weighted_total = 0.0
    active_weight = 0.0
    for field_name, weight in COMPONENT_WEIGHTS.items():
        value = getattr(breakdown, field_name)
        if value is None:
            continue
        weighted_total += _clamp_01(value) * weight
        active_weight += weight
    if active_weight <= 0:
        return None
    return _clamp_01(weighted_total / active_weight)


def _normalize_title_tokens(values: Iterable[str] | None) -> list[str]:
    if not values:
        return []
    return [
        normalized
        for normalized in (_normalize_title_token(value) for value in values)
        if normalized
    ]


def _normalize_title_token(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.replace("_", " ").strip().lower()
    normalized = " ".join(normalized.split())
    return normalized or None


def _normalize_skill_tokens(values: Iterable[str] | None) -> list[str]:
    if not values:
        return []
    normalized_values = []
    for value in values:
        normalized = normalize_skill_name(value)
        if normalized:
            normalized_values.append(normalized)
    return _dedupe_strings(normalized_values)


def _dedupe_strings(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        key = value.strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(key)
    return deduped


def _clamp_01(value: float | None) -> float | None:
    if value is None:
        return None
    return max(0.0, min(1.0, float(value)))
