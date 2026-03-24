import pytest

from app.config.enums.processing_run_status import ProcessingRunStatus
from app.config.enums.processing_stage import ProcessingStage
from app.models.job_search import JobSearchExtractionLLMOutput, JobSearchPreparationRequest
from app.service.job_search.graph import JobSearchPreparationError
from app.service.job_search.service import JobSearchPreparationService
from database.postgres.crud.cv import (
    JobProcessingRunRepository,
    JobSearchProfileRepository,
)


class FakeJobLLMClient:
    def __init__(self, payload: dict | None = None, error: Exception | None = None):
        self.payload = payload or {}
        self.error = error
        self.model = "fake-job-llm-model"

    async def extract_requirements(self, raw_text: str) -> JobSearchExtractionLLMOutput:
        if self.error:
            raise self.error
        return JobSearchExtractionLLMOutput.model_validate(self.payload)


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
            normalized_skill_external_id=101,
            match_type="exact",
            confidence=0.95,
        )


def _job_payload() -> dict:
    return {
        "title_raw": "Senior Python Backend Engineer",
        "seniority_normalized": "senior",
        "location_raw": "Milan, Italy",
        "remote_policies": ["Hybrid", "Remote"],
        "employment_type": "Full-time",
        "required_languages": [
            {
                "language_normalized": "English",
                "min_proficiency_normalized": "Advanced",
                "required": True,
            }
        ],
        "required_skills": [
            {"raw_skill": "Python 3", "source_type": "explicit", "confidence": 0.95},
            {"raw_skill": "Postgres", "source_type": "explicit", "confidence": 0.92},
        ],
        "optional_skills": [
            {"raw_skill": "Fast API", "source_type": "explicit", "confidence": 0.82}
        ],
        "domains": ["FinTech"],
        "min_years_experience": 5,
        "education_requirements": ["Bachelor's degree in Computer Science"],
        "certification_requirements": ["AWS Certified Developer"],
        "responsibilities_summary": "Build backend APIs and payment integrations.",
        "extraction_confidence": 0.87,
    }


def _project_manager_payload() -> dict:
    return {
        "title_raw": "Project Manager",
        "seniority_normalized": "manager",
        "location_raw": "Warsaw, Poland",
        "remote_policies": ["Remote"],
        "required_languages": [
            {
                "language_normalized": "English",
                "min_proficiency_normalized": "B2+",
                "required": True,
            }
        ],
        "required_skills": [
            {"raw_skill": "Agile / Scrum", "source_type": "must_have", "confidence": 0.95},
            {"raw_skill": "Project planning", "source_type": "must_have", "confidence": 0.93},
            {"raw_skill": "Risk management", "source_type": "must_have", "confidence": 0.92},
            {"raw_skill": "Resource planning", "source_type": "must_have", "confidence": 0.9},
            {"raw_skill": "Sprint planning", "source_type": "must_have", "confidence": 0.87},
            {"raw_skill": "Retrospectives", "source_type": "must_have", "confidence": 0.84},
            {"raw_skill": "Cashflow control", "source_type": "must_have", "confidence": 0.82},
            {"raw_skill": "Two-week sprints", "source_type": "must_have", "confidence": 0.8},
        ],
        "domains": ["Digital Health"],
        "min_years_experience": 3,
        "responsibilities_summary": (
            "Lead parallel delivery projects, maintain roadmaps and sprint plans, "
            "control risks and resources, and coordinate cross-functional teams."
        ),
        "extraction_confidence": 0.91,
    }


@pytest.mark.asyncio
async def test_job_search_preparation_happy_path_persists_profile(db_sessionmaker):
    async with db_sessionmaker() as session:
        service = JobSearchPreparationService(
            session,
            llm_client=FakeJobLLMClient(_job_payload()),
            skill_normalizer=FakeSkillNormalizer(),
        )

        result = await service.run(
            JobSearchPreparationRequest(
                job_id="job-001",
                raw_text=(
                    "Senior Python Backend Engineer\n"
                    "Must have Python, Postgres\n"
                    "Nice to have Fast API\n"
                    "English Advanced\n"
                ),
            )
        )

        assert result.job_id == "job-001"
        assert result.current_title_normalized == ["backend_engineer"]
        assert result.seniority_normalized == ["senior"]
        assert result.location_normalized == ["milan, italy"]
        assert result.remote_policies == ["hybrid", "remote"]
        assert result.employment_types == ["full_time"]
        assert result.min_total_experience_months == 60
        assert result.include_skills == ["python", "postgresql"]
        assert result.optional_skills == ["fastapi"]
        assert result.languages[0].language_normalized == "English"
        assert (
            result.languages[0].min_proficiency_normalized
            == "professional"
        )
        assert result.query_text is not None
        assert "Must-have skills: python, postgresql." in result.query_text
        assert (
            result.processing_status == ProcessingRunStatus.COMPLETED
        )

        profile = await JobSearchProfileRepository(session).get_by_job_id("job-001")
        assert profile is not None
        assert profile.semantic_query_text_main == result.query_text


@pytest.mark.asyncio
async def test_job_search_preparation_rerun_replaces_previous_data(db_sessionmaker):
    async with db_sessionmaker() as session:
        service = JobSearchPreparationService(
            session,
            llm_client=FakeJobLLMClient(_job_payload()),
            skill_normalizer=FakeSkillNormalizer(),
        )
        await service.run(
            JobSearchPreparationRequest(job_id="job-rerun", raw_text="Backend role")
        )

    async with db_sessionmaker() as session:
        rerun_payload = _job_payload()
        rerun_payload["required_skills"] = [
            {"raw_skill": "Python 3", "source_type": "explicit", "confidence": 0.95}
        ]
        rerun_payload["optional_skills"] = [
            {"raw_skill": "React", "source_type": "explicit", "confidence": 0.8}
        ]
        rerun_payload["domains"] = ["HealthTech"]
        service = JobSearchPreparationService(
            session,
            llm_client=FakeJobLLMClient(rerun_payload),
            skill_normalizer=FakeSkillNormalizer(),
        )
        result = await service.run(
            JobSearchPreparationRequest(job_id="job-rerun", raw_text="Backend role rerun")
        )

        assert result.include_skills == ["python"]
        assert result.optional_skills == ["react"]
        assert result.domains == ["healthtech"]


@pytest.mark.asyncio
async def test_job_search_preparation_missing_raw_text_fails_and_marks_run(db_sessionmaker):
    async with db_sessionmaker() as session:
        service = JobSearchPreparationService(
            session,
            llm_client=FakeJobLLMClient(_job_payload()),
            skill_normalizer=FakeSkillNormalizer(),
        )

        with pytest.raises(JobSearchPreparationError, match="Raw text is missing"):
            await service.run(
                JobSearchPreparationRequest(job_id="job-empty", raw_text="   ")
            )

        run = await JobProcessingRunRepository(session).get_by_job_and_stage(
            "job-empty",
            ProcessingStage.JOB_SEARCH_PREPARATION,
        )
        assert run is not None
        assert run.status == ProcessingRunStatus.FAILED


@pytest.mark.asyncio
async def test_job_search_preparation_llm_failure_marks_run_failed(db_sessionmaker):
    async with db_sessionmaker() as session:
        service = JobSearchPreparationService(
            session,
            llm_client=FakeJobLLMClient(error=RuntimeError("LLM provider unavailable")),
            skill_normalizer=FakeSkillNormalizer(),
        )

        with pytest.raises(JobSearchPreparationError, match="LLM provider unavailable"):
            await service.run(
                JobSearchPreparationRequest(
                    job_id="job-llm-fail",
                    raw_text="Senior backend engineer with Python experience",
                )
            )

        run = await JobProcessingRunRepository(session).get_by_job_and_stage(
            "job-llm-fail",
            ProcessingStage.JOB_SEARCH_PREPARATION,
        )
        assert run is not None
        assert run.status == ProcessingRunStatus.FAILED
        assert run.error_message == "LLM provider unavailable"


@pytest.mark.asyncio
async def test_job_search_preparation_demotes_pm_process_phrases_to_semantic_signals(
    db_sessionmaker,
):
    async with db_sessionmaker() as session:
        service = JobSearchPreparationService(
            session,
            llm_client=FakeJobLLMClient(_project_manager_payload()),
            skill_normalizer=FakeSkillNormalizer(),
        )

        result = await service.run(
            JobSearchPreparationRequest(
                job_id="job-pm-001",
                raw_text="Project manager role for digital health delivery",
            )
        )

        assert result.current_title_normalized == ["project_manager"]
        assert result.include_skills == [
            "agile scrum",
            "project planning",
            "risk management",
            "resource planning",
        ]
        assert result.optional_skills is None
        assert result.query_text_skills is not None
        assert "Required skills: agile scrum, project planning, risk management, resource planning." in result.query_text_skills
        assert "Delivery signals: sprint planning, retrospectives, cashflow control, two-week sprints." in result.query_text_skills
