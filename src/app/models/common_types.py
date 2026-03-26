from __future__ import annotations

from typing import Literal, TypeAlias

from app.service.normalization.primitives import (
    EDUCATION_CANONICAL,
    EMPLOYMENT_TYPE_CANONICAL,
    PROFICIENCY_CANONICAL,
    REMOTE_POLICY_CANONICAL,
    SENIORITY_CANONICAL,
)

RemotePolicyLiteral: TypeAlias = Literal[*REMOTE_POLICY_CANONICAL]
EmploymentTypeLiteral: TypeAlias = Literal[*EMPLOYMENT_TYPE_CANONICAL]
SeniorityLiteral: TypeAlias = Literal[*SENIORITY_CANONICAL]
ProficiencyLiteral: TypeAlias = Literal[*PROFICIENCY_CANONICAL]
EducationLiteral: TypeAlias = Literal[*EDUCATION_CANONICAL]

ExtractedSkillSourceLiteral: TypeAlias = Literal[
    "explicit",
    "inferred_from_experience",
    "must_have",
    "nice_to_have",
]
CandidateSkillSearchSourceLiteral: TypeAlias = Literal[
    "explicit",
    "inferred_from_experience",
    "any",
]
VectorChunkTypeLiteral: TypeAlias = Literal[
    "role_profile",
    "experience_role",
    "skills_profile",
]
EducationMatchStatusLiteral: TypeAlias = Literal["matched", "partial", "mismatch"]
