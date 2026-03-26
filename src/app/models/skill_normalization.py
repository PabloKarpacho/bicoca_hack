from __future__ import annotations

from pydantic import BaseModel, Field


class HHSkillSuggestion(BaseModel):
    id: int = Field(description="HH suggestion identifier for the skill.")
    text: str = Field(description="Suggested skill label returned by HH autosuggest.")


class HHSkillNormalizationResult(BaseModel):
    raw_skill: str = Field(description="Original skill string submitted for normalization.")
    normalized_skill_text: str | None = Field(default=None, description="Best normalized skill label returned by HH, if any.")
    normalized_skill_external_id: int | None = Field(default=None, description="HH external identifier for the matched skill, if any.")
    provider: str = Field(default="hh", description="Normalization provider name.")
    match_type: str = Field(default="no_match", description="How the normalized skill was selected, for example exact or prefix.")
    confidence: float = Field(default=0.0, description="Confidence score assigned to the normalization result.")
    alternatives: list[HHSkillSuggestion] = Field(default_factory=list, description="Alternative suggestions considered during normalization.")
    error: str | None = Field(default=None, description="Error message if normalization failed.")
