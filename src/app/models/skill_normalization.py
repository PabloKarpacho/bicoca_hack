from __future__ import annotations

from pydantic import BaseModel, Field


class HHSkillSuggestion(BaseModel):
    id: int
    text: str


class HHSkillNormalizationResult(BaseModel):
    raw_skill: str
    normalized_skill_text: str | None = None
    normalized_skill_external_id: int | None = None
    provider: str = "hh"
    match_type: str = "no_match"
    confidence: float = 0.0
    alternatives: list[HHSkillSuggestion] = Field(default_factory=list)
    error: str | None = None
