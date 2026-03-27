from __future__ import annotations

import json
from dataclasses import dataclass

from loguru import logger
from sqlalchemy import case, exists, func, literal, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate_search import (
    CandidateLanguageFilter,
    CandidateSearchFilters,
    CandidateSearchMatchMetadata,
    CandidateSearchResult,
    CandidateSearchResultItem,
)
from app.service.search.candidate_match_scoring import calculate_candidate_match_score
from app.service.normalization.primitives import (
    education_level_rank,
    extract_employment_types,
    extract_remote_policies,
    normalize_degree,
    normalize_job_title,
    normalize_language_level,
    normalize_skill_name,
)
from database.postgres.schema import (
    CandidateCertification,
    CandidateEducation,
    CandidateExperience,
    CandidateLanguage,
    CandidateProfile,
    CandidateSkill,
)

LANGUAGE_PROFICIENCY_ORDER = {
    "basic": 1,
    "intermediate": 2,
    "professional": 3,
    "fluent": 4,
    "native": 5,
}


@dataclass(slots=True)
class CandidateRuleSearchService:
    session: AsyncSession

    async def search(self, filters: CandidateSearchFilters) -> CandidateSearchResult:
        """Run recall-first structured search and rank by soft evidence.

        This search mode intentionally avoids hard-filtering away candidates for most
        recruiter inputs. Instead of treating titles, languages, experience, or
        certifications as strict SQL gates, we load the available candidate set,
        compute structured overlap metadata, and sort by the explainable match score.

        The only scope-narrowing filter we keep at the SQL level is an explicit
        shortlist via `candidate_ids`.
        """
        applied_filters = self._normalize_filters(filters)
        logger.info(
            "Candidate rule search: start candidate_ids={candidate_ids}, requested_skills={requested_skills}, languages={languages}, domains={domains}, sort_by={sort_by}, sort_order={sort_order}, limit={limit}, offset={offset}",
            candidate_ids=len(applied_filters.candidate_ids or []),
            requested_skills=len(self._requested_skills(applied_filters)),
            languages=len(applied_filters.languages or []),
            domains=len(applied_filters.domains or []),
            sort_by=applied_filters.sort_by,
            sort_order=applied_filters.sort_order,
            limit=applied_filters.limit,
            offset=applied_filters.offset,
        )

        conditions = self._build_conditions(applied_filters)
        logger.debug("Candidate rule search: built conditions: {conditions}", conditions=conditions)
        sort_column = self._sort_column(applied_filters.sort_by)
        order_clause = (
            sort_column.asc() if applied_filters.sort_order == "asc" else sort_column.desc()
        )
        stmt = select(CandidateProfile).where(*conditions).order_by(
            order_clause,
            CandidateProfile.candidate_id.asc(),
            CandidateProfile.document_id.asc(),
        )
        result = await self.session.execute(stmt)
        profiles = list(result.scalars().all())

        metadata_by_document = await self._load_match_metadata(profiles, applied_filters)
        items = [
            self._build_result_item(
                profile=profile,
                filters=applied_filters,
                match_metadata=metadata_by_document.get(profile.document_id),
            )
            for profile in profiles
        ]
        items = self._rank_result_items(items)
        total = len(items)
        items = items[applied_filters.offset : applied_filters.offset + applied_filters.limit]

        logger.info(
            "Candidate rule search: completed total={total}, returned_items={returned_items}",
            total=total,
            returned_items=len(items),
        )
        return CandidateSearchResult(
            total=total,
            items=items,
            applied_filters=applied_filters,
        )

    def _build_result_item(
        self,
        *,
        profile: CandidateProfile,
        filters: CandidateSearchFilters,
        match_metadata: CandidateSearchMatchMetadata | None,
    ) -> CandidateSearchResultItem:
        """Build one rule-search result item and attach a user-facing match percentage.

        The returned `score` field remains unused for pure rule-based search so that
        existing API semantics do not change unexpectedly. Instead, we compute a separate
        `match_score_percent` that the UI can safely present as recruiter-facing fit.
        """

        match_score_percent, match_score_breakdown = calculate_candidate_match_score(
            filters=filters,
            current_title_normalized=profile.current_title_normalized,
            total_experience_months=profile.total_experience_months,
            match_metadata=match_metadata,
            vector_semantic_score=None,
        )
        return CandidateSearchResultItem(
            candidate_id=profile.candidate_id,
            document_id=profile.document_id,
            full_name=profile.full_name,
            current_title_normalized=profile.current_title_normalized,
            seniority_normalized=profile.seniority_normalized,
            total_experience_months=profile.total_experience_months,
            location_normalized=self._normalize_location(profile.location_raw),
            remote_policies=_parse_json_array(profile.remote_policies_json),
            match_metadata=match_metadata,
            match_score_percent=match_score_percent,
            match_score_breakdown=match_score_breakdown,
        )

    def _build_conditions(self, filters: CandidateSearchFilters) -> list:
        """Build only scope-narrowing SQL conditions.

        Most structured filters are intentionally *not* turned into hard SQL
        predicates. They are consumed later as evidence for ranking and metadata so
        that the search can still surface candidates even when exact overlap is weak.
        """
        conditions = [literal(True)]

        if filters.candidate_ids:
            conditions.append(CandidateProfile.candidate_id.in_(filters.candidate_ids))
        return conditions

    def _build_skill_conditions(self, filters: CandidateSearchFilters) -> list:
        return []

    def _build_language_conditions(self, filters: CandidateSearchFilters) -> list:
        if not filters.languages:
            return []

        conditions = []
        per_language_exists = [
            exists(
                select(1).where(
                    CandidateLanguage.document_id == CandidateProfile.document_id,
                    func.lower(CandidateLanguage.language_normalized)
                    == language_filter.language_normalized.lower(),
                    self._language_proficiency_condition(language_filter),
                )
            )
            for language_filter in filters.languages
        ]
        if filters.require_all_languages:
            conditions.extend(per_language_exists)
        else:
            conditions.append(or_(*per_language_exists))
        return conditions

    def _build_experience_conditions(self, filters: CandidateSearchFilters) -> list:
        title_values = filters.current_or_past_titles or []
        company_values = filters.companies or []

        row_conditions = [
            CandidateExperience.document_id == CandidateProfile.document_id,
        ]
        if title_values:
            row_conditions.append(
                func.lower(CandidateExperience.job_title_normalized).in_(title_values)
            )
        if company_values:
            row_conditions.append(
                func.lower(CandidateExperience.company_name_raw).in_(company_values)
            )
        if filters.is_currently_employed_in_title is True:
            row_conditions.append(CandidateExperience.is_current.is_(True))
        elif filters.is_currently_employed_in_title is False and title_values:
            row_conditions.append(CandidateExperience.is_current.is_(False))

        conditions = []
        if title_values or company_values or filters.is_currently_employed_in_title is not None:
            conditions.append(exists(select(1).where(*row_conditions)))

        if filters.min_relevant_experience_months is not None:
            duration_conditions = [
                CandidateExperience.document_id == CandidateProfile.document_id,
            ]
            if title_values:
                duration_conditions.append(
                    func.lower(CandidateExperience.job_title_normalized).in_(title_values)
                )
            if company_values:
                duration_conditions.append(
                    func.lower(CandidateExperience.company_name_raw).in_(company_values)
                )
            relevant_months = (
                select(func.coalesce(func.sum(CandidateExperience.duration_months), 0))
                .where(*duration_conditions)
                .scalar_subquery()
            )
            conditions.append(
                relevant_months >= filters.min_relevant_experience_months
            )
        return conditions

    def _build_education_conditions(self, filters: CandidateSearchFilters) -> list:
        return []

    def _build_certification_conditions(self, filters: CandidateSearchFilters) -> list:
        if not filters.certifications:
            return []
        return [
            exists(
                select(1).where(
                    CandidateCertification.document_id == CandidateProfile.document_id,
                    func.lower(CandidateCertification.certification_name_normalized).in_(
                        filters.certifications
                    ),
                )
            )
        ]

    def _skill_source_condition(self, source_type: str) -> list:
        if source_type in {"any", "", None}:
            return []
        return [CandidateSkill.source_type == source_type]

    def _language_proficiency_condition(self, language_filter: CandidateLanguageFilter):
        min_level = normalize_language_level(language_filter.min_proficiency_normalized)
        if min_level is None:
            return literal(True)

        candidate_rank = func.coalesce(
            func.lower(CandidateLanguage.proficiency_normalized),
            "",
        )
        rank_expr = func.coalesce(
            case(
                *[
                    (candidate_rank == level, rank)
                    for level, rank in LANGUAGE_PROFICIENCY_ORDER.items()
                ],
                else_=0,
            ),
            0,
        )
        return rank_expr >= LANGUAGE_PROFICIENCY_ORDER.get(min_level, 0)

    def _sort_column(self, sort_by: str):
        if sort_by == "created_at":
            return CandidateProfile.created_at
        if sort_by == "total_experience_months":
            return func.coalesce(CandidateProfile.total_experience_months, 0)
        if sort_by == "full_name":
            return func.lower(func.coalesce(CandidateProfile.full_name, ""))
        return CandidateProfile.updated_at

    def _rank_result_items(
        self,
        items: list[CandidateSearchResultItem],
    ) -> list[CandidateSearchResultItem]:
        """Sort candidates by recruiter-facing fit before pagination.

        SQL ordering remains useful as a stable fallback, but once we have match
        scores we prefer them over raw update timestamps. This keeps the broad,
        recall-first result set usable by surfacing the strongest candidates first.
        """

        if not any(item.match_score_percent is not None for item in items):
            return items

        return sorted(
            items,
            key=lambda item: (
                -(item.match_score_percent or -1),
                -(item.total_experience_months or -1),
                (item.full_name or "").strip().lower(),
                item.candidate_id,
            ),
        )

    async def _load_match_metadata(
        self,
        profiles: list[CandidateProfile],
        filters: CandidateSearchFilters,
    ) -> dict[str, CandidateSearchMatchMetadata]:
        if not profiles:
            return {}
        document_ids = [profile.document_id for profile in profiles]
        matched_skills = await self._load_matched_skills(document_ids, filters)
        matched_languages = await self._load_matched_languages(document_ids, filters)
        matched_employment_types = await self._load_matched_employment_types(
            document_ids,
            filters,
        )
        education_metadata = await self._load_education_metadata(document_ids, filters)
        metadata: dict[str, CandidateSearchMatchMetadata] = {}
        for document_id in document_ids:
            metadata[document_id] = CandidateSearchMatchMetadata(
                matched_skills=matched_skills.get(document_id, []),
                matched_languages=matched_languages.get(document_id, []),
                matched_employment_types=matched_employment_types.get(document_id, []),
                matched_degrees=education_metadata.get(document_id, {}).get(
                    "matched_degrees",
                    [],
                ),
                matched_fields_of_study=education_metadata.get(document_id, {}).get(
                    "matched_fields_of_study",
                    [],
                ),
                education_match_status=education_metadata.get(document_id, {}).get(
                    "education_match_status"
                ),
                education_match_note=education_metadata.get(document_id, {}).get(
                    "education_match_note"
                ),
            )
        return metadata

    async def _load_matched_skills(
        self,
        document_ids: list[str],
        filters: CandidateSearchFilters,
    ) -> dict[str, list[str]]:
        requested_skills = self._requested_skills(filters)
        if not requested_skills:
            return {}
        stmt = select(CandidateSkill.document_id, CandidateSkill.normalized_skill).where(
            CandidateSkill.document_id.in_(document_ids),
            func.lower(CandidateSkill.normalized_skill).in_(requested_skills),
            *self._skill_source_condition(filters.skill_source_type),
        )
        result = await self.session.execute(stmt)
        items: dict[str, list[str]] = {}
        for document_id, skill in result.all():
            items.setdefault(document_id, []).append(skill)
        return {key: sorted(set(values)) for key, values in items.items()}

    async def _load_matched_languages(
        self,
        document_ids: list[str],
        filters: CandidateSearchFilters,
    ) -> dict[str, list[str]]:
        if not filters.languages:
            return {}
        target_languages = [item.language_normalized for item in filters.languages]
        stmt = select(
            CandidateLanguage.document_id,
            CandidateLanguage.language_normalized,
        ).where(
            CandidateLanguage.document_id.in_(document_ids),
            func.lower(CandidateLanguage.language_normalized).in_(
                [item.lower() for item in target_languages]
            ),
        )
        result = await self.session.execute(stmt)
        items: dict[str, list[str]] = {}
        for document_id, language in result.all():
            items.setdefault(document_id, []).append(language)
        return {key: sorted(set(values)) for key, values in items.items()}

    async def _load_matched_employment_types(
        self,
        document_ids: list[str],
        filters: CandidateSearchFilters,
    ) -> dict[str, list[str]]:
        if not filters.employment_types:
            return {}

        stmt = select(
            CandidateProfile.document_id,
            CandidateProfile.employment_types_json,
        ).where(CandidateProfile.document_id.in_(document_ids))
        result = await self.session.execute(stmt)

        items: dict[str, list[str]] = {}
        requested = set(filters.employment_types)
        for document_id, employment_types_json in result.all():
            candidate_values = set(
                self._normalize_employment_types(_parse_json_array(employment_types_json))
                or []
            )
            if not candidate_values:
                continue
            matched = sorted(candidate_values & requested)
            if matched:
                items[document_id] = matched
        return items

    async def _load_education_metadata(
        self,
        document_ids: list[str],
        filters: CandidateSearchFilters,
    ) -> dict[str, dict]:
        """Return education compatibility as metadata instead of hard filtering.

        Education requirements are treated as a soft compatibility signal for search.
        This prevents strong candidates from disappearing purely because their degree is
        below the requested level while still exposing the gap in the result payload.
        """

        requested_degrees = self._normalize_degrees(filters.degree_normalized) or []
        requested_fields = self._normalize_strings(filters.fields_of_study) or []
        if not requested_degrees and not requested_fields:
            return {}

        stmt = select(
            CandidateEducation.document_id,
            CandidateEducation.degree_normalized,
            CandidateEducation.field_of_study,
        ).where(CandidateEducation.document_id.in_(document_ids))
        result = await self.session.execute(stmt)

        grouped: dict[str, dict[str, list[str]]] = {}
        for document_id, degree_normalized, field_of_study in result.all():
            bucket = grouped.setdefault(
                document_id,
                {"degrees": [], "fields_of_study": []},
            )
            if degree_normalized:
                bucket["degrees"].append(str(degree_normalized))
            if field_of_study:
                bucket["fields_of_study"].append(str(field_of_study))

        metadata: dict[str, dict] = {}
        for document_id in document_ids:
            candidate_item = grouped.get(
                document_id,
                {"degrees": [], "fields_of_study": []},
            )
            metadata[document_id] = self._evaluate_education_match(
                candidate_degrees=self._normalize_degrees(candidate_item["degrees"]) or [],
                candidate_fields=self._normalize_strings(
                    candidate_item["fields_of_study"]
                )
                or [],
                requested_degrees=requested_degrees,
                requested_fields=requested_fields,
            )
        return metadata

    def _evaluate_education_match(
        self,
        *,
        candidate_degrees: list[str],
        candidate_fields: list[str],
        requested_degrees: list[str],
        requested_fields: list[str],
    ) -> dict:
        """Compare requested education against candidate education.

        Degree filtering is intentionally modeled as set overlap for the user-provided
        filter values. If the recruiter selects multiple degree levels, we interpret this
        as "any of these levels is acceptable", not as "candidate must satisfy the
        highest selected level".

        Example:
        - requested degrees = ["master", "phd"]
        - candidate degrees = ["master"]
        -> this is a match because the sets intersect

        Field-of-study remains a secondary signal:
        - degree overlap + missing field overlap -> partial
        - no degree overlap -> mismatch
        - no degree filter, only field filter -> matched/mismatch by field overlap
        """

        highest_candidate_degree = self._highest_degree(candidate_degrees)
        highest_requested_degree = self._highest_degree(requested_degrees)
        matched_degrees = sorted(set(candidate_degrees) & set(requested_degrees))
        matched_fields = sorted(set(candidate_fields) & set(requested_fields))

        if requested_degrees and not matched_degrees:
            return {
                "matched_degrees": matched_degrees,
                "matched_fields_of_study": matched_fields,
                "education_match_status": "mismatch",
                "education_match_note": (
                    f"No overlap with requested degree levels: requested {', '.join(requested_degrees)}, "
                    f"candidate has {', '.join(candidate_degrees) if candidate_degrees else 'not specified'}."
                ),
            }

        if requested_fields and not matched_fields:
            return {
                "matched_degrees": matched_degrees or candidate_degrees,
                "matched_fields_of_study": matched_fields,
                "education_match_status": "partial" if requested_degrees else "mismatch",
                "education_match_note": (
                    "Degree filter matches, but requested field of study is not explicitly present."
                    if requested_degrees
                    else "Requested field of study is not explicitly present."
                ),
            }

        return {
            "matched_degrees": matched_degrees or candidate_degrees,
            "matched_fields_of_study": matched_fields,
            "education_match_status": "matched",
            "education_match_note": (
                f"Education filter matched on: {', '.join(matched_degrees)}."
                if matched_degrees
                else "Requested field of study is present."
            ),
        }

    @staticmethod
    def _highest_degree(values: list[str]) -> str | None:
        if not values:
            return None
        return max(values, key=lambda value: education_level_rank(value) or 0)

    def _normalize_filters(self, filters: CandidateSearchFilters) -> CandidateSearchFilters:
        return CandidateSearchFilters(
            query_text=filters.query_text,
            candidate_ids=self._unique(filters.candidate_ids),
            current_title_normalized=self._normalize_titles(filters.current_title_normalized),
            seniority_normalized=self._normalize_strings(filters.seniority_normalized),
            min_total_experience_months=filters.min_total_experience_months,
            max_total_experience_months=filters.max_total_experience_months,
            location_normalized=self._normalize_locations(filters.location_normalized),
            remote_policies=self._normalize_remote_policies(filters.remote_policies),
            employment_types=self._normalize_employment_types(filters.employment_types),
            languages=self._normalize_language_filters(filters.languages),
            require_all_languages=filters.require_all_languages,
            include_skills=self._normalize_skills(filters.include_skills),
            optional_skills=self._normalize_skills(filters.optional_skills),
            require_all_skills=filters.require_all_skills,
            skill_source_type=filters.skill_source_type,
            current_or_past_titles=self._normalize_titles(filters.current_or_past_titles),
            companies=self._normalize_strings(filters.companies),
            domains=self._normalize_strings(filters.domains),
            min_relevant_experience_months=filters.min_relevant_experience_months,
            is_currently_employed_in_title=filters.is_currently_employed_in_title,
            degree_normalized=self._normalize_degrees(filters.degree_normalized),
            fields_of_study=self._normalize_strings(filters.fields_of_study),
            certifications=self._normalize_strings(filters.certifications),
            chunk_types=self._normalize_strings(filters.chunk_types),
            score_threshold=filters.score_threshold,
            limit=filters.limit,
            offset=filters.offset,
            sort_by=filters.sort_by,
            sort_order=filters.sort_order,
        )

    def _requested_skills(self, filters: CandidateSearchFilters) -> list[str]:
        requested_skills: list[str] = []
        for value in [
            *(filters.include_skills or []),
            *(filters.optional_skills or []),
        ]:
            if value not in requested_skills:
                requested_skills.append(value)
        return requested_skills

    def _normalize_language_filters(
        self,
        languages: list[CandidateLanguageFilter] | None,
    ) -> list[CandidateLanguageFilter] | None:
        if not languages:
            return None
        normalized = []
        for item in languages:
            language = self._normalize_language_name(item.language_normalized)
            if not language:
                continue
            normalized.append(
                CandidateLanguageFilter(
                    language_normalized=language,
                    min_proficiency_normalized=normalize_language_level(
                        item.min_proficiency_normalized
                    ),
                )
            )
        return normalized or None

    @staticmethod
    def _normalize_skills(values: list[str] | None) -> list[str] | None:
        if not values:
            return None
        normalized = [normalize_skill_name(value) for value in values]
        return [value for value in dict.fromkeys(normalized) if value]

    @staticmethod
    def _normalize_titles(values: list[str] | None) -> list[str] | None:
        if not values:
            return None
        normalized = [normalize_job_title(value) for value in values]
        logger.debug("Normalized job titles: {normalized}", normalized=normalized)
        return [value for value in dict.fromkeys(normalized) if value]

    @staticmethod
    def _normalize_degrees(values: list[str] | None) -> list[str] | None:
        if not values:
            return None
        normalized = [normalize_degree(value) for value in values]
        return [value for value in dict.fromkeys(normalized) if value]

    @staticmethod
    def _normalize_strings(values: list[str] | None) -> list[str] | None:
        if not values:
            return None
        normalized = [
            " ".join(value.strip().lower().split())
            for value in values
            if value and value.strip()
        ]
        return list(dict.fromkeys(normalized)) or None

    def _normalize_locations(self, values: list[str] | None) -> list[str] | None:
        if not values:
            return None
        normalized = [self._normalize_location(value) for value in values]
        return [value for value in dict.fromkeys(normalized) if value]

    @staticmethod
    def _normalize_remote_policies(values: list[str] | None) -> list[str] | None:
        extracted = extract_remote_policies(values)
        return list(dict.fromkeys(extracted)) if extracted else None

    @staticmethod
    def _normalize_employment_types(values: list[str] | None) -> list[str] | None:
        extracted = extract_employment_types(values)
        return list(dict.fromkeys(extracted)) if extracted else None

    @staticmethod
    def _normalize_location(value: str | None) -> str | None:
        if not value or not value.strip():
            return None
        return " ".join(value.strip().lower().split())

    @staticmethod
    def _normalize_language_name(value: str | None) -> str | None:
        if not value or not value.strip():
            return None
        normalized = " ".join(value.strip().split())
        return normalized.title()

    @staticmethod
    def _unique(values: list[str] | None) -> list[str] | None:
        if not values:
            return None
        return list(dict.fromkeys(value for value in values if value))


def _parse_json_array(value: str | None) -> list[str] | None:
    if not value:
        return None
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list):
        return None
    items = [item for item in parsed if isinstance(item, str)]
    return items or None
