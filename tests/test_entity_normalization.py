import pytest

from app.config.enums.normalization_class import NormalizationClass
from app.config.enums.normalization_status import NormalizationStatus
from app.models.entity_extraction import JobSearchExtractionLLMOutput
from app.models.normalization import NormalizationAgentOutput
from app.service.normalization.agent_client import build_system_prompt
from app.service.normalization.job_preparation import normalize_job_search_requirements
from app.service.normalization.primitives import normalize_degree, normalize_language_level
from app.service.normalization.service import EntityNormalizationService
from app.models.work_normalization import HHWorkNormalizationResult, HHWorkSuggestion
from database.postgres.crud.cv import EntityNormalizationRepository


class FakeNormalizationAgentClient:
    def __init__(self, mapping: dict[tuple[str, str], NormalizationAgentOutput] | None = None):
        self.mapping = mapping or {}
        self.calls: list[tuple[str, str, list[str]]] = []
        self.model = "fake-normalizer-model"

    async def normalize(self, *, normalization_class, original_value, canonical_values):
        self.calls.append((normalization_class.value, original_value, canonical_values))
        return self.mapping.get(
            (normalization_class.value, original_value),
            NormalizationAgentOutput(
                normalized_value=None,
                status=NormalizationStatus.NO_MATCH,
                confidence=0.0,
                matched_existing_canonical=False,
            ),
        )


class FakeSkillNormalizer:
    def __init__(self):
        self.calls: list[str | None] = []

    async def normalize_skill(self, raw_skill: str | None):
        from app.models.skill_normalization import HHSkillNormalizationResult

        self.calls.append(raw_skill)
        mapping = {
            "Py": ("Python", 42, "exact"),
            "JS": ("JavaScript", 43, "exact"),
        }
        if raw_skill in mapping:
            text, external_id, match_type = mapping[raw_skill]
            return HHSkillNormalizationResult(
                raw_skill=raw_skill or "",
                normalized_skill_text=text,
                normalized_skill_external_id=external_id,
                match_type=match_type,
                confidence=0.99,
            )
        return HHSkillNormalizationResult(
            raw_skill=raw_skill or "",
            match_type="no_match",
            confidence=0.0,
        )


class FakeWorkNormalizer:
    def __init__(self):
        self.calls: list[str | None] = []

    async def normalize_work(self, raw_work: str | None):
        self.calls.append(raw_work)
        if raw_work == "Data":
            return HHWorkNormalizationResult(
                raw_work=raw_work or "",
                normalized_work_text="Data Engineer",
                normalized_work_external_id=77,
                match_type="top_result",
                confidence=0.83,
                alternatives=[HHWorkSuggestion(id=77, text="Data Engineer")],
            )
        return HHWorkNormalizationResult(
            raw_work=raw_work or "",
            match_type="no_match",
            confidence=0.0,
        )


def test_normalization_prompt_locks_proficiency_to_single_canonical_value():
    prompt = build_system_prompt(NormalizationClass.PROFICIENCY_LEVELS)

    assert "closed allowed set" in prompt
    assert "choose exactly one value from canonical_values" in prompt
    assert "Never invent a new proficiency level" in prompt
    assert '"Upper-Intermediate / Advanced working proficiency (B2/C1)"' in prompt
    assert "Output must never contain multiple levels" in prompt


def test_language_level_normalization_treats_b2_plus_as_professional():
    assert normalize_language_level("B2") == "professional"
    assert normalize_language_level("Upper-Intermediate") == "professional"
    assert normalize_language_level("B2+") == "professional"


def test_degree_normalization_uses_fixed_canonical_levels():
    assert normalize_degree("High School Diploma") == "secondary"
    assert normalize_degree("College Diploma") == "associate"
    assert normalize_degree("BSc Computer Science") == "bachelor"
    assert normalize_degree("MBA") == "master"
    assert normalize_degree("Doctorate in AI") == "phd"


@pytest.mark.asyncio
async def test_entity_normalization_cache_hit_uses_registry(db_sessionmaker):
    async with db_sessionmaker() as session:
        repo = EntityNormalizationRepository(session)
        await repo.upsert_normalization(
            normalization_class=NormalizationClass.LANGUAGES,
            original_value="English",
            original_value_lookup="english",
            normalized_value="English",
            normalized_value_canonical="English",
            normalization_status=NormalizationStatus.NORMALIZED,
            confidence=1.0,
            provider="seed",
            model_version=None,
            pipeline_version="seed_v1",
            metadata_json=None,
        )
        await session.commit()

        agent = FakeNormalizationAgentClient()
        service = EntityNormalizationService(
            session=session,
            agent_client=agent,
            skill_normalizer=FakeSkillNormalizer(),
        )
        result = await service.normalize(
            original_value=" English ",
            normalization_class=NormalizationClass.LANGUAGES,
        )

        assert result.was_cache_hit is True
        assert result.normalized_value == "English"
        assert agent.calls == []


@pytest.mark.asyncio
async def test_entity_normalization_cache_miss_calls_agent_and_persists(db_sessionmaker):
    async with db_sessionmaker() as session:
        agent = FakeNormalizationAgentClient(
            {
                ("languages", "Англ. яз"): NormalizationAgentOutput(
                    normalized_value="English",
                    status=NormalizationStatus.NORMALIZED,
                    confidence=0.94,
                    matched_existing_canonical=True,
                )
            }
        )
        service = EntityNormalizationService(
            session=session,
            agent_client=agent,
            skill_normalizer=FakeSkillNormalizer(),
        )

        first = await service.normalize(
            original_value="Англ. яз",
            normalization_class=NormalizationClass.LANGUAGES,
        )
        await session.commit()
        second = await service.normalize(
            original_value="Англ. яз",
            normalization_class=NormalizationClass.LANGUAGES,
        )

        assert first.was_cache_hit is False
        assert first.normalized_value == "English"
        assert second.was_cache_hit is True
        assert len(agent.calls) == 1


@pytest.mark.asyncio
async def test_entity_normalization_unrecognized_seniority_dispatches_agent(db_sessionmaker):
    async with db_sessionmaker() as session:
        agent = FakeNormalizationAgentClient(
            {
                ("seniority_levels", "Architect-level"): NormalizationAgentOutput(
                    normalized_value="lead",
                    status=NormalizationStatus.NORMALIZED,
                    confidence=0.81,
                    matched_existing_canonical=True,
                )
            }
        )
        service = EntityNormalizationService(
            session=session,
            agent_client=agent,
            skill_normalizer=FakeSkillNormalizer(),
        )

        result = await service.normalize(
            original_value="Architect-level",
            normalization_class=NormalizationClass.SENIORITY_LEVELS,
        )

        assert result.normalized_value == "lead"
        assert result.provider == "agent"
        assert len(agent.calls) == 1
        assert agent.calls[0][0] == "seniority_levels"
        assert agent.calls[0][1] == "Architect-level"


@pytest.mark.asyncio
async def test_entity_normalization_separate_classes_do_not_conflict(db_sessionmaker):
    async with db_sessionmaker() as session:
        agent = FakeNormalizationAgentClient(
            {
                ("professions", "Senior"): NormalizationAgentOutput(
                    normalized_value="senior_specialist",
                    status=NormalizationStatus.NORMALIZED,
                    confidence=0.6,
                    matched_existing_canonical=False,
                )
            }
        )
        service = EntityNormalizationService(
            session=session,
            agent_client=agent,
            skill_normalizer=FakeSkillNormalizer(),
        )

        seniority = await service.normalize(
            original_value="Senior",
            normalization_class=NormalizationClass.SENIORITY_LEVELS,
        )
        profession = await service.normalize(
            original_value="Senior",
            normalization_class=NormalizationClass.PROFESSIONS,
        )
        await session.commit()

        assert seniority.normalized_value == "senior"
        assert profession.normalized_value == "senior_specialist"
        records = await EntityNormalizationRepository(session).list_by_class(
            NormalizationClass.PROFESSIONS
        )
        assert len(records) == 1


@pytest.mark.asyncio
async def test_entity_normalization_no_match_is_persisted(db_sessionmaker):
    async with db_sessionmaker() as session:
        agent = FakeNormalizationAgentClient(
            {
                ("cities", "Atlantis"): NormalizationAgentOutput(
                    normalized_value=None,
                    status=NormalizationStatus.NO_MATCH,
                    confidence=0.12,
                    matched_existing_canonical=False,
                )
            }
        )
        service = EntityNormalizationService(
            session=session,
            agent_client=agent,
            skill_normalizer=FakeSkillNormalizer(),
        )

        result = await service.normalize(
            original_value="Atlantis",
            normalization_class=NormalizationClass.CITIES,
        )
        await session.commit()
        cached = await service.normalize(
            original_value="Atlantis",
            normalization_class=NormalizationClass.CITIES,
        )

        assert result.status == NormalizationStatus.NO_MATCH
        assert result.normalized_value is None
        assert cached.was_cache_hit is True
        assert len(agent.calls) == 1


@pytest.mark.asyncio
async def test_entity_normalization_failed_agent_is_persisted(db_sessionmaker):
    async with db_sessionmaker() as session:
        agent = FakeNormalizationAgentClient(
            {
                ("countries", "???"): NormalizationAgentOutput(
                    normalized_value=None,
                    status=NormalizationStatus.FAILED,
                    confidence=0.0,
                    matched_existing_canonical=False,
                )
            }
        )
        service = EntityNormalizationService(
            session=session,
            agent_client=agent,
            skill_normalizer=FakeSkillNormalizer(),
        )

        result = await service.normalize(
            original_value="???",
            normalization_class=NormalizationClass.COUNTRIES,
        )

        assert result.status == NormalizationStatus.FAILED
        assert result.normalized_value is None


@pytest.mark.asyncio
async def test_entity_normalization_canonical_values_merge_registry_and_seeds(db_sessionmaker):
    async with db_sessionmaker() as session:
        repo = EntityNormalizationRepository(session)
        await repo.upsert_normalization(
            normalization_class=NormalizationClass.CITIES,
            original_value="Milano",
            original_value_lookup="milano",
            normalized_value="Milan",
            normalized_value_canonical="Milan",
            normalization_status=NormalizationStatus.NORMALIZED,
            confidence=0.99,
            provider="seed",
            model_version=None,
            pipeline_version="seed_v1",
            metadata_json=None,
        )
        await session.commit()

        service = EntityNormalizationService(
            session=session,
            agent_client=FakeNormalizationAgentClient(),
            skill_normalizer=FakeSkillNormalizer(),
        )
        canonical = await service.list_canonical_values(NormalizationClass.CITIES)

        assert "Milan" in canonical
        assert "Berlin" in canonical


@pytest.mark.asyncio
async def test_entity_normalization_supports_remote_policy_employment_and_education(
    db_sessionmaker,
):
    async with db_sessionmaker() as session:
        service = EntityNormalizationService(
            session=session,
            agent_client=FakeNormalizationAgentClient(),
            skill_normalizer=FakeSkillNormalizer(),
        )

        remote_policy = await service.normalize(
            original_value="Hybrid",
            normalization_class=NormalizationClass.REMOTE_POLICY,
        )
        employment_type = await service.normalize(
            original_value="Full-time",
            normalization_class=NormalizationClass.EMPLOYMENT_TYPE,
        )
        education = await service.normalize(
            original_value="MSc Computer Science",
            normalization_class=NormalizationClass.EDUCATION,
        )

        assert remote_policy.normalized_value == "hybrid"
        assert employment_type.normalized_value == "full_time"
        assert education.normalized_value == "master"


@pytest.mark.asyncio
async def test_entity_normalization_skill_uses_hh_before_agent(db_sessionmaker):
    async with db_sessionmaker() as session:
        agent = FakeNormalizationAgentClient(
            {
                ("skills", "Py"): NormalizationAgentOutput(
                    normalized_value="python_agent",
                    status=NormalizationStatus.NORMALIZED,
                    confidence=0.5,
                    matched_existing_canonical=False,
                )
            }
        )
        hh = FakeSkillNormalizer()
        service = EntityNormalizationService(
            session=session,
            agent_client=agent,
            skill_normalizer=hh,
        )

        result = await service.normalize(
            original_value="Py",
            normalization_class=NormalizationClass.SKILLS,
        )

        assert result.normalized_value == "python"
        assert result.provider == "hh"
        assert agent.calls == []
        assert hh.calls == ["Py"]


@pytest.mark.asyncio
async def test_entity_normalization_profession_uses_hh_before_agent(db_sessionmaker):
    async with db_sessionmaker() as session:
        agent = FakeNormalizationAgentClient(
            {
                ("professions", "Data"): NormalizationAgentOutput(
                    normalized_value="data_scientist",
                    status=NormalizationStatus.NORMALIZED,
                    confidence=0.5,
                    matched_existing_canonical=False,
                )
            }
        )
        work = FakeWorkNormalizer()
        service = EntityNormalizationService(
            session=session,
            agent_client=agent,
            skill_normalizer=FakeSkillNormalizer(),
            work_normalizer=work,
        )

        result = await service.normalize(
            original_value="Data",
            normalization_class=NormalizationClass.PROFESSIONS,
        )

        assert result.normalized_value == "data_engineer"
        assert result.provider == "hh"
        assert agent.calls == []
        assert work.calls == ["Data"]


@pytest.mark.asyncio
async def test_entity_normalization_upsert_behavior_is_unique_per_class_and_lookup(db_sessionmaker):
    async with db_sessionmaker() as session:
        repo = EntityNormalizationRepository(session)
        await repo.upsert_normalization(
            normalization_class=NormalizationClass.SKILLS,
            original_value="Py",
            original_value_lookup="py",
            normalized_value="python",
            normalized_value_canonical="python",
            normalization_status=NormalizationStatus.NORMALIZED,
            confidence=0.9,
            provider="hh",
            model_version=None,
            pipeline_version="v1",
            metadata_json=None,
        )
        await repo.upsert_normalization(
            normalization_class=NormalizationClass.SKILLS,
            original_value="Py",
            original_value_lookup="py",
            normalized_value="python",
            normalized_value_canonical="python",
            normalization_status=NormalizationStatus.NORMALIZED,
            confidence=0.95,
            provider="manual",
            model_version=None,
            pipeline_version="v2",
            metadata_json='{"note":"updated"}',
        )
        await session.commit()

        records = await repo.list_by_class(NormalizationClass.SKILLS)
        assert len(records) == 1
        assert records[0].provider == "manual"


@pytest.mark.asyncio
async def test_entity_normalization_integrates_with_job_preparation(db_sessionmaker):
    async with db_sessionmaker() as session:
        agent = FakeNormalizationAgentClient(
            {
                ("languages", "Англ. яз"): NormalizationAgentOutput(
                    normalized_value="English",
                    status=NormalizationStatus.NORMALIZED,
                    confidence=0.93,
                    matched_existing_canonical=True,
                )
            }
        )
        normalization_service = EntityNormalizationService(
            session=session,
            agent_client=agent,
            skill_normalizer=FakeSkillNormalizer(),
        )

        prepared = await normalize_job_search_requirements(
            raw_text="Senior Python Backend Engineer with English requirement",
            extracted=JobSearchExtractionLLMOutput.model_validate(
                {
                    "title_raw": "Senior Python Backend Engineer",
                    "required_languages": [
                        {
                            "language_raw": "Англ. яз",
                            "required": True,
                        }
                    ],
                    "required_skills": [
                        {"raw_skill": "Py", "source_type": "explicit", "confidence": 0.9}
                    ],
                }
            ),
            normalization_service=normalization_service,
            skill_normalizer=FakeSkillNormalizer(),
        )
        await session.commit()

        assert prepared.rule_filters.title_normalized == "backend_engineer"
        assert prepared.rule_filters.required_languages[0].language_normalized == "English"
        assert prepared.rule_filters.required_skills == ["python"]
        records = await EntityNormalizationRepository(session).list_by_class(
            NormalizationClass.LANGUAGES
        )
        assert len(records) == 1
