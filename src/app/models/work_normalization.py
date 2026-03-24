from __future__ import annotations

from pydantic import BaseModel, Field


class HHWorkSuggestion(BaseModel):
    id: int
    text: str


class HHWorkNormalizationResult(BaseModel):
    raw_work: str
    normalized_work_text: str | None = None
    normalized_work_external_id: int | None = None
    provider: str = "hh"
    match_type: str = "no_match"
    confidence: float = 0.0
    alternatives: list[HHWorkSuggestion] = Field(default_factory=list)
    error: str | None = None
