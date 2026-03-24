from io import BytesIO
import math
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from httpx import ASGITransport, AsyncClient

from app.config.enums.document_status import DocumentProcessingStatus
from database.postgres.crud.cv import (
    CandidateDocumentRepository,
    CandidateDocumentChunkRepository,
    CandidateExperienceRepository,
    CandidateLanguageRepository,
    CandidateProfileRepository,
    CandidateRepository,
    CandidateSkillRepository,
)


def build_docx_bytes(text: str) -> bytes:
    document_xml = f"""
    <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
      <w:body>
        <w:p><w:r><w:t>{text}</w:t></w:r></w:p>
      </w:body>
    </w:document>
    """.strip().encode()

    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<?xml version='1.0' encoding='UTF-8'?>")
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


class FakeVectorEmbeddings:
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

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(text) for text in texts]

    async def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        normalized = text.lower()
        return [float(normalized.count(token)) for token in self.TOKENS]


class FakeQdrant:
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, dict]] = {}
        self.distance_metric = "cosine"

    async def create_collection(
        self,
        collection_name: str,
        vector_size: int,
        metadata: dict | None = None,
    ) -> None:
        self.collections.setdefault(collection_name, {})

    async def delete_vectors_by_document_id(
        self,
        collection_name: str,
        document_id: str,
    ) -> None:
        collection = self.collections.setdefault(collection_name, {})
        for point_id in [
            key
            for key, value in collection.items()
            if value["payload"].get("document_id") == document_id
        ]:
            collection.pop(point_id, None)

    async def upsert_points(self, collection_name: str, points: list[dict]) -> None:
        collection = self.collections.setdefault(collection_name, {})
        for point in points:
            collection[point["id"]] = {
                "vector": point["vector"],
                "payload": point["payload"],
            }

    async def delete_points_by_ids(self, collection_name: str, point_ids: list[str]) -> None:
        collection = self.collections.setdefault(collection_name, {})
        for point_id in point_ids:
            collection.pop(point_id, None)

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

    async def get_collection_distance_metric(self, collection_name: str) -> str | None:
        self.collections.setdefault(collection_name, {})
        return self.distance_metric


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return numerator / (left_norm * right_norm)


@pytest.fixture
def mock_unstructured_loader(monkeypatch):
    from app.service.loaders.unstructured import unstructured_loader

    class FakeUnstructuredLoader:
        def __init__(self, contents):
            self.contents = contents

        async def load(self):
            return [SimpleNamespace(page_content="Jane Doe Python Engineer")]

    monkeypatch.setattr(
        unstructured_loader,
        "UnstructuredLoader",
        FakeUnstructuredLoader,
    )


@pytest.fixture
def mock_entity_extraction_client(monkeypatch):
    from app.service.cv.entity_extraction import service as extraction_service

    class FakeEntityClient:
        def __init__(self, *args, **kwargs):
            self.model = "fake-entity-model"

        async def extract_entities(self, raw_text: str):
            from app.models.entity_extraction import CVEntityExtractionLLMOutput

            return CVEntityExtractionLLMOutput.model_validate(
                {
                    "profile": {
                        "full_name": "Jane Doe",
                        "headline": "Senior Backend Engineer",
                        "current_title_raw": "Senior Python Developer",
                        "confidence": 0.9,
                    },
                    "languages": [
                        {
                            "language_raw": "English",
                            "proficiency_raw": "Advanced",
                            "confidence": 0.88,
                        }
                    ],
                    "experiences": [
                        {
                            "company_name_raw": "Example Inc",
                            "job_title_raw": "Senior Python Developer",
                            "start_date": "2021-01-01",
                            "is_current": True,
                            "technologies_text": "Python, FastAPI, PostgreSQL",
                            "confidence": 0.9,
                        }
                    ],
                    "skills": [
                        {
                            "raw_skill": "Python3",
                            "source_type": "explicit",
                            "confidence": 0.95,
                        }
                    ],
                    "education": [],
                    "certifications": [],
                }
            )

    monkeypatch.setattr(
        extraction_service,
        "CVEntityExtractionLLMClient",
        FakeEntityClient,
    )


@pytest.fixture
def mock_vector_embedding_service(monkeypatch):
    from app.service.search import candidate_vector_indexing as vector_indexing_module

    class FakeEmbeddingService:
        def __init__(self):
            self.model_version = "fake-embeddings-v1"
            self.embeddings = FakeVectorEmbeddings()

        async def embed_texts(self, texts: list[str]) -> list[list[float]]:
            return await self.embeddings.embed_texts(texts)

    monkeypatch.setattr(
        vector_indexing_module,
        "CandidateEmbeddingService",
        FakeEmbeddingService,
    )


@pytest.fixture
def mock_job_search_preparation_clients(monkeypatch):
    from app.service.job_search import service as job_service

    class FakeJobLLMClient:
        def __init__(self, *args, **kwargs):
            self.model = "fake-job-model"

        async def extract_requirements(self, raw_text: str):
            from app.models.job_search import JobSearchExtractionLLMOutput

            return JobSearchExtractionLLMOutput.model_validate(
                {
                    "title_raw": "Senior Python Backend Engineer",
                    "seniority_normalized": "senior",
                    "location_raw": "Milan, Italy",
                    "remote_policies": ["Hybrid", "Remote"],
                    "required_languages": [
                        {
                            "language_normalized": "English",
                            "min_proficiency_normalized": "Advanced",
                            "required": True,
                        }
                    ],
                    "required_skills": [
                        {
                            "raw_skill": "Python 3",
                            "source_type": "explicit",
                            "confidence": 0.95,
                        },
                        {
                            "raw_skill": "Postgres",
                            "source_type": "explicit",
                            "confidence": 0.92,
                        },
                    ],
                    "optional_skills": [
                        {
                            "raw_skill": "Fast API",
                            "source_type": "explicit",
                            "confidence": 0.82,
                        }
                    ],
                    "domains": ["FinTech"],
                    "min_years_experience": 5,
                    "responsibilities_summary": "Build backend APIs.",
                    "extraction_confidence": 0.9,
                }
            )

    class FakeSkillNormalizer:
        async def normalize_skill(self, raw_skill: str | None):
            from app.models.skill_normalization import HHSkillNormalizationResult

            mapping = {
                "Python 3": "Python",
                "Postgres": "PostgreSQL",
                "Fast API": "FastAPI",
            }
            return HHSkillNormalizationResult(
                raw_skill=raw_skill or "",
                normalized_skill_text=mapping.get(raw_skill or "", raw_skill or ""),
                normalized_skill_external_id=12,
                match_type="exact",
                confidence=0.95,
            )

    monkeypatch.setattr(job_service, "JobSearchPreparationLLMClient", FakeJobLLMClient)
    monkeypatch.setattr(job_service, "HHSkillNormalizerService", FakeSkillNormalizer)


@pytest.mark.asyncio
async def test_upload_cv_happy_path(
    app,
    mock_unstructured_loader,
    mock_entity_extraction_client,
    mock_vector_embedding_service,
):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/rag/ingest_file",
            files={
                "file": (
                    "resume.docx",
                    build_docx_bytes("Jane Doe Python Engineer"),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            data={
                "candidate_external_id": "cand-001",
                "candidate_full_name": "Jane Doe",
                "candidate_email": "jane@example.com",
            },
        )

        assert response.status_code == 202, response.text
        payload = response.json()
        assert payload["status"] == "stored"
        assert payload["pipeline_status_url"] == f"/rag/file/{payload['document_id']}/pipeline-status"
        document_id = payload["document_id"]

        status_response = await client.get(f"/rag/file/{document_id}")
        assert status_response.status_code == 200, status_response.text
        status_payload = status_response.json()
        assert status_payload["processing_status"] == "ready"
        assert status_payload["text_available"] is True
        assert status_payload["extractor_name"] == "unstructured"
        assert status_payload["extracted_char_count"] > 0

        pipeline_response = await client.get(f"/rag/file/{document_id}/pipeline-status")
        assert pipeline_response.status_code == 200, pipeline_response.text
        pipeline_payload = pipeline_response.json()
        assert pipeline_payload["is_terminal"] is True
        assert pipeline_payload["current_stage"] == "completed"
        assert pipeline_payload["raw_text_extraction"]["status"] == "completed"
        assert pipeline_payload["entity_extraction"]["status"] == "completed"
        assert pipeline_payload["vector_indexing"]["status"] == "completed"


@pytest.mark.asyncio
async def test_upload_duplicate_cv_returns_conflict(
    app,
    mock_unstructured_loader,
    mock_entity_extraction_client,
    mock_vector_embedding_service,
):
    docx = build_docx_bytes("Same Resume")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first_response = await client.post(
            "/rag/ingest_file",
            files={
                "file": (
                    "resume.docx",
                    docx,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            data={"candidate_external_id": "cand-dup"},
        )
        assert first_response.status_code == 202, first_response.text

        second_response = await client.post(
            "/rag/ingest_file",
            files={
                "file": (
                    "resume-copy.docx",
                    docx,
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            data={"candidate_external_id": "cand-dup"},
        )
        assert second_response.status_code == 409, second_response.text


@pytest.mark.asyncio
async def test_upload_unsupported_extension_returns_415(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/rag/ingest_file",
            files={"file": ("resume.txt", b"plain text", "text/plain")},
        )
        assert response.status_code == 415, response.text


@pytest.mark.asyncio
async def test_get_unknown_document_returns_404(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/rag/file/does-not-exist")
        assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_extract_entities_and_read_result(
    app,
    mock_unstructured_loader,
    mock_entity_extraction_client,
    mock_vector_embedding_service,
):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        upload_response = await client.post(
            "/rag/ingest_file",
            files={
                "file": (
                    "resume.docx",
                    build_docx_bytes("Jane Doe Python Engineer"),
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                )
            },
            data={"candidate_external_id": "cand-entities"},
        )
        assert upload_response.status_code == 202, upload_response.text
        document_id = upload_response.json()["document_id"]

        extract_response = await client.post(f"/rag/file/{document_id}/extract-entities")
        assert extract_response.status_code == 200, extract_response.text
        extract_payload = extract_response.json()
        assert extract_payload["status"] == "completed"

        entities_response = await client.get(f"/rag/file/{document_id}/entities")
        assert entities_response.status_code == 200, entities_response.text
        entities_payload = entities_response.json()
        assert entities_payload["profile"]["seniority_normalized"] == "senior"
        assert entities_payload["languages"][0]["language_normalized"] == "English"
        assert entities_payload["skills"][0]["normalized_skill"] == "python"


@pytest.mark.asyncio
async def test_index_vectors_happy_path(app, db_sessionmaker, monkeypatch):
    from app.service.search import candidate_vector_indexing as vector_indexing_module

    class FakeEmbeddingService:
        def __init__(self):
            self.model_version = "fake-embeddings-v1"
            self.embeddings = FakeVectorEmbeddings()

        async def embed_texts(self, texts: list[str]) -> list[list[float]]:
            return await self.embeddings.embed_texts(texts)

    app.state.qdrant = FakeQdrant()
    monkeypatch.setattr(
        vector_indexing_module,
        "CandidateEmbeddingService",
        FakeEmbeddingService,
    )

    async with db_sessionmaker() as session:
        candidates = CandidateRepository(session)
        documents = CandidateDocumentRepository(session)
        experiences = CandidateExperienceRepository(session)
        profiles = CandidateProfileRepository(session)
        skills = CandidateSkillRepository(session)
        languages = CandidateLanguageRepository(session)

        candidate = await candidates.create(
            external_id="cand-index-api",
            full_name="Jane Doe",
            email="jane@example.com",
        )
        document = await documents.create(
            candidate_id=candidate.candidate_id,
            original_filename="resume.docx",
            file_extension="docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=123,
            checksum_sha256="index-api-checksum",
            processing_status=DocumentProcessingStatus.RAW_TEXT_READY,
        )
        await profiles.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            full_name="Jane Doe",
            email="jane@example.com",
            headline="Senior Backend Engineer",
            summary="Backend engineer focused on Python and fintech APIs.",
            current_title_normalized="backend_engineer",
            seniority_normalized="senior",
            total_experience_months=72,
            location_raw="Milan",
        )
        await skills.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            raw_skill="Python",
            normalized_skill="python",
            skill_category="programming_language",
            source_type="explicit",
            confidence=0.95,
        )
        await skills.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            raw_skill="FastAPI",
            normalized_skill="fastapi",
            skill_category="framework",
            source_type="explicit",
            confidence=0.9,
        )
        await languages.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            language_raw="English",
            language_normalized="English",
            proficiency_raw="Advanced",
            proficiency_normalized="professional",
            confidence=0.9,
        )
        await experiences.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            position_order=1,
            company_name_raw="Example Inc",
            job_title_raw="Senior Backend Engineer",
            job_title_normalized="backend_engineer",
            responsibilities_text="Built fintech APIs",
            technologies_text="Python, FastAPI",
            domain_hint="fintech",
            is_current=True,
            confidence=0.9,
        )
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(f"/rag/file/{document.document_id}/index-vectors")

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["document_id"] == document.document_id
        assert payload["candidate_id"] == candidate.candidate_id
        assert payload["status"] == "completed"
        assert payload["chunk_count"] == 3

    async with db_sessionmaker() as session:
        chunks = await CandidateDocumentChunkRepository(session).list_by_document_id(
            document.document_id
        )
        stored_document = await CandidateDocumentRepository(session).get_plain_by_id(
            document.document_id
        )
        assert len(chunks) == 3
        assert all(chunk.embedding_status == "indexed" for chunk in chunks)
        assert stored_document is not None
        assert stored_document.indexing_status == "indexed"


@pytest.mark.asyncio
async def test_vector_debug_search_returns_raw_hits(app, db_sessionmaker, monkeypatch):
    from app.service.search import candidate_vector_indexing as vector_indexing_module
    from app.service.search import candidate_vector_search as vector_search_module

    class FakeEmbeddingService:
        def __init__(self):
            self.model_version = "fake-embeddings-v1"
            self.embeddings = FakeVectorEmbeddings()

        async def embed_texts(self, texts: list[str]) -> list[list[float]]:
            return await self.embeddings.embed_texts(texts)

        async def embed_query(self, text: str) -> list[float]:
            return await self.embeddings.embed_query(text)

    app.state.qdrant = FakeQdrant()
    monkeypatch.setattr(
        vector_indexing_module,
        "CandidateEmbeddingService",
        FakeEmbeddingService,
    )
    monkeypatch.setattr(
        vector_search_module,
        "CandidateEmbeddingService",
        FakeEmbeddingService,
    )

    async with db_sessionmaker() as session:
        candidates = CandidateRepository(session)
        documents = CandidateDocumentRepository(session)
        experiences = CandidateExperienceRepository(session)
        profiles = CandidateProfileRepository(session)
        skills = CandidateSkillRepository(session)

        candidate = await candidates.create(
            external_id="cand-vector-debug",
            full_name="Jane Doe",
            email="jane@example.com",
        )
        document = await documents.create(
            candidate_id=candidate.candidate_id,
            original_filename="resume.docx",
            file_extension="docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=123,
            checksum_sha256="vector-debug-checksum",
            processing_status=DocumentProcessingStatus.RAW_TEXT_READY,
        )
        await profiles.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            full_name="Jane Doe",
            headline="Senior Backend Engineer",
            summary="Backend engineer focused on Python and fintech APIs.",
            current_title_normalized="backend_engineer",
            seniority_normalized="senior",
            total_experience_months=72,
            location_raw="Milan",
        )
        await skills.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            raw_skill="Python",
            normalized_skill="python",
            skill_category="programming_language",
            source_type="explicit",
            confidence=0.95,
        )
        await experiences.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            position_order=1,
            company_name_raw="Example Inc",
            job_title_raw="Senior Backend Engineer",
            job_title_normalized="backend_engineer",
            responsibilities_text="Built fintech APIs",
            technologies_text="Python, FastAPI",
            domain_hint="fintech",
            is_current=True,
            confidence=0.9,
        )
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        index_response = await client.post(f"/rag/file/{document.document_id}/index-vectors")
        assert index_response.status_code == 200, index_response.text

        response = await client.post(
            "/rag/search/vector-debug",
            json={
                "query_text": "senior python backend engineer",
            },
        )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["query_text"] == "senior python backend engineer"
    assert payload["vector_dimension"] == len(FakeVectorEmbeddings.TOKENS)
    assert payload["distance_metric"] == "cosine"
    assert payload["collection_name"] == "candidate_chunks"
    assert "query_vector" not in payload
    assert len(payload["hits"]) >= 1
    assert payload["hits"][0]["candidate_id"] == candidate.candidate_id
    assert payload["hits"][0]["document_id"] == document.document_id
    assert payload["hits"][0]["chunk_type"] in {
        "role_profile",
        "experience_role",
        "skills_profile",
    }
    assert isinstance(payload["hits"][0]["score"], float)


@pytest.mark.asyncio
async def test_index_vectors_returns_503_when_qdrant_is_not_configured(
    app,
    db_sessionmaker,
):
    app.state.qdrant = None
    async with db_sessionmaker() as session:
        candidates = CandidateRepository(session)
        documents = CandidateDocumentRepository(session)

        candidate = await candidates.create(
            external_id="cand-index-no-qdrant",
            full_name="Jane Doe",
            email="jane@example.com",
        )
        document = await documents.create(
            candidate_id=candidate.candidate_id,
            original_filename="resume.docx",
            file_extension="docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=123,
            checksum_sha256="index-no-qdrant-checksum",
            processing_status=DocumentProcessingStatus.RAW_TEXT_READY,
        )
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(f"/rag/file/{document.document_id}/index-vectors")

        assert response.status_code == 503, response.text
        assert response.json()["detail"] == "Qdrant is not configured"


@pytest.mark.asyncio
async def test_search_rule_based_candidates(app, db_sessionmaker):
    async with db_sessionmaker() as session:
        candidates = CandidateRepository(session)
        documents = CandidateDocumentRepository(session)
        experiences = CandidateExperienceRepository(session)
        profiles = CandidateProfileRepository(session)
        skills = CandidateSkillRepository(session)
        languages = CandidateLanguageRepository(session)

        candidate = await candidates.create(
            external_id="cand-search-api",
            full_name="Jane Doe",
            email="jane@example.com",
        )
        document = await documents.create(
            candidate_id=candidate.candidate_id,
            original_filename="resume.docx",
            file_extension="docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=123,
            checksum_sha256="search-api-checksum",
            processing_status=DocumentProcessingStatus.RAW_TEXT_READY,
        )
        await documents.update_storage(
            document,
            bucket=app.state.cv_storage.bucket_name,
            key=f"cv/originals/{document.document_id}.docx",
            processing_status=DocumentProcessingStatus.STORED,
        )
        await profiles.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            full_name="Jane Doe",
            email="jane@example.com",
            current_title_normalized="backend_engineer",
            seniority_normalized="senior",
            total_experience_months=72,
            location_raw="Milan",
        )
        await skills.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            raw_skill="Python",
            normalized_skill="python",
            skill_category="programming_language",
            source_type="explicit",
            confidence=0.95,
        )
        await languages.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            language_raw="English",
            language_normalized="English",
            proficiency_raw="Advanced",
            proficiency_normalized="professional",
            confidence=0.9,
        )
        await experiences.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            position_order=1,
            company_name_raw="Example Inc",
            job_title_raw="Senior Backend Engineer",
            job_title_normalized="backend_engineer",
            domain_hint="fintech",
            confidence=0.9,
        )
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/rag/search?search_strategy=rule_based",
            json={
                "include_skills": ["python"],
                "seniority_normalized": ["senior"],
                "languages": [
                    {
                        "language_normalized": "English",
                        "min_proficiency_normalized": "professional",
                    }
                ],
                "sort_by": "full_name",
                "sort_order": "asc",
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["total"] == 1
        assert payload["items"][0]["full_name"] == "Jane Doe"
        assert (
            payload["items"][0]["resume_download_url"]
            == f"https://fake-s3.local/{app.state.cv_storage.bucket_name}/cv/originals/{document.document_id}.docx?expires_in=3600"
        )
        assert payload["items"][0]["match_metadata"]["matched_skills"] == ["python"]
        assert payload["items"][0]["match_metadata"]["matched_languages"] == [
            "English"
        ]


@pytest.mark.asyncio
async def test_skill_autocomplete_returns_hh_suggestions(app, monkeypatch):
    from app.models.skill_normalization import HHSkillSuggestion
    from app.routers.rag import rag as rag_router

    class FakeSkillNormalizerService:
        async def suggest_skills(self, raw_skill: str | None):
            assert raw_skill == "py"
            return [
                HHSkillSuggestion(id=1, text="Python"),
                HHSkillSuggestion(id=2, text="PyTorch"),
            ]

    monkeypatch.setattr(
        rag_router,
        "HHSkillNormalizerService",
        FakeSkillNormalizerService,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/rag/skills/autocomplete", params={"q": "py"})

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload == [
            {"id": 1, "text": "Python"},
            {"id": 2, "text": "PyTorch"},
        ]


@pytest.mark.asyncio
async def test_profession_autocomplete_returns_hh_suggestions(app, monkeypatch):
    from app.models.work_normalization import HHWorkSuggestion
    from app.routers.rag import rag as rag_router

    class FakeWorkNormalizerService:
        async def suggest_works(self, raw_work: str | None):
            assert raw_work == "data"
            return [
                HHWorkSuggestion(id=1, text="Data Engineer"),
                HHWorkSuggestion(id=2, text="Data Analyst"),
            ]

    monkeypatch.setattr(
        rag_router,
        "HHWorkNormalizerService",
        FakeWorkNormalizerService,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/rag/professions/autocomplete", params={"q": "data"})

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload == [
            {"id": 1, "text": "Data Engineer"},
            {"id": 2, "text": "Data Analyst"},
        ]


@pytest.mark.asyncio
async def test_search_invalid_strategy_returns_422(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/rag/search?search_strategy=bogus",
            json={},
        )

        assert response.status_code == 422, response.text


@pytest.mark.asyncio
async def test_search_hybrid_uses_rule_shortlist_then_vector_rerank(
    app,
    db_sessionmaker,
    monkeypatch,
):
    from app.models.candidate_search import CandidateSearchResult, CandidateSearchResultItem
    from app.routers.rag import rag as rag_router

    async with db_sessionmaker() as session:
        candidates = CandidateRepository(session)
        documents = CandidateDocumentRepository(session)
        profiles = CandidateProfileRepository(session)
        skills = CandidateSkillRepository(session)
        languages = CandidateLanguageRepository(session)

        candidate = await candidates.create(
            external_id="cand-hybrid-api",
            full_name="Jane Doe",
            email="jane@example.com",
        )
        document = await documents.create(
            candidate_id=candidate.candidate_id,
            original_filename="resume.docx",
            file_extension="docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=123,
            checksum_sha256="hybrid-api-checksum",
            processing_status=DocumentProcessingStatus.RAW_TEXT_READY,
        )
        await profiles.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            full_name="Jane Doe",
            email="jane@example.com",
            current_title_normalized="backend_engineer",
            seniority_normalized="senior",
            total_experience_months=72,
            location_raw="Milan",
        )
        await skills.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            raw_skill="Python",
            normalized_skill="python",
            skill_category="programming_language",
            source_type="explicit",
            confidence=0.95,
        )
        await languages.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            language_raw="English",
            language_normalized="English",
            proficiency_raw="Advanced",
            proficiency_normalized="professional",
            confidence=0.9,
        )
        await session.commit()

    captured = {}

    class FakeVectorSearchService:
        def __init__(self, session, qdrant):
            self.session = session
            self.qdrant = qdrant

        async def search(self, filters):
            captured["candidate_ids"] = filters.candidate_ids
            return CandidateSearchResult(
                total=1,
                items=[
                    CandidateSearchResultItem(
                        candidate_id=candidate.candidate_id,
                        document_id=document.document_id,
                        full_name="Jane Doe",
                        score=0.91,
                        matched_chunk_type="role_profile",
                        matched_chunk_text_preview="Python backend engineer",
                    )
                ],
                applied_filters=filters,
            )

    monkeypatch.setattr(
        rag_router,
        "CandidateVectorSearchService",
        FakeVectorSearchService,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/rag/search?search_strategy=hybrid",
            json={
                "query_text": "senior python backend engineer",
                "include_skills": ["python"],
                "seniority_normalized": ["senior"],
                "languages": [
                    {
                        "language_normalized": "English",
                        "min_proficiency_normalized": "professional",
                    }
                ],
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert captured["candidate_ids"] == [candidate.candidate_id]
        assert payload["total"] == 1
        assert payload["items"][0]["score"] == 0.91
        assert payload["items"][0]["match_metadata"]["matched_skills"] == ["python"]


@pytest.mark.asyncio
async def test_search_hybrid_uses_profession_filters_without_query_text(
    app,
    db_sessionmaker,
    monkeypatch,
):
    from app.models.candidate_search import CandidateSearchResult, CandidateSearchResultItem
    from app.routers.rag import rag as rag_router

    async with db_sessionmaker() as session:
        candidates = CandidateRepository(session)
        documents = CandidateDocumentRepository(session)
        profiles = CandidateProfileRepository(session)

        candidate = await candidates.create(
            external_id="cand-hybrid-profession-api",
            full_name="Jane Doe",
            email="jane@example.com",
        )
        document = await documents.create(
            candidate_id=candidate.candidate_id,
            original_filename="resume.docx",
            file_extension="docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=123,
            checksum_sha256="hybrid-profession-api-checksum",
            processing_status=DocumentProcessingStatus.RAW_TEXT_READY,
        )
        await profiles.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            full_name="Jane Doe",
            email="jane@example.com",
            current_title_normalized="backend_engineer",
            seniority_normalized="senior",
            total_experience_months=72,
            location_raw="Milan",
        )
        await session.commit()

    captured = {}

    class FakeVectorSearchService:
        def __init__(self, session, qdrant):
            self.session = session
            self.qdrant = qdrant

        async def search(self, filters):
            captured["current_title_normalized"] = filters.current_title_normalized
            return CandidateSearchResult(
                total=1,
                items=[
                    CandidateSearchResultItem(
                        candidate_id=candidate.candidate_id,
                        document_id=document.document_id,
                        full_name="Jane Doe",
                        score=0.88,
                        matched_chunk_type="role_profile",
                        matched_chunk_text_preview="Backend engineer",
                    )
                ],
                applied_filters=filters,
            )

    monkeypatch.setattr(
        rag_router,
        "CandidateVectorSearchService",
        FakeVectorSearchService,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/rag/search?search_strategy=hybrid",
            json={
                "current_title_normalized": ["backend_engineer"],
                "seniority_normalized": ["senior"],
            },
        )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert captured["current_title_normalized"] == ["backend_engineer"]
        assert payload["total"] == 1
        assert payload["items"][0]["score"] == 0.88


@pytest.mark.asyncio
async def test_prepare_job_and_read_result(app, mock_job_search_preparation_clients):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        prepare_response = await client.post(
            "/rag/jobs/prepare",
            json={
                "job_id": "job-api-001",
                "raw_text": (
                    "Senior Python Backend Engineer\n"
                    "Must have Python and Postgres\n"
                    "Nice to have Fast API\n"
                    "English Advanced\n"
                ),
            },
        )

        assert prepare_response.status_code == 200, prepare_response.text
        payload = prepare_response.json()
        assert payload["job_id"] == "job-api-001"
        assert payload["current_title_normalized"] == ["backend_engineer"]
        assert payload["remote_policies"] == ["hybrid", "remote"]
        assert payload["include_skills"] == ["python", "postgresql"]
        assert payload["domains"] == ["fintech"]
        assert payload["query_text"]
        assert payload["processing_status"] == "completed"

        get_response = await client.get("/rag/jobs/job-api-001")
        assert get_response.status_code == 200, get_response.text
        get_payload = get_response.json()
        assert get_payload["job_id"] == "job-api-001"
        assert get_payload["optional_skills"] == ["fastapi"]


@pytest.mark.asyncio
async def test_prepared_job_payload_can_be_sent_directly_to_search(
    app,
    db_sessionmaker,
    mock_job_search_preparation_clients,
):
    async with db_sessionmaker() as session:
        candidates = CandidateRepository(session)
        documents = CandidateDocumentRepository(session)
        experiences = CandidateExperienceRepository(session)
        profiles = CandidateProfileRepository(session)
        skills = CandidateSkillRepository(session)
        languages = CandidateLanguageRepository(session)

        candidate = await candidates.create(
            external_id="cand-job-search-compat",
            full_name="Jane Doe",
            email="jane@example.com",
        )
        document = await documents.create(
            candidate_id=candidate.candidate_id,
            original_filename="resume.docx",
            file_extension="docx",
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            size_bytes=123,
            checksum_sha256="job-search-compat",
            processing_status=DocumentProcessingStatus.RAW_TEXT_READY,
        )
        await profiles.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            full_name="Jane Doe",
            email="jane@example.com",
            remote_policies_json='["remote","hybrid"]',
            current_title_normalized="backend_engineer",
            seniority_normalized="senior",
            total_experience_months=72,
            location_raw="milan, italy",
        )
        await skills.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            raw_skill="Python",
            normalized_skill="python",
            skill_category="programming_language",
            source_type="explicit",
            confidence=0.95,
        )
        await skills.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            raw_skill="Postgres",
            normalized_skill="postgresql",
            skill_category="database",
            source_type="explicit",
            confidence=0.95,
        )
        await languages.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            language_raw="English",
            language_normalized="English",
            proficiency_raw="Advanced",
            proficiency_normalized="professional",
            confidence=0.9,
        )
        await experiences.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            position_order=1,
            company_name_raw="Example Inc",
            job_title_raw="Senior Backend Engineer",
            job_title_normalized="backend_engineer",
            domain_hint="fintech",
            confidence=0.9,
        )
        await session.commit()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        prepared_response = await client.post(
            "/rag/jobs/prepare",
            json={
                "job_id": "job-api-search-compat",
                "raw_text": (
                    "Senior Python Backend Engineer\n"
                    "Must have Python and Postgres\n"
                    "English Advanced\n"
                ),
            },
        )
        assert prepared_response.status_code == 200, prepared_response.text
        prepared_payload = prepared_response.json()

        search_response = await client.post(
            "/rag/search?search_strategy=rule_based",
            json=prepared_payload,
        )
        assert search_response.status_code == 200, search_response.text
        search_payload = search_response.json()
        assert search_payload["total"] == 1
        assert search_payload["items"][0]["full_name"] == "Jane Doe"
