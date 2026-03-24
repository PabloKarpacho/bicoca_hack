import pytest

from app.config.enums.processing_run_status import ProcessingRunStatus
from app.config.enums.processing_stage import ProcessingStage
from app.config.enums.document_status import DocumentProcessingStatus
from app.models.entity_extraction import CVEntityExtractionLLMOutput
from app.models.skill_normalization import HHSkillNormalizationResult, HHSkillSuggestion
from app.service.cv.entity_extraction.graph import EntityExtractionGraphError
from app.service.cv.entity_extraction.service import CandidateEntityExtractionService
from database.postgres.crud.cv import (
    CandidateDocumentRepository,
    CandidateDocumentTextRepository,
    CandidateProfileRepository,
    CandidateRepository,
    CandidateSkillRepository,
    DocumentProcessingRunRepository,
)


class FakeLLMClient:
    def __init__(self, payload: dict | None = None, error: Exception | None = None):
        self.payload = payload or {}
        self.error = error
        self.model = "fake-llm-model"

    async def extract_entities(self, raw_text: str) -> CVEntityExtractionLLMOutput:
        if self.error:
            raise self.error
        return CVEntityExtractionLLMOutput.model_validate(self.payload)


class FakeSkillNormalizer:
    def __init__(self, mode: str = "match") -> None:
        self.mode = mode

    async def normalize_skill(self, raw_skill: str | None) -> HHSkillNormalizationResult:
        if self.mode == "error":
            return HHSkillNormalizationResult(
                raw_skill=raw_skill or "",
                match_type="error",
                confidence=0.0,
                error="HH autosuggest request timed out",
            )
        mapping = {
            "Python3": "Python",
            "Python": "Python",
            "Postgres": "PostgreSQL",
            "FastAPI": "FastAPI",
            "JavaScript": "JavaScript",
        }
        normalized_text = mapping.get(raw_skill or "", raw_skill or "")
        return HHSkillNormalizationResult(
            raw_skill=raw_skill or "",
            normalized_skill_text=normalized_text,
            normalized_skill_external_id=42,
            match_type="exact",
            confidence=0.99,
            alternatives=[HHSkillSuggestion(id=42, text=normalized_text)],
        )


async def _create_document(
    session,
    *,
    raw_text: str | None,
    checksum: str = "abc123",
) -> tuple[str, str]:
    candidates = CandidateRepository(session)
    documents = CandidateDocumentRepository(session)
    texts = CandidateDocumentTextRepository(session)

    candidate = await candidates.create(
        external_id="cand-entity",
        full_name="Jane Doe",
        email="jane@example.com",
    )
    document = await documents.create(
        candidate_id=candidate.candidate_id,
        original_filename="resume.docx",
        file_extension="docx",
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=123,
        checksum_sha256=checksum,
        processing_status=DocumentProcessingStatus.RAW_TEXT_READY,
    )
    if raw_text is not None:
        await texts.upsert(document_id=document.document_id, raw_text=raw_text)
    await session.commit()
    return candidate.candidate_id, document.document_id


def _happy_payload() -> dict:
    return {
        "profile": {
            "full_name": "Jane Doe",
            "headline": "Senior Backend Engineer",
            "current_title_raw": "Senior Python Developer",
            "location_raw": "Milan, Italy",
            "remote_policies": ["Remote", "Hybrid"],
            "employment_types": ["Full-time", "Contract"],
            "summary": "Backend engineer focused on Python systems.",
            "confidence": 0.92,
        },
        "languages": [
            {
                "language_raw": "English",
                "proficiency_raw": "Full professional proficiency",
                "confidence": 0.9,
            },
            {
                "language_raw": "Italian",
                "proficiency_raw": "Native",
                "confidence": 0.98,
            },
        ],
        "experiences": [
            {
                "company_name_raw": "Example Inc",
                "job_title_raw": "Senior Python Developer",
                "start_date": "2021-01-01",
                "end_date": None,
                "is_current": True,
                "technologies_text": "Python, FastAPI, PostgreSQL",
                "responsibilities_text": "Built backend services",
                "confidence": 0.91,
            }
        ],
        "skills": [
            {
                "raw_skill": "Python3",
                "source_type": "explicit",
                "confidence": 0.95,
            },
            {
                "raw_skill": "Postgres",
                "source_type": "explicit",
                "confidence": 0.89,
            },
            {
                "raw_skill": "Python",
                "source_type": "explicit",
                "confidence": 0.8,
            },
        ],
        "education": [
            {
                "institution_raw": "Politecnico di Milano",
                "degree_raw": "MSc Computer Science",
                "end_date": "2020-01-01",
                "confidence": 0.87,
            }
        ],
        "certifications": [
            {
                "certification_name_raw": "AWS Certified Developer",
                "issuer": "Amazon",
                "issue_date": "2024-01-01",
                "confidence": 0.82,
            }
        ],
    }


@pytest.mark.asyncio
async def test_entity_extraction_happy_path_persists_entities(db_sessionmaker):
    async with db_sessionmaker() as session:
        candidate_id, document_id = await _create_document(
            session,
            raw_text=(
                "Jane Doe\nSenior Backend Engineer\njane@example.com\n"
                "English - Full professional proficiency\n"
                "Italian - Native\n"
            ),
        )

    async with db_sessionmaker() as session:
        service = CandidateEntityExtractionService(
            session,
            llm_client=FakeLLMClient(_happy_payload()),
            skill_normalizer=FakeSkillNormalizer(),
        )
        run = await service.run(document_id)
        result = await service.get_result(document_id)

        assert run.status == ProcessingRunStatus.COMPLETED
        assert run.document_id == document_id
        assert result.candidate_id == candidate_id
        assert result.profile is not None
        assert result.profile.email == "jane@example.com"
        assert result.profile.current_title_normalized == "backend_engineer"
        assert result.profile.seniority_normalized == "senior"
        assert result.profile.remote_policies == ["remote", "hybrid"]
        assert result.profile.employment_types == ["full_time", "contract"]
        assert result.profile.total_experience_months is not None
        assert {skill.normalized_skill for skill in result.skills} >= {
            "python",
            "postgresql",
            "fastapi",
        }
        python_skill = next(
            item for item in result.skills if item.normalized_skill == "python"
        )
        assert python_skill.normalization_source == "hh"
        assert python_skill.normalization_external_id == 42
        assert python_skill.normalization_status == "matched"
        assert python_skill.normalization_confidence == 0.99
        assert python_skill.normalization_metadata is not None
        assert len(result.languages) == 2
        assert result.languages[0].proficiency_normalized in {
            "fluent",
            "professional",
        }
        assert len(result.experiences) == 1
        assert result.experiences[0].job_title_normalized == "backend_engineer"
        assert len(result.education) == 1
        assert len(result.certifications) == 1
        assert result.processing_run is not None
        assert result.processing_run.processing_stage == ProcessingStage.ENTITY_EXTRACTION


@pytest.mark.asyncio
async def test_entity_extraction_rerun_replaces_previous_entities(db_sessionmaker):
    async with db_sessionmaker() as session:
        _, document_id = await _create_document(
            session,
            raw_text="Jane Doe\nSenior Python Developer",
            checksum="rerun-1",
        )

    async with db_sessionmaker() as session:
        service = CandidateEntityExtractionService(
            session,
            llm_client=FakeLLMClient(_happy_payload()),
            skill_normalizer=FakeSkillNormalizer(),
        )
        await service.run(document_id)

    async with db_sessionmaker() as session:
        rerun_payload = _happy_payload()
        rerun_payload["skills"] = [
            {
                "raw_skill": "JavaScript",
                "source_type": "explicit",
                "confidence": 0.91,
            }
        ]
        rerun_payload["languages"] = [
            {
                "language_raw": "English",
                "proficiency_raw": "Advanced",
                "confidence": 0.88,
            }
        ]
        service = CandidateEntityExtractionService(
            session,
            llm_client=FakeLLMClient(rerun_payload),
            skill_normalizer=FakeSkillNormalizer(),
        )
        await service.run(document_id)
        result = await service.get_result(document_id)

        assert {skill.normalized_skill for skill in result.skills} == {
            "javascript",
            "python",
            "fastapi",
            "postgresql",
        }
        assert len(result.languages) == 1


@pytest.mark.asyncio
async def test_entity_extraction_missing_raw_text_marks_failed(db_sessionmaker):
    async with db_sessionmaker() as session:
        _, document_id = await _create_document(session, raw_text=None, checksum="missing")

    async with db_sessionmaker() as session:
        service = CandidateEntityExtractionService(
            session,
            llm_client=FakeLLMClient(_happy_payload()),
            skill_normalizer=FakeSkillNormalizer(),
        )
        with pytest.raises(
            EntityExtractionGraphError,
            match="Raw text is missing for entity extraction",
        ):
            await service.run(document_id)

        run = await DocumentProcessingRunRepository(session).get_by_document_and_stage(
            document_id,
            ProcessingStage.ENTITY_EXTRACTION,
        )
        assert run is not None
        assert run.status == ProcessingRunStatus.FAILED


@pytest.mark.asyncio
async def test_entity_extraction_failed_llm_marks_failed(db_sessionmaker):
    async with db_sessionmaker() as session:
        _, document_id = await _create_document(
            session,
            raw_text="Jane Doe\nSenior Backend Engineer",
            checksum="failed-llm",
        )

    async with db_sessionmaker() as session:
        service = CandidateEntityExtractionService(
            session,
            llm_client=FakeLLMClient(error=RuntimeError("LLM exploded")),
            skill_normalizer=FakeSkillNormalizer(),
        )
        with pytest.raises(EntityExtractionGraphError, match="LLM exploded"):
            await service.run(document_id)

        run = await DocumentProcessingRunRepository(session).get_by_document_and_stage(
            document_id,
            ProcessingStage.ENTITY_EXTRACTION,
        )
        assert run is not None
        assert run.status == ProcessingRunStatus.FAILED
        assert run.error_message == "LLM exploded"


@pytest.mark.asyncio
async def test_entity_extraction_persistence_repositories(db_sessionmaker):
    async with db_sessionmaker() as session:
        _, document_id = await _create_document(
            session,
            raw_text="Jane Doe\nSenior Backend Engineer",
            checksum="repos",
        )

    async with db_sessionmaker() as session:
        service = CandidateEntityExtractionService(
            session,
            llm_client=FakeLLMClient(_happy_payload()),
            skill_normalizer=FakeSkillNormalizer(),
        )
        await service.run(document_id)

        profile = await CandidateProfileRepository(session).get_by_document_id(document_id)
        skills = await CandidateSkillRepository(session).list_by_document_id(document_id)

        assert profile is not None
        assert profile.full_name == "Jane Doe"
        assert profile.seniority_normalized == "senior"
        assert profile.remote_policies_json == '["remote", "hybrid"]'
        assert {item.normalized_skill for item in skills} >= {
            "python",
            "postgresql",
            "fastapi",
        }
        python_skill = next(item for item in skills if item.normalized_skill == "python")
        assert python_skill.normalization_source == "hh"
        assert python_skill.normalization_external_id == 42
        assert python_skill.normalization_status == "matched"


@pytest.mark.asyncio
async def test_entity_extraction_hh_skill_failure_does_not_break_pipeline(
    db_sessionmaker,
):
    async with db_sessionmaker() as session:
        _, document_id = await _create_document(
            session,
            raw_text="Jane Doe\nSenior Backend Engineer",
            checksum="hh-error",
        )

    async with db_sessionmaker() as session:
        service = CandidateEntityExtractionService(
            session,
            llm_client=FakeLLMClient(_happy_payload()),
            skill_normalizer=FakeSkillNormalizer(mode="error"),
        )
        run = await service.run(document_id)
        result = await service.get_result(document_id)

        assert run.status == ProcessingRunStatus.COMPLETED
        assert result.skills[0].normalized_skill == "python"
        assert result.skills[0].normalization_status == "error"
        assert result.skills[0].normalization_source == "local"
