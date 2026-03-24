from __future__ import annotations

from app.config.enums.normalization_class import NormalizationClass
from app.config.llm_config import llm_settings
from app.models.normalization import NormalizationAgentOutput
from app.service.llm.agent import Agent

BASE_SYSTEM_PROMPT = """
You normalize one entity value into a canonical value for a specific normalization class.
Return only valid JSON. Do not return markdown. Do not add commentary.

You receive:
- normalization_class
- original_value
- canonical_values

Rules:
- Prefer an existing canonical value when there is a good match.
- Do not invent verbose prose.
- If there is no reliable match, return status=no_match and normalized_value=null.
- confidence must be between 0 and 1.
- matched_existing_canonical=true only when the result came from the provided canonical list.
""".strip()

CLASS_PROMPT_RULES = {
    NormalizationClass.PROFICIENCY_LEVELS: """
Class-specific rules for proficiency_levels:
- canonical_values is a closed allowed set. You must choose exactly one value from canonical_values or return normalized_value=null with status=no_match.
- Never invent a new proficiency level, label, band, CEFR code, or prose variant.
- If the source contains multiple levels, ranges, mixed labels, or slash-separated values such as "Upper-Intermediate / Advanced working proficiency (B2/C1)", choose one final canonical value only.
- When multiple levels are present, prefer the strongest explicitly supported level that best represents the phrase as a whole.
- Output must never contain multiple levels.
""".strip(),
    NormalizationClass.LANGUAGES: """
Class-specific rules for languages:
- Prefer an existing canonical language from canonical_values.
- Do not invent proficiency labels here; normalize only the language name.
- If the language is not identifiable with high confidence, return normalized_value=null with status=no_match.
""".strip(),
}


def build_system_prompt(normalization_class: NormalizationClass) -> str:
    prompt_parts = [BASE_SYSTEM_PROMPT]
    class_rules = CLASS_PROMPT_RULES.get(normalization_class)
    if class_rules:
        prompt_parts.append(class_rules)
    return "\n\n".join(prompt_parts)


class NormalizationAgentClient:
    """LLM client for class-aware entity normalization with structured output."""

    def __init__(
        self,
        *,
        api_key: str | None = llm_settings.llm_api_key,
        base_url: str | None = llm_settings.llm_base_url,
        model: str | None = None,
    ) -> None:
        resolved_model = (
            model
            or llm_settings.llm_entity_normalization_model_name
            or llm_settings.llm_cv_extraction_model_name
        )
        self.model = resolved_model
        self.base_url = base_url.rstrip("/") if base_url else None
        self.agent = (
            Agent(api_key=api_key, base_url=self.base_url)
            if self.base_url and resolved_model
            else None
        )

    async def normalize(
        self,
        *,
        normalization_class: NormalizationClass,
        original_value: str,
        canonical_values: list[str],
    ) -> NormalizationAgentOutput:
        if self.agent is None or self.model is None:
            return NormalizationAgentOutput(
                normalized_value=None,
                status="needs_review",
                confidence=0.0,
                rationale_short="agent_unavailable",
                matched_existing_canonical=False,
            )

        return await self.agent.structured_response(
            system_prompt=build_system_prompt(normalization_class),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"normalization_class: {normalization_class.value}\n"
                        f"original_value: {original_value}\n"
                        f"canonical_values: {canonical_values}"
                    ),
                }
            ],
            model=self.model,
            pydantic_class=NormalizationAgentOutput,
            temperature=0,
            max_tokens=1200,
        )
