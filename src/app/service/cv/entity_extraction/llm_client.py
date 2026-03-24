from __future__ import annotations

from app.config.llm_config import llm_settings
from app.models.entity_extraction import CVEntityExtractionLLMOutput
from app.service.llm.agent import Agent

KNOWN_SKILL_CATEGORIES = [
    "Backend",
    "Data / Storage",
    "framework",
    "LLM / Agents",
    "ML Framework",
    "MLOps / Evaluation",
    "ML / Speech",
    "Programming",
    "programming_language",
    "Retrieval / ML",
    "Retrieval / Vector DB",
    "Serving / Infra",
]

KNOWN_SKILL_CATEGORIES_TEXT = "\n".join(
    f"- {category}" for category in KNOWN_SKILL_CATEGORIES
)

SYSTEM_PROMPT = f"""
You extract structured candidate entities from CV text.
Return only valid JSON. Do not return markdown. Do not add commentary.

Required top-level keys:
- profile
- languages
- experiences
- skills
- education
- certifications

Rules:
- Use null for unknown scalar values.
- Use [] for unknown arrays.
- If the CV mentions preferred work format, profile.remote_policies must be a list containing only values from: remote, hybrid, onsite.
- Do not invent remote policies. Use [] when not stated.
- If the CV mentions preferred employment arrangement, profile.employment_types must be a list containing only values from: full_time, part_time, contract, internship.
- Do not invent employment types. Use [] when not stated.
- education entries must use degree_normalized only from this closed set when the level can be inferred reliably: secondary, associate, bachelor, master, phd.
- For education, prefer canonical degree levels in degree_normalized and keep degree_raw as stated in the CV.
- If the exact education level is unclear, set degree_normalized=null instead of inventing a new value.
- Prefer ISO dates: YYYY-MM-DD. If only month is known, use the first day of month. If only year is known, use January 1st.
- Set is_current=true when the role is current, and end_date=null in that case.
- Keep summaries concise and factual.
- For skills, treat skills as hard skills only: technologies, programming languages, frameworks, libraries, databases, cloud/platform tools, developer tools, software products, and other concrete technical tools a person can use.
- Do not treat soft skills, personality traits, responsibilities, achievements, project descriptions, or full application names/sentences as skills.
- Each skill must be a short value: one word or a short phrase. Do not output full clauses, long descriptions, or whole application/project names in the skill field.
- If the CV has a dedicated skills/stack/technologies section, prefer taking skills from there exactly as stated and do not invent additional skills from other sections unless they are also clearly and explicitly stated elsewhere.
- If the CV does not have a dedicated skills section, you may extract skills from experience only when they are clearly supported by the resume text, but still output only short hard-skill labels.
- For inferred_from_experience, be conservative. Only use it when the hard skill is strongly evidenced by the resume.
- For each skill, fill skill_category when possible.
- Prefer one of these historically used skill_category values when there is a good semantic match:
{KNOWN_SKILL_CATEGORIES_TEXT}
- The historical categories are not fully normalized. Reuse them as-is for compatibility when they fit.
- If multiple historical categories seem possible, prefer the most specific existing one.
- For pure programming languages, prefer `programming_language` unless the CV clearly uses a broader bucket.
- If none of the historical categories fit, you may introduce a new concise English category label.
- Do not force a bad match only to stay inside the historical list.
- confidence values must be between 0 and 1.
""".strip()


class CVEntityExtractionLLMClient:
    def __init__(
        self,
        *,
        api_key: str | None = llm_settings.llm_api_key,
        base_url: str | None = llm_settings.llm_base_url,
        model: str | None = llm_settings.llm_cv_extraction_model_name,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") if base_url else None
        self.model = model
        self.agent = (
            Agent(
                api_key=self.api_key,
                base_url=self.base_url,
            )
            if self.base_url
            else None
        )

    async def extract_entities(self, raw_text: str) -> CVEntityExtractionLLMOutput:
        return await self.agent.structured_response(
            system_prompt=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": raw_text,
                }
            ],
            model=self.model,
            pydantic_class=CVEntityExtractionLLMOutput,
            temperature=0,
            max_tokens=4000,
        )
