import json

import pytest

from app.config.enums.document_status import DocumentProcessingStatus
from app.models.candidate_search import CandidateLanguageFilter, CandidateSearchFilters
from app.service.search.candidate_rule_search import CandidateRuleSearchService
from database.postgres.crud.cv import (
    CandidateCertificationRepository,
    CandidateDocumentRepository,
    CandidateEducationRepository,
    CandidateExperienceRepository,
    CandidateLanguageRepository,
    CandidateProfileRepository,
    CandidateRepository,
    CandidateSkillRepository,
)


async def _seed_candidate(
    session,
    *,
    external_id: str,
    full_name: str,
    email: str,
    current_title_normalized: str,
    seniority_normalized: str,
    total_experience_months: int,
    location_raw: str,
    remote_policies: list[str] | None = None,
    employment_types: list[str] | None = None,
    skills: list[dict],
    languages: list[dict],
    experiences: list[dict],
    education: list[dict] | None = None,
    certifications: list[dict] | None = None,
):
    candidates = CandidateRepository(session)
    documents = CandidateDocumentRepository(session)
    profiles = CandidateProfileRepository(session)
    skill_repo = CandidateSkillRepository(session)
    language_repo = CandidateLanguageRepository(session)
    experience_repo = CandidateExperienceRepository(session)
    education_repo = CandidateEducationRepository(session)
    certification_repo = CandidateCertificationRepository(session)

    candidate = await candidates.create(
        external_id=external_id,
        full_name=full_name,
        email=email,
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
        email=email,
        location_raw=location_raw,
        remote_policies_json=(
            json.dumps(remote_policies, ensure_ascii=False)
            if remote_policies is not None
            else None
        ),
        employment_types_json=(
            json.dumps(employment_types, ensure_ascii=False)
            if employment_types is not None
            else None
        ),
        current_title_normalized=current_title_normalized,
        seniority_normalized=seniority_normalized,
        total_experience_months=total_experience_months,
    )

    for skill in skills:
        await skill_repo.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            **skill,
        )
    for language in languages:
        await language_repo.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            **language,
        )
    for experience in experiences:
        await experience_repo.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            **experience,
        )
    for item in education or []:
        await education_repo.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            **item,
        )
    for item in certifications or []:
        await certification_repo.create(
            candidate_id=candidate.candidate_id,
            document_id=document.document_id,
            **item,
        )
    await session.commit()
    return candidate.candidate_id, document.document_id


async def _seed_search_data(session) -> None:
    await _seed_candidate(
        session,
        external_id="cand-a",
        full_name="Alice",
        email="alice@example.com",
        current_title_normalized="backend_engineer",
        seniority_normalized="senior",
        total_experience_months=72,
        location_raw="Milan",
        remote_policies=["remote", "hybrid"],
        employment_types=["full_time", "contract"],
        skills=[
            {
                "raw_skill": "Python",
                "normalized_skill": "python",
                "skill_category": "programming_language",
                "source_type": "explicit",
                "confidence": 0.9,
            },
            {
                "raw_skill": "FastAPI",
                "normalized_skill": "fastapi",
                "skill_category": "framework",
                "source_type": "explicit",
                "confidence": 0.88,
            },
        ],
        languages=[
            {
                "language_raw": "English",
                "language_normalized": "English",
                "proficiency_raw": "Advanced",
                "proficiency_normalized": "professional",
                "confidence": 0.9,
            }
        ],
        experiences=[
            {
                "position_order": 1,
                "company_name_raw": "Example Inc",
                "job_title_raw": "Backend Engineer",
                "job_title_normalized": "backend_engineer",
                "duration_months": 48,
                "domain_hint": "fintech",
                "is_current": True,
            }
        ],
        education=[
            {
                "position_order": 1,
                "institution_raw": "Polimi",
                "degree_raw": "MSc Computer Science",
                "degree_normalized": "master",
                "field_of_study": "computer science",
            }
        ],
        certifications=[
            {
                "certification_name_raw": "AWS Certified Developer",
                "certification_name_normalized": "aws certified developer",
                "issuer": "Amazon",
            }
        ],
    )
    await _seed_candidate(
        session,
        external_id="cand-b",
        full_name="Bob",
        email="bob@example.com",
        current_title_normalized="data_engineer",
        seniority_normalized="mid",
        total_experience_months=48,
        location_raw="Rome",
        remote_policies=["onsite"],
        employment_types=["part_time"],
        skills=[
            {
                "raw_skill": "Python",
                "normalized_skill": "python",
                "skill_category": "programming_language",
                "source_type": "explicit",
                "confidence": 0.85,
            },
            {
                "raw_skill": "PostgreSQL",
                "normalized_skill": "postgresql",
                "skill_category": "database",
                "source_type": "explicit",
                "confidence": 0.84,
            },
        ],
        languages=[
            {
                "language_raw": "English",
                "language_normalized": "English",
                "proficiency_raw": "Basic",
                "proficiency_normalized": "basic",
                "confidence": 0.7,
            },
            {
                "language_raw": "Italian",
                "language_normalized": "Italian",
                "proficiency_raw": "Native",
                "proficiency_normalized": "native",
                "confidence": 0.95,
            },
        ],
        experiences=[
            {
                "position_order": 1,
                "company_name_raw": "Data Corp",
                "job_title_raw": "Data Engineer",
                "job_title_normalized": "data_engineer",
                "duration_months": 36,
                "domain_hint": "data platform",
                "is_current": True,
            }
        ],
    )
    await _seed_candidate(
        session,
        external_id="cand-c",
        full_name="Carol",
        email="carol@example.com",
        current_title_normalized="frontend_engineer",
        seniority_normalized="senior",
        total_experience_months=60,
        location_raw="Berlin",
        remote_policies=["remote"],
        employment_types=["contract"],
        skills=[
            {
                "raw_skill": "JavaScript",
                "normalized_skill": "javascript",
                "skill_category": "programming_language",
                "source_type": "explicit",
                "confidence": 0.9,
            },
            {
                "raw_skill": "React",
                "normalized_skill": "react",
                "skill_category": "framework",
                "source_type": "explicit",
                "confidence": 0.9,
            },
        ],
        languages=[
            {
                "language_raw": "English",
                "language_normalized": "English",
                "proficiency_raw": "Fluent",
                "proficiency_normalized": "fluent",
                "confidence": 0.93,
            }
        ],
        experiences=[
            {
                "position_order": 1,
                "company_name_raw": "Shop Co",
                "job_title_raw": "Frontend Engineer",
                "job_title_normalized": "frontend_engineer",
                "duration_months": 42,
                "domain_hint": "ecommerce",
                "is_current": True,
            }
        ],
    )
    await _seed_candidate(
        session,
        external_id="cand-d",
        full_name="Dave",
        email="dave@example.com",
        current_title_normalized="backend_engineer",
        seniority_normalized="junior",
        total_experience_months=24,
        location_raw="Milan",
        remote_policies=None,
        employment_types=["internship"],
        skills=[
            {
                "raw_skill": "Go",
                "normalized_skill": "go",
                "skill_category": "programming_language",
                "source_type": "explicit",
                "confidence": 0.83,
            },
            {
                "raw_skill": "PostgreSQL",
                "normalized_skill": "postgresql",
                "skill_category": "database",
                "source_type": "inferred_from_experience",
                "confidence": 0.6,
            },
        ],
        languages=[
            {
                "language_raw": "Italian",
                "language_normalized": "Italian",
                "proficiency_raw": "Professional",
                "proficiency_normalized": "professional",
                "confidence": 0.82,
            }
        ],
        experiences=[
            {
                "position_order": 1,
                "company_name_raw": "Infra Co",
                "job_title_raw": "Backend Engineer",
                "job_title_normalized": "backend_engineer",
                "duration_months": 18,
                "domain_hint": "infra",
                "is_current": True,
            }
        ],
    )


@pytest.mark.asyncio
async def test_rule_search_filter_by_one_skill(db_sessionmaker):
    async with db_sessionmaker() as session:
        await _seed_search_data(session)
    async with db_sessionmaker() as session:
        result = await CandidateRuleSearchService(session).search(
            CandidateSearchFilters(include_skills=["python"], sort_by="full_name", sort_order="asc")
        )

        assert result.total == 4
        assert [item.full_name for item in result.items] == ["Alice", "Bob", "Carol", "Dave"]
        assert result.items[0].match_metadata is not None
        assert result.items[0].match_metadata.matched_skills == ["python"]
        assert result.items[2].match_metadata is not None
        assert result.items[2].match_metadata.matched_skills == []


@pytest.mark.asyncio
async def test_rule_search_multiple_skills_are_reported_as_metadata_only(db_sessionmaker):
    async with db_sessionmaker() as session:
        await _seed_search_data(session)
    async with db_sessionmaker() as session:
        result = await CandidateRuleSearchService(session).search(
            CandidateSearchFilters(
                include_skills=["python", "fastapi"],
                require_all_skills=True,
                sort_by="full_name",
                sort_order="asc",
            )
        )

        assert result.total == 4
        assert result.items[0].full_name == "Alice"
        assert result.items[0].match_metadata is not None
        assert result.items[0].match_metadata.matched_skills == ["fastapi", "python"]


@pytest.mark.asyncio
async def test_rule_search_language_with_proficiency(db_sessionmaker):
    async with db_sessionmaker() as session:
        await _seed_search_data(session)
    async with db_sessionmaker() as session:
        result = await CandidateRuleSearchService(session).search(
            CandidateSearchFilters(
                languages=[
                    CandidateLanguageFilter(
                        language_normalized="English",
                        min_proficiency_normalized="professional",
                    )
                ],
                sort_by="full_name",
                sort_order="asc",
            )
        )

        assert result.total == 4
        assert [item.full_name for item in result.items[:2]] == ["Alice", "Carol"]
        assert result.items[0].match_metadata is not None
        assert result.items[0].match_metadata.matched_languages == ["English"]


@pytest.mark.asyncio
async def test_rule_search_seniority_and_min_experience(db_sessionmaker):
    async with db_sessionmaker() as session:
        await _seed_search_data(session)
    async with db_sessionmaker() as session:
        result = await CandidateRuleSearchService(session).search(
            CandidateSearchFilters(
                seniority_normalized=["senior"],
                min_total_experience_months=60,
                sort_by="full_name",
                sort_order="asc",
            )
        )

        assert result.total == 4
        assert [item.full_name for item in result.items[:2]] == ["Alice", "Carol"]
        assert result.items[0].match_score_percent is not None
        assert result.items[0].match_score_percent >= result.items[1].match_score_percent


@pytest.mark.asyncio
async def test_rule_search_domain_is_not_a_hard_filter(db_sessionmaker):
    async with db_sessionmaker() as session:
        await _seed_search_data(session)
    async with db_sessionmaker() as session:
        result = await CandidateRuleSearchService(session).search(
            CandidateSearchFilters(
                domains=["fintech"],
                sort_by="full_name",
                sort_order="asc",
            )
        )

        assert result.total == 4
        assert [item.full_name for item in result.items] == [
            "Alice",
            "Bob",
            "Carol",
            "Dave",
        ]


@pytest.mark.asyncio
async def test_rule_search_remote_policy_is_not_a_hard_filter(db_sessionmaker):
    async with db_sessionmaker() as session:
        await _seed_search_data(session)
    async with db_sessionmaker() as session:
        result = await CandidateRuleSearchService(session).search(
            CandidateSearchFilters(
                remote_policies=["hybrid"],
                sort_by="full_name",
                sort_order="asc",
            )
        )

        assert result.total == 4
        assert [item.full_name for item in result.items] == [
            "Alice",
            "Bob",
            "Carol",
            "Dave",
        ]
        assert result.items[0].remote_policies == ["remote", "hybrid"]


@pytest.mark.asyncio
async def test_rule_search_employment_types_match_on_intersection(db_sessionmaker):
    async with db_sessionmaker() as session:
        await _seed_search_data(session)
    async with db_sessionmaker() as session:
        result = await CandidateRuleSearchService(session).search(
            CandidateSearchFilters(
                employment_types=["full_time", "part_time"],
                sort_by="full_name",
                sort_order="asc",
            )
        )

        assert result.total == 4
        assert [item.full_name for item in result.items] == ["Alice", "Bob", "Carol", "Dave"]
        assert result.items[0].match_metadata is not None
        assert result.items[0].match_metadata.matched_employment_types == ["full_time"]
        assert result.items[1].match_metadata is not None
        assert result.items[1].match_metadata.matched_employment_types == ["part_time"]
        assert result.items[2].match_metadata is not None
        assert result.items[2].match_metadata.matched_employment_types == []
        assert result.items[3].match_metadata is not None
        assert result.items[3].match_metadata.matched_employment_types == []


@pytest.mark.asyncio
async def test_rule_search_empty_result(db_sessionmaker):
    async with db_sessionmaker() as session:
        await _seed_search_data(session)
    async with db_sessionmaker() as session:
        result = await CandidateRuleSearchService(session).search(
            CandidateSearchFilters(include_skills=["rust"])
        )

        assert result.total == 4
        assert all((item.match_metadata and item.match_metadata.matched_skills == []) for item in result.items)


@pytest.mark.asyncio
async def test_rule_search_education_is_soft_and_reports_match_mismatch(db_sessionmaker):
    async with db_sessionmaker() as session:
        await _seed_search_data(session)
    async with db_sessionmaker() as session:
        result = await CandidateRuleSearchService(session).search(
            CandidateSearchFilters(
                degree_normalized=["master"],
                sort_by="full_name",
                sort_order="asc",
            )
        )

        assert result.total == 4
        alice = result.items[0]
        bob = result.items[1]

        assert alice.full_name == "Alice"
        assert alice.match_metadata is not None
        assert alice.match_metadata.education_match_status == "matched"
        assert "matched on: master" in (alice.match_metadata.education_match_note or "").lower()

        assert bob.full_name == "Bob"
        assert bob.match_metadata is not None
        assert bob.match_metadata.education_match_status == "mismatch"
        assert "no overlap" in (bob.match_metadata.education_match_note or "").lower()


@pytest.mark.asyncio
async def test_rule_search_education_matches_when_any_requested_degree_intersects(
    db_sessionmaker,
):
    async with db_sessionmaker() as session:
        await _seed_search_data(session)
    async with db_sessionmaker() as session:
        result = await CandidateRuleSearchService(session).search(
            CandidateSearchFilters(
                degree_normalized=["master", "phd"],
                sort_by="full_name",
                sort_order="asc",
            )
        )

        assert result.total == 4
        alice = result.items[0]
        assert alice.full_name == "Alice"
        assert alice.match_metadata is not None
        assert alice.match_metadata.education_match_status == "matched"
        assert alice.match_metadata.matched_degrees == ["master"]
        assert "matched on: master" in (alice.match_metadata.education_match_note or "").lower()


@pytest.mark.asyncio
async def test_rule_search_pagination(db_sessionmaker):
    async with db_sessionmaker() as session:
        await _seed_search_data(session)
    async with db_sessionmaker() as session:
        result = await CandidateRuleSearchService(session).search(
            CandidateSearchFilters(limit=2, offset=1, sort_by="full_name", sort_order="asc")
        )

        assert result.total == 4
        assert [item.full_name for item in result.items] == ["Bob", "Carol"]


@pytest.mark.asyncio
async def test_rule_search_stable_ordering(db_sessionmaker):
    async with db_sessionmaker() as session:
        await _seed_search_data(session)
    async with db_sessionmaker() as session:
        result = await CandidateRuleSearchService(session).search(
            CandidateSearchFilters(sort_by="full_name", sort_order="asc")
        )

        assert [item.full_name for item in result.items] == [
            "Alice",
            "Bob",
            "Carol",
            "Dave",
        ]


@pytest.mark.asyncio
async def test_rule_search_multiple_filters_together(db_sessionmaker):
    async with db_sessionmaker() as session:
        await _seed_search_data(session)
    async with db_sessionmaker() as session:
        result = await CandidateRuleSearchService(session).search(
            CandidateSearchFilters(
                include_skills=["python"],
                current_title_normalized=["backend engineer"],
                seniority_normalized=["senior"],
                languages=[
                    CandidateLanguageFilter(
                        language_normalized="english",
                        min_proficiency_normalized="professional",
                    )
                ],
                domains=["fintech"],
            )
        )

        assert result.total == 4
        assert result.items[0].full_name == "Alice"
        assert result.items[0].match_score_percent is not None
        assert result.items[0].match_score_percent > (result.items[1].match_score_percent or 0)


@pytest.mark.asyncio
async def test_rule_search_current_title_is_not_a_hard_filter(db_sessionmaker):
    async with db_sessionmaker() as session:
        await _seed_search_data(session)
    async with db_sessionmaker() as session:
        result = await CandidateRuleSearchService(session).search(
            CandidateSearchFilters(
                current_title_normalized=["backend engineer"],
                sort_by="full_name",
                sort_order="asc",
            )
        )

        assert result.total == 4
        assert [item.full_name for item in result.items] == [
            "Alice",
            "Bob",
            "Carol",
            "Dave",
        ]


@pytest.mark.asyncio
async def test_rule_search_keeps_results_even_when_many_filters_do_not_overlap(
    db_sessionmaker,
):
    async with db_sessionmaker() as session:
        await _seed_search_data(session)
    async with db_sessionmaker() as session:
        result = await CandidateRuleSearchService(session).search(
            CandidateSearchFilters(
                current_title_normalized=["site reliability engineer"],
                seniority_normalized=["lead"],
                min_total_experience_months=120,
                location_normalized=["Paris"],
                languages=[
                    CandidateLanguageFilter(
                        language_normalized="German",
                        min_proficiency_normalized="native",
                    )
                ],
                certifications=["kubernetes administrator"],
            )
        )

        assert result.total == 4
        assert len(result.items) == 4
