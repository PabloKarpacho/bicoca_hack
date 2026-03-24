from app.models.candidate_search import (
    CandidateLanguageFilter,
    CandidateSearchFilters,
    CandidateSearchMatchMetadata,
)
from app.service.search.candidate_match_scoring import calculate_candidate_match_score


def test_match_score_combines_vector_and_structured_signals():
    percent, breakdown = calculate_candidate_match_score(
        filters=CandidateSearchFilters(
            current_title_normalized=["project_manager"],
            include_skills=["agile scrum", "project planning"],
            languages=[
                CandidateLanguageFilter(
                    language_normalized="English",
                    min_proficiency_normalized="professional",
                )
            ],
            min_total_experience_months=36,
        ),
        current_title_normalized="project_manager",
        total_experience_months=48,
        match_metadata=CandidateSearchMatchMetadata(
            matched_skills=["agile scrum", "project planning"],
            matched_languages=["English"],
        ),
        vector_semantic_score=0.82,
    )

    assert percent is not None
    assert breakdown is not None
    assert breakdown.vector_semantic_score == 0.82
    assert breakdown.role_match_score == 1.0
    assert breakdown.skills_match_score == 1.0
    assert breakdown.language_match_score == 1.0
    assert breakdown.experience_match_score == 1.0
    assert percent >= 85


def test_match_score_does_not_penalize_missing_optional_dimensions():
    percent, breakdown = calculate_candidate_match_score(
        filters=CandidateSearchFilters(
            current_title_normalized=["backend_engineer"],
        ),
        current_title_normalized="backend_engineer",
        total_experience_months=24,
        match_metadata=None,
        vector_semantic_score=None,
    )

    assert percent == 100
    assert breakdown is not None
    assert breakdown.role_match_score == 1.0
    assert breakdown.skills_match_score is None
    assert breakdown.language_match_score is None


def test_match_score_returns_zero_for_requested_but_unmatched_role_and_skills():
    percent, breakdown = calculate_candidate_match_score(
        filters=CandidateSearchFilters(
            current_title_normalized=["project_manager"],
            include_skills=["agile scrum", "project planning"],
        ),
        current_title_normalized="backend_engineer",
        total_experience_months=48,
        match_metadata=CandidateSearchMatchMetadata(
            matched_skills=[],
            matched_languages=[],
        ),
        vector_semantic_score=None,
    )

    assert percent == 0
    assert breakdown is not None
    assert breakdown.role_match_score == 0.0
    assert breakdown.skills_match_score == 0.0
