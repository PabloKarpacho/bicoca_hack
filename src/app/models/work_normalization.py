from __future__ import annotations

from pydantic import BaseModel, Field


class HHWorkSuggestion(BaseModel):
    id: int = Field(description="HH suggestion identifier for the profession.")
    text: str = Field(description="Suggested profession label returned by HH autosuggest.")


class HHWorkNormalizationResult(BaseModel):
    raw_work: str = Field(description="Original profession or work label submitted for normalization.")
    normalized_work_text: str | None = Field(default=None, description="Best normalized profession label returned by HH, if any.")
    normalized_work_external_id: int | None = Field(default=None, description="HH external identifier for the matched profession, if any.")
    provider: str = Field(default="hh", description="Normalization provider name.")
    match_type: str = Field(default="no_match", description="How the normalized profession was selected, for example exact or prefix.")
    confidence: float = Field(default=0.0, description="Confidence score assigned to the normalization result.")
    alternatives: list[HHWorkSuggestion] = Field(default_factory=list, description="Alternative profession suggestions considered during normalization.")
    error: str | None = Field(default=None, description="Error message if normalization failed.")
