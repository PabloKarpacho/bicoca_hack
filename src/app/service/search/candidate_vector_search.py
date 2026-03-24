from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.candidate_search import (
    CandidateSearchFilters,
    CandidateSearchResult,
    CandidateSearchResultItem,
)
from app.models.candidate_vector import (
    CandidateVectorDebugHit,
    CandidateVectorDebugSearchResponse,
)
from app.service.search.candidate_embedding_service import CandidateEmbeddingService
from app.service.search.candidate_match_scoring import calculate_candidate_match_score
from app.service.vector_db.qdrant.qdrant_api import QdrantAPI
from database.postgres.schema import CandidateProfile


class CandidateVectorSearchError(RuntimeError):
    pass


QueryIntent = Literal[
    "profession_centric",
    "experience_centric",
    "skills_centric",
    "mixed",
]


@dataclass(slots=True)
class CandidateVectorSearchService:
    session: AsyncSession
    qdrant: QdrantAPI | None
    embedding_service: CandidateEmbeddingService | None = None
    collection_name: str = settings.qdrant_candidate_chunks_collection_name

    def __post_init__(self) -> None:
        self.embedding_service = self.embedding_service or CandidateEmbeddingService()

    async def search(self, filters: CandidateSearchFilters) -> CandidateSearchResult:
        if self.qdrant is None:
            raise CandidateVectorSearchError("Qdrant is not configured")
        query_text = self._build_query_text(filters)
        if query_text is None:
            raise CandidateVectorSearchError(
                "query_text or semantic filters are required for vector search"
            )

        logger.info(
            "Candidate vector search: start query_text_length={query_length}, shortlist_candidate_ids={candidate_ids}, chunk_types={chunk_types}, intent={intent}, limit={limit}",
            query_length=len(query_text),
            candidate_ids=len(filters.candidate_ids or []),
            chunk_types=len(self._resolve_chunk_types(filters) or []),
            intent=self._resolve_query_intent(filters),
            limit=filters.limit,
        )
        logger.debug(f"Candidate vector search: full query_text='{query_text}'")

        chunk_types = self._resolve_chunk_types(filters)
        query_vector = await self.embedding_service.embed_query(query_text)
        try:
            raw_hits = await self.qdrant.search_points(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=max(filters.limit * 5, filters.limit),
                candidate_ids=filters.candidate_ids,
                chunk_types=chunk_types,
                score_threshold=filters.score_threshold,
            )
            logger.debug(
                f"Candidate vector search: raw_hits_count={len(raw_hits)}, raw_hits={raw_hits}"
            )
        except ValueError:
            raw_hits = []
        aggregated = self._aggregate_hits(raw_hits)
        ordered_items = sorted(
            aggregated.values(),
            key=lambda item: ((item.score or 0.0), item.candidate_id),
            reverse=True,
        )
        sliced = ordered_items[filters.offset : filters.offset + filters.limit]
        profiles = await self._load_profiles(sliced)
        items = []
        for item in sliced:
            profile = profiles.get(item.document_id)
            match_score_percent, match_score_breakdown = calculate_candidate_match_score(
                filters=filters,
                current_title_normalized=(
                    profile.current_title_normalized if profile else None
                ),
                total_experience_months=(
                    profile.total_experience_months if profile else None
                ),
                match_metadata=item.match_metadata,
                vector_semantic_score=item.score,
            )
            items.append(
                CandidateSearchResultItem(
                    candidate_id=item.candidate_id,
                    document_id=item.document_id,
                    score=item.score,
                    match_score_percent=match_score_percent,
                    match_score_breakdown=match_score_breakdown,
                    full_name=profile.full_name if profile else None,
                    current_title_normalized=(
                        profile.current_title_normalized if profile else None
                    ),
                    seniority_normalized=profile.seniority_normalized if profile else None,
                    total_experience_months=(
                        profile.total_experience_months if profile else None
                    ),
                    location_normalized=(
                        " ".join(profile.location_raw.strip().lower().split())
                        if profile and profile.location_raw
                        else None
                    ),
                    remote_policies=_parse_json_array(
                        profile.remote_policies_json if profile else None
                    ),
                    matched_chunk_type=item.matched_chunk_type,
                    matched_chunk_text_preview=item.matched_chunk_text_preview,
                    top_chunks=item.top_chunks,
                    match_metadata=None,
                )
            )
        logger.info(
            "Candidate vector search: completed candidates={total}, returned_items={returned_items}",
            total=len(ordered_items),
            returned_items=len(items),
        )
        return CandidateSearchResult(
            total=len(ordered_items),
            items=items,
            applied_filters=filters,
        )

    async def debug_search(
        self,
        query_text: str,
    ) -> CandidateVectorDebugSearchResponse:
        if self.qdrant is None:
            raise CandidateVectorSearchError("Qdrant is not configured")

        query_text = self._clean_text(query_text)
        if query_text is None:
            raise CandidateVectorSearchError(
                "query_text is required for vector debug search"
            )

        query_vector = await self.embedding_service.embed_query(query_text)
        try:
            raw_hits = await self.qdrant.search_points(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=20,
                candidate_ids=None,
                chunk_types=None,
                score_threshold=0.0,
            )
            distance_metric = await self.qdrant.get_collection_distance_metric(
                self.collection_name
            )
        except ValueError:
            raw_hits = []
            distance_metric = None

        return CandidateVectorDebugSearchResponse(
            query_text=query_text,
            vector_dimension=len(query_vector),
            collection_name=self.collection_name,
            distance_metric=distance_metric,
            chunk_types=None,
            score_threshold=0.0,
            hits=[
                CandidateVectorDebugHit(
                    point_id=str(hit.get("id", "")),
                    score=float(hit.get("score", 0.0)),
                    candidate_id=hit.get("payload", {}).get("candidate_id"),
                    document_id=hit.get("payload", {}).get("document_id"),
                    chunk_id=hit.get("payload", {}).get("chunk_id"),
                    chunk_type=hit.get("payload", {}).get("chunk_type"),
                    text_preview=(
                        str(hit.get("payload", {}).get("text", ""))[:240]
                        if hit.get("payload", {}).get("text")
                        else None
                    ),
                    payload=hit.get("payload", {}),
                )
                for hit in raw_hits
            ],
        )

    def _resolve_chunk_types(self, filters: CandidateSearchFilters) -> list[str] | None:
        if filters.chunk_types:
            return filters.chunk_types
        intent = self._resolve_query_intent(filters)
        if intent == "profession_centric":
            return ["role_profile", "experience_role"]
        if intent == "experience_centric":
            return ["experience_role", "role_profile"]
        if intent == "skills_centric":
            return ["skills_profile", "experience_role", "role_profile"]
        return ["role_profile", "experience_role", "skills_profile"]

    def _build_query_text(self, filters: CandidateSearchFilters) -> str | None:
        intent = self._resolve_query_intent(filters)
        profession_values = self._unique_preserving_order(
            [
                *[
                    self._humanize_token(value)
                    for value in (filters.current_title_normalized or [])
                ],
                *[
                    self._humanize_token(value)
                    for value in (filters.current_or_past_titles or [])
                ],
            ]
        )
        parts = self._build_query_parts(filters, intent, profession_values)
        cleaned_parts = [part for part in (self._clean_text(value) for value in parts) if part]
        if not cleaned_parts:
            return None
        return " ".join(cleaned_parts)

    def _clean_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        return cleaned or None

    def _humanize_token(self, value: str) -> str:
        return " ".join(value.replace("_", " ").split())

    def _unique_preserving_order(self, values: list[str]) -> list[str]:
        seen: set[str] = set()
        unique_values: list[str] = []
        for value in values:
            key = value.lower()
            if key in seen or not value.strip():
                continue
            seen.add(key)
            unique_values.append(value)
        return unique_values

    def _resolve_query_intent(self, filters: CandidateSearchFilters) -> QueryIntent:
        has_profession_signal = bool(
            (filters.current_title_normalized and len(filters.current_title_normalized) > 0)
            or (filters.current_or_past_titles and len(filters.current_or_past_titles) > 0)
            or bool(self._clean_text(filters.title_raw))
            or bool(filters.seniority_normalized)
        )
        has_experience_signal = bool(
            bool(self._clean_text(filters.query_text_responsibilities))
            or bool(filters.current_or_past_titles)
            or bool(filters.companies)
            or filters.min_relevant_experience_months is not None
            or filters.is_currently_employed_in_title is not None
        )
        has_skills_signal = bool(
            bool(self._clean_text(filters.query_text_skills))
            or bool(filters.include_skills)
            or bool(filters.optional_skills)
        )
        has_general_query = bool(self._clean_text(filters.query_text))

        active_modes = sum(
            1
            for flag in [has_profession_signal, has_experience_signal, has_skills_signal]
            if flag
        )

        if has_experience_signal and not has_profession_signal and not has_skills_signal:
            return "experience_centric"
        if has_skills_signal and not has_profession_signal and not has_experience_signal:
            return "skills_centric"
        if has_profession_signal and not has_experience_signal and not has_skills_signal and not has_general_query:
            return "profession_centric"
        if has_general_query and active_modes <= 1 and has_profession_signal:
            return "profession_centric"
        if has_general_query and active_modes <= 1 and has_skills_signal:
            return "skills_centric"
        if has_general_query and active_modes <= 1 and has_experience_signal:
            return "experience_centric"
        return "mixed"

    def _build_query_parts(
        self,
        filters: CandidateSearchFilters,
        intent: QueryIntent,
        profession_values: list[str],
    ) -> list[str]:
        base_query = self._clean_text(filters.query_text)
        title_raw = self._clean_text(filters.title_raw)
        seniority_values = (
            [self._humanize_token(value) for value in filters.seniority_normalized]
            if filters.seniority_normalized
            else []
        )
        required_skills = (
            [self._humanize_token(value) for value in filters.include_skills]
            if filters.include_skills
            else []
        )
        optional_skills = (
            [self._humanize_token(value) for value in filters.optional_skills]
            if filters.optional_skills
            else []
        )
        domains = (
            [self._humanize_token(value) for value in filters.domains]
            if filters.domains
            else []
        )
        language_fragments = []
        if filters.languages:
            for item in filters.languages:
                language = self._humanize_token(item.language_normalized)
                proficiency = self._clean_text(item.min_proficiency_normalized)
                language_fragments.append(
                    f"{language} ({proficiency})" if proficiency else language
                )

        if intent == "profession_centric":
            return [
                _build_sentence("Requested role", ", ".join(profession_values) if profession_values else title_raw),
                _build_sentence("Target seniority", ", ".join(seniority_values) if seniority_values else None),
                _build_sentence("Relevant domains", ", ".join(domains) if domains else None),
                _build_sentence("Core skills", ", ".join(required_skills[:8]) if required_skills else None),
                _build_sentence("Language requirements", ", ".join(language_fragments) if language_fragments else None),
                base_query,
            ]
        if intent == "experience_centric":
            return [
                self._clean_text(filters.query_text_responsibilities),
                _build_sentence("Responsibilities focus", base_query),
                _build_sentence("Relevant past roles", ", ".join(profession_values) if profession_values else None),
                _build_sentence("Relevant companies", ", ".join(filters.companies) if filters.companies else None),
                _build_sentence("Relevant domains", ", ".join(domains) if domains else None),
                _build_sentence(
                    "Relevant experience",
                    (
                        f"{filters.min_relevant_experience_months} months minimum"
                        if filters.min_relevant_experience_months is not None
                        else None
                    ),
                ),
            ]
        if intent == "skills_centric":
            return [
                self._clean_text(filters.query_text_skills),
                _build_sentence("Required skills", ", ".join(required_skills) if required_skills else None),
                _build_sentence("Supporting skills", ", ".join(optional_skills) if optional_skills else None),
                _build_sentence("Relevant roles", ", ".join(profession_values) if profession_values else None),
                _build_sentence("Relevant domains", ", ".join(domains) if domains else None),
                base_query,
            ]
        return [
            base_query,
            self._clean_text(filters.query_text_responsibilities),
            self._clean_text(filters.query_text_skills),
            _build_sentence("Requested role", ", ".join(profession_values) if profession_values else title_raw),
            _build_sentence("Target seniority", ", ".join(seniority_values) if seniority_values else None),
            _build_sentence("Required skills", ", ".join(required_skills) if required_skills else None),
            _build_sentence("Supporting skills", ", ".join(optional_skills) if optional_skills else None),
            _build_sentence("Relevant domains", ", ".join(domains) if domains else None),
            _build_sentence("Language requirements", ", ".join(language_fragments) if language_fragments else None),
            _build_sentence(
                "Locations",
                ", ".join(self._humanize_token(value) for value in filters.location_normalized)
                if filters.location_normalized
                else None,
            ),
            _build_sentence(
                "Employment type",
                ", ".join(self._humanize_token(value) for value in filters.employment_types)
                if filters.employment_types
                else None,
            ),
        ]

    def _aggregate_hits(self, raw_hits: list[dict]) -> dict[str, CandidateSearchResultItem]:
        """Aggregate chunk-level Qdrant hits into candidate-level semantic evidence.

        We intentionally aggregate over the best few chunks instead of using just the
        single best hit. This reduces noise from one accidentally high-scoring chunk and
        rewards candidates whose evidence is distributed across multiple relevant chunks.

        Current policy:
        - keep top 3 hits per candidate
        - weight `experience_role` highest, then `role_profile`, then `skills_profile`
        - down-weight lower-ranked hits with positional weights
        - add a small diversity bonus when multiple chunk types match

        The resulting `score` remains a vector-first ranking signal in the 0..1 range.
        A separate recruiter-facing percentage is computed later by
        `calculate_candidate_match_score(...)`, which combines this semantic score with
        explicit structured evidence such as skills, languages, and experience.
        """
        hits_by_candidate: dict[str, list[dict]] = {}
        for hit in raw_hits:
            payload = hit.get("payload", {})
            candidate_id = payload.get("candidate_id")
            if not candidate_id:
                continue
            hits_by_candidate.setdefault(candidate_id, []).append(hit)

        aggregated: dict[str, CandidateSearchResultItem] = {}
        type_weights = {
            "experience_role": 1.0,
            "role_profile": 0.85,
            "skills_profile": 0.65,
        }
        positional_weights = [1.0, 0.75, 0.55]

        for candidate_id, candidate_hits in hits_by_candidate.items():
            sorted_hits = sorted(
                candidate_hits,
                key=lambda item: float(item.get("score", 0.0)),
                reverse=True,
            )
            top_hits = sorted_hits[:3]
            if not top_hits:
                continue

            top_chunks = []
            weighted_score = 0.0
            positional_total = 0.0
            chunk_types = set()
            best_hit = top_hits[0]

            for index, hit in enumerate(top_hits):
                payload = hit.get("payload", {})
                chunk_type = payload.get("chunk_type")
                score = float(hit.get("score", 0.0))
                position_weight = positional_weights[index]
                type_weight = type_weights.get(chunk_type, 0.75)
                weighted_score += score * type_weight * position_weight
                positional_total += position_weight
                if chunk_type:
                    chunk_types.add(chunk_type)
                top_chunks.append(
                    {
                        "chunk_id": payload.get("chunk_id"),
                        "document_id": payload.get("document_id"),
                        "chunk_type": chunk_type,
                        "score": score,
                        "text_preview": str(payload.get("text", ""))[:240],
                    }
                )

            base_score = weighted_score / positional_total if positional_total else 0.0
            diversity_bonus = min(0.06, 0.03 * max(0, len(chunk_types) - 1))
            final_score = min(1.0, base_score + diversity_bonus)

            aggregated[candidate_id] = CandidateSearchResultItem(
                candidate_id=candidate_id,
                document_id=best_hit.get("payload", {}).get("document_id"),
                score=final_score,
                matched_chunk_type=best_hit.get("payload", {}).get("chunk_type"),
                matched_chunk_text_preview=str(best_hit.get("payload", {}).get("text", ""))[:240],
                top_chunks=top_chunks,
            )
        return aggregated

    async def _load_profiles(
        self,
        items: list[CandidateSearchResultItem],
    ) -> dict[str, CandidateProfile]:
        document_ids = [item.document_id for item in items]
        if not document_ids:
            return {}
        result = await self.session.execute(
            select(CandidateProfile).where(CandidateProfile.document_id.in_(document_ids))
        )
        profiles = list(result.scalars().all())
        return {profile.document_id: profile for profile in profiles}


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


def _build_sentence(label: str, value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).split())
    if not cleaned:
        return None
    return f"{label}: {cleaned}."
