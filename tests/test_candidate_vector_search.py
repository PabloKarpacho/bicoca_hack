import json
import math

import pytest

from app.config.enums.document_status import DocumentProcessingStatus
from app.models.candidate_search import CandidateSearchFilters
from app.service.search.candidate_chunk_builder import CandidateChunkBuilderService
from app.service.search.candidate_embedding_service import CandidateEmbeddingService
from app.service.search.candidate_vector_indexing import CandidateVectorIndexingService
from app.service.search.candidate_vector_search import CandidateVectorSearchService
from database.postgres.crud.cv import (
    CandidateDocumentChunkRepository,
    CandidateDocumentRepository,
    CandidateExperienceRepository,
    CandidateLanguageRepository,
    CandidateProfileRepository,
    CandidateRepository,
    CandidateSkillRepository,
)


class FakeEmbeddings:
    TOKENS = [
        "python",
        "fastapi",
        "backend",
        "frontend",
        "react",
        "fintech",
        "postgresql",
        "data",
    ]

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    async def aembed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        normalized = text.lower()
        return [float(normalized.count(token)) for token in self.TOKENS]


class FakeQdrant:
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, dict]] = {}

    async def create_collection(self, collection_name: str, vector_size: int, metadata: dict | None = None) -> None:
        self.collections.setdefault(collection_name, {})

    async def delete_vectors_by_document_id(self, collection_name: str, document_id: str) -> None:
        collection = self.collections.setdefault(collection_name, {})
        for point_id in [
            key
            for key, value in collection.items()
            if value["payload"].get("document_id") == document_id
        ]:
            collection.pop(point_id, None)

    async def delete_points_by_ids(self, collection_name: str, point_ids: list[str]) -> None:
        collection = self.collections.setdefault(collection_name, {})
        for point_id in point_ids:
            collection.pop(point_id, None)

    async def upsert_points(self, collection_name: str, points: list[dict]) -> None:
        collection = self.collections.setdefault(collection_name, {})
        for point in points:
            collection[point["id"]] = {
                "vector": point["vector"],
                "payload": point["payload"],
            }

    async def search_points(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int,
        candidate_ids: list[str] | None = None,
        chunk_types: list[str] | None = None,
        score_threshold: float = 0.0,
    ) -> list[dict]:
        collection = self.collections.get(collection_name, {})
        hits = []
        for point_id, item in collection.items():
            payload = item["payload"]
            if candidate_ids and payload.get("candidate_id") not in candidate_ids:
                continue
            if chunk_types and payload.get("chunk_type") not in chunk_types:
                continue
            score = _cosine_similarity(query_vector, item["vector"])
            if score < score_threshold:
                continue
            hits.append({"id": point_id, "score": score, "payload": payload})
        hits.sort(key=lambda hit: hit["score"], reverse=True)
        return hits[:limit]


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


async def _seed_candidate(
    session,
    *,
    external_id: str,
    full_name: str,
    current_title_normalized: str,
    seniority_normalized: str,
    total_experience_months: int,
    summary: str,
    skills: list[str],
    languages: list[str],
    proficiency: str,
    experience_title: str,
    company: str,
    domain: str,
) -> tuple[str, str]:
    candidates = CandidateRepository(session)
    documents = CandidateDocumentRepository(session)
    profiles = CandidateProfileRepository(session)
    skill_repo = CandidateSkillRepository(session)
    language_repo = CandidateLanguageRepository(session)
    experience_repo = CandidateExperienceRepository(session)

    candidate = await candidates.create(
        external_id=external_id,
        full_name=full_name,
        email=f"{external_id}@example.com",
    )
    document = await documents.create(
        candidate_id=candidate.candidate_id,
        original_filename=f"{external_id}.docx",
        file_extension="docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=100,
        checksum_sha256=f"checksum-{external_id}",
        processing_status=DocumentProcessingStatus.RAW_TEXT_READY,
    )
    await profiles.create(
        candidate_id=candidate.candidate_id,
        document_id=document.document_id,
        full_name=full_name,
        headline=current_title_normalized.replace("_", " "),
        summary=summary,
        current_title_normalized=current_title_normalized,
        seniority_normalized=seniority_normalized,
        total_experience_months=total_experience_months,
        location_raw="Milan",
    )
    for skill in skills:
        await skill_repo.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            raw_skill=skill,
            normalized_skill=skill,
            skill_category="programming_language",
            source_type="explicit",
            confidence=0.9,
        )
    for language in languages:
        await language_repo.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            language_raw=language,
            language_normalized=language.title(),
            proficiency_raw=proficiency,
            proficiency_normalized=proficiency,
            confidence=0.9,
        )
    await experience_repo.create(
        candidate_id=candidate.candidate_id,
        document_id=document.document_id,
        position_order=1,
        company_name_raw=company,
        job_title_raw=experience_title.replace("_", " "),
        job_title_normalized=experience_title,
        duration_months=max(total_experience_months - 12, 12),
        responsibilities_text=f"Built {domain} systems",
        technologies_text=", ".join(skills),
        domain_hint=domain,
        is_current=True,
    )
    await session.commit()
    return candidate.candidate_id, document.document_id


@pytest.mark.asyncio
async def test_candidate_chunk_builder_builds_expected_chunk_types(db_sessionmaker):
    async with db_sessionmaker() as session:
        _, document_id = await _seed_candidate(
            session,
            external_id="alice",
            full_name="Alice",
            current_title_normalized="backend_engineer",
            seniority_normalized="senior",
            total_experience_months=72,
            summary="Backend engineer focused on Python and fintech APIs.",
            skills=["python", "fastapi", "postgresql"],
            languages=["english"],
            proficiency="professional",
            experience_title="backend_engineer",
            company="Example Inc",
            domain="fintech",
        )
        builder = CandidateChunkBuilderService(
            profiles=CandidateProfileRepository(session),
            languages=CandidateLanguageRepository(session),
            experiences=CandidateExperienceRepository(session),
            skills=CandidateSkillRepository(session),
        )

        chunks = await builder.build_document_chunks(document_id)

        assert [chunk.chunk_type for chunk in chunks] == [
            "role_profile",
            "experience_role",
            "skills_profile",
        ]
        assert "Current role: backend engineer." in chunks[0].chunk_text
        assert "Core skills: fastapi, postgresql, python." in chunks[0].chunk_text
        assert chunks[1].source_entity_type == "candidate_experience"
        assert "Core skills: fastapi, postgresql, python." in chunks[2].chunk_text


@pytest.mark.asyncio
async def test_vector_indexing_persists_chunks_and_upserts_qdrant(db_sessionmaker):
    fake_qdrant = FakeQdrant()
    async with db_sessionmaker() as session:
        candidate_id, document_id = await _seed_candidate(
            session,
            external_id="alice",
            full_name="Alice",
            current_title_normalized="backend_engineer",
            seniority_normalized="senior",
            total_experience_months=72,
            summary="Backend engineer focused on Python and fintech APIs.",
            skills=["python", "fastapi", "postgresql"],
            languages=["english"],
            proficiency="professional",
            experience_title="backend_engineer",
            company="Example Inc",
            domain="fintech",
        )
        service = CandidateVectorIndexingService(
            session=session,
            qdrant=fake_qdrant,
            embedding_service=CandidateEmbeddingService(
                embeddings=FakeEmbeddings(),
                model_version="fake-embeddings-v1",
            ),
            collection_name="candidate_chunks",
        )

        result = await service.index_document(document_id)
        chunk_rows = await CandidateDocumentChunkRepository(session).list_by_document_id(
            document_id
        )

        assert result.candidate_id == candidate_id
        assert result.chunk_count == 3
        assert len(chunk_rows) == 3
        assert all(chunk.embedding_status == "indexed" for chunk in chunk_rows)
        assert len(fake_qdrant.collections["candidate_chunks"]) == 3


@pytest.mark.asyncio
async def test_vector_search_aggregates_chunks_by_candidate(db_sessionmaker):
    fake_qdrant = FakeQdrant()
    async with db_sessionmaker() as session:
        _, document_a = await _seed_candidate(
            session,
            external_id="alice",
            full_name="Alice",
            current_title_normalized="backend_engineer",
            seniority_normalized="senior",
            total_experience_months=72,
            summary="Backend engineer focused on Python and fintech APIs.",
            skills=["python", "fastapi", "postgresql"],
            languages=["english"],
            proficiency="professional",
            experience_title="backend_engineer",
            company="Example Inc",
            domain="fintech",
        )
        _, document_b = await _seed_candidate(
            session,
            external_id="bob",
            full_name="Bob",
            current_title_normalized="frontend_engineer",
            seniority_normalized="mid",
            total_experience_months=48,
            summary="Frontend engineer focused on React.",
            skills=["react"],
            languages=["english"],
            proficiency="fluent",
            experience_title="frontend_engineer",
            company="UI Inc",
            domain="ecommerce",
        )
        indexing = CandidateVectorIndexingService(
            session=session,
            qdrant=fake_qdrant,
            embedding_service=CandidateEmbeddingService(
                embeddings=FakeEmbeddings(),
                model_version="fake-embeddings-v1",
            ),
            collection_name="candidate_chunks",
        )
        await indexing.index_document(document_a)
        await indexing.index_document(document_b)

        search = CandidateVectorSearchService(
            session=session,
            qdrant=fake_qdrant,
            embedding_service=CandidateEmbeddingService(
                embeddings=FakeEmbeddings(),
                model_version="fake-embeddings-v1",
            ),
            collection_name="candidate_chunks",
        )
        result = await search.search(
            CandidateSearchFilters(
                query_text="senior python backend fastapi fintech",
                score_threshold=0.0,
                limit=5,
            )
        )

        assert result.total == 2
        assert result.items[0].full_name == "Alice"
        assert result.items[0].score is not None
        assert result.items[0].matched_chunk_type in {
            "role_profile",
            "skills_profile",
            "experience_role",
        }
        assert len(result.items[0].top_chunks or []) >= 1


@pytest.mark.asyncio
async def test_vector_search_respects_shortlist_candidate_ids(db_sessionmaker):
    fake_qdrant = FakeQdrant()
    async with db_sessionmaker() as session:
        candidate_a, document_a = await _seed_candidate(
            session,
            external_id="alice",
            full_name="Alice",
            current_title_normalized="backend_engineer",
            seniority_normalized="senior",
            total_experience_months=72,
            summary="Backend engineer focused on Python.",
            skills=["python", "fastapi"],
            languages=["english"],
            proficiency="professional",
            experience_title="backend_engineer",
            company="Example Inc",
            domain="fintech",
        )
        candidate_b, document_b = await _seed_candidate(
            session,
            external_id="bob",
            full_name="Bob",
            current_title_normalized="backend_engineer",
            seniority_normalized="mid",
            total_experience_months=48,
            summary="Backend engineer with data focus.",
            skills=["python", "data"],
            languages=["english"],
            proficiency="professional",
            experience_title="backend_engineer",
            company="Data Corp",
            domain="data",
        )
        indexing = CandidateVectorIndexingService(
            session=session,
            qdrant=fake_qdrant,
            embedding_service=CandidateEmbeddingService(
                embeddings=FakeEmbeddings(),
                model_version="fake-embeddings-v1",
            ),
            collection_name="candidate_chunks",
        )
        await indexing.index_document(document_a)
        await indexing.index_document(document_b)

        search = CandidateVectorSearchService(
            session=session,
            qdrant=fake_qdrant,
            embedding_service=CandidateEmbeddingService(
                embeddings=FakeEmbeddings(),
                model_version="fake-embeddings-v1",
            ),
            collection_name="candidate_chunks",
        )
        result = await search.search(
            CandidateSearchFilters(
                query_text="python backend",
                candidate_ids=[candidate_b],
                score_threshold=0.0,
                limit=5,
            )
        )

        assert result.total == 1
        assert result.items[0].candidate_id == candidate_b
        assert result.items[0].candidate_id != candidate_a


@pytest.mark.asyncio
async def test_vector_search_can_build_query_from_profession_filters(db_sessionmaker):
    fake_qdrant = FakeQdrant()
    async with db_sessionmaker() as session:
        candidate_a, document_a = await _seed_candidate(
            session,
            external_id="alice-profession",
            full_name="Alice",
            current_title_normalized="backend_engineer",
            seniority_normalized="senior",
            total_experience_months=72,
            summary="Backend engineer focused on APIs.",
            skills=["python", "fastapi"],
            languages=["english"],
            proficiency="professional",
            experience_title="backend_engineer",
            company="Example Inc",
            domain="fintech",
        )
        _, document_b = await _seed_candidate(
            session,
            external_id="carol-profession",
            full_name="Carol",
            current_title_normalized="frontend_engineer",
            seniority_normalized="senior",
            total_experience_months=72,
            summary="Frontend engineer focused on React.",
            skills=["javascript", "react"],
            languages=["english"],
            proficiency="professional",
            experience_title="frontend_engineer",
            company="Shop Co",
            domain="ecommerce",
        )
        indexing = CandidateVectorIndexingService(
            session=session,
            qdrant=fake_qdrant,
            embedding_service=CandidateEmbeddingService(
                embeddings=FakeEmbeddings(),
                model_version="fake-embeddings-v1",
            ),
            collection_name="candidate_chunks",
        )
        await indexing.index_document(document_a)
        await indexing.index_document(document_b)

        search = CandidateVectorSearchService(
            session=session,
            qdrant=fake_qdrant,
            embedding_service=CandidateEmbeddingService(
                embeddings=FakeEmbeddings(),
                model_version="fake-embeddings-v1",
            ),
            collection_name="candidate_chunks",
        )
        result = await search.search(
            CandidateSearchFilters(
                current_title_normalized=["backend_engineer"],
                score_threshold=0.0,
                limit=5,
            )
        )

        assert result.total >= 1
        assert result.items[0].candidate_id == candidate_a
        assert result.items[0].current_title_normalized == "backend_engineer"
        assert result.items[0].matched_chunk_type in {"role_profile", "experience_role"}


@pytest.mark.asyncio
async def test_vector_reindex_replaces_existing_points_and_chunks(db_sessionmaker):
    fake_qdrant = FakeQdrant()
    async with db_sessionmaker() as session:
        _, document_id = await _seed_candidate(
            session,
            external_id="alice",
            full_name="Alice",
            current_title_normalized="backend_engineer",
            seniority_normalized="senior",
            total_experience_months=72,
            summary="Backend engineer focused on Python.",
            skills=["python", "fastapi"],
            languages=["english"],
            proficiency="professional",
            experience_title="backend_engineer",
            company="Example Inc",
            domain="fintech",
        )
        indexing = CandidateVectorIndexingService(
            session=session,
            qdrant=fake_qdrant,
            embedding_service=CandidateEmbeddingService(
                embeddings=FakeEmbeddings(),
                model_version="fake-embeddings-v1",
            ),
            collection_name="candidate_chunks",
        )
        await indexing.index_document(document_id)

        skills = CandidateSkillRepository(session)
        document = await CandidateDocumentRepository(session).get_plain_by_id(document_id)
        await skills.create(
            candidate_id=document.candidate_id,
            document_id=document_id,
            raw_skill="data",
            normalized_skill="data",
            skill_category="data",
            source_type="explicit",
            confidence=0.8,
        )
        await session.commit()

        result = await indexing.index_document(document_id)
        chunk_rows = await CandidateDocumentChunkRepository(session).list_by_document_id(
            document_id
        )
        skills_profile = next(chunk for chunk in chunk_rows if chunk.chunk_type == "skills_profile")
        metadata = json.loads(skills_profile.chunk_metadata_json or "{}")

        assert result.chunk_count == 3
        assert len(fake_qdrant.collections["candidate_chunks"]) == 3
        assert "data" in metadata["skill_tags"]


@pytest.mark.asyncio
async def test_vector_search_resolves_query_intent_and_chunk_types(db_sessionmaker):
    fake_qdrant = FakeQdrant()
    async with db_sessionmaker() as session:
        search = CandidateVectorSearchService(
            session=session,
            qdrant=fake_qdrant,
            embedding_service=CandidateEmbeddingService(
                embeddings=FakeEmbeddings(),
                model_version="fake-embeddings-v1",
            ),
            collection_name="candidate_chunks",
        )

        profession_filters = CandidateSearchFilters(
            current_title_normalized=["backend_engineer"],
            seniority_normalized=["senior"],
        )
        experience_filters = CandidateSearchFilters(
            query_text_responsibilities="build backend services and own API delivery",
            domains=["fintech"],
        )
        skills_filters = CandidateSearchFilters(
            include_skills=["python", "fastapi"],
        )
        mixed_filters = CandidateSearchFilters(
            current_title_normalized=["backend_engineer"],
            include_skills=["python"],
            query_text_responsibilities="build backend services",
        )

        assert search._resolve_query_intent(profession_filters) == "profession_centric"
        assert search._resolve_query_intent(experience_filters) == "experience_centric"
        assert search._resolve_query_intent(skills_filters) == "skills_centric"
        assert search._resolve_query_intent(mixed_filters) == "mixed"
        assert search._resolve_chunk_types(profession_filters) == [
            "role_profile",
            "experience_role",
        ]
        assert search._resolve_chunk_types(experience_filters) == [
            "experience_role",
            "role_profile",
        ]
        assert search._resolve_chunk_types(skills_filters) == [
            "skills_profile",
            "experience_role",
            "role_profile",
        ]
        assert search._resolve_chunk_types(
            CandidateSearchFilters(chunk_types=["skills_profile"])
        ) == ["skills_profile"]


@pytest.mark.asyncio
async def test_vector_aggregation_uses_top_k_and_diversity_bonus(db_sessionmaker):
    fake_qdrant = FakeQdrant()
    async with db_sessionmaker() as session:
        search = CandidateVectorSearchService(
            session=session,
            qdrant=fake_qdrant,
            embedding_service=CandidateEmbeddingService(
                embeddings=FakeEmbeddings(),
                model_version="fake-embeddings-v1",
            ),
            collection_name="candidate_chunks",
        )

        aggregated = search._aggregate_hits(
            [
                {
                    "id": "skills-a",
                    "score": 0.95,
                    "payload": {
                        "candidate_id": "cand-a",
                        "document_id": "doc-a",
                        "chunk_id": "skills-a",
                        "chunk_type": "skills_profile",
                        "text": "Core skills: python, fastapi",
                    },
                },
                {
                    "id": "exp-b",
                    "score": 0.90,
                    "payload": {
                        "candidate_id": "cand-b",
                        "document_id": "doc-b",
                        "chunk_id": "exp-b",
                        "chunk_type": "experience_role",
                        "text": "Role: backend engineer",
                    },
                },
                {
                    "id": "role-b",
                    "score": 0.82,
                    "payload": {
                        "candidate_id": "cand-b",
                        "document_id": "doc-b",
                        "chunk_id": "role-b",
                        "chunk_type": "role_profile",
                        "text": "Current role: backend engineer",
                    },
                },
            ]
        )

        assert aggregated["cand-b"].score is not None
        assert aggregated["cand-a"].score is not None
        assert aggregated["cand-b"].score > aggregated["cand-a"].score
        assert aggregated["cand-b"].matched_chunk_type == "experience_role"
        assert len(aggregated["cand-b"].top_chunks or []) == 2
