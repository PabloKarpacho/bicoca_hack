from __future__ import annotations

from app.config.llm_config import llm_settings
from app.models.entity_extraction import JobSearchExtractionLLMOutput
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

SYSTEM_PROMPT = """
You extract structured job requirements from a job description so they can later be compared with structured candidate entities.
Return only valid JSON. Do not return markdown. Do not add commentary.

Required top-level keys:
- profile
- languages
- skills
- education
- certifications
- domains
- responsibilities_summary
- extraction_confidence

Rules:
- Use null for unknown scalar values.
- Use [] for unknown arrays.
- profile must include:
  - title_raw
  - title_normalized
  - seniority_normalized
  - location_raw
  - remote_policies
  - employment_type
  - min_years_experience
  - min_experience_months
- profile.remote_policies must contain only values from: remote, hybrid, onsite.
- profile.remote_policies may contain multiple values when the job description clearly allows more than one work mode.
- Do not invent requirements that are not supported by the text.
- languages entries must include:
  - language_raw or language_normalized
  - proficiency_raw or min_proficiency_normalized
  - required
- skills must contain objects with:
  - raw_skill
  - normalized_skill
  - skill_category
  - source_type
  - confidence
- For job skills, source_type must be one of: must_have, nice_to_have.
- Separate must-have from nice-to-have whenever the wording clearly distinguishes mandatory requirements from optional preferences.
- For skills, treat skills as hard skills only: technologies, programming languages, frameworks, libraries, databases, cloud/platform tools, developer tools, software products, and other concrete technical tools.
- Do not treat soft skills, personality traits, responsibilities, broad team qualities, or full sentence fragments as skills.
- Each skill must be a short value: one word or a short phrase. Do not output long descriptions or project-sized phrases.
- For managerial and delivery roles, keep skill labels focused on stable capabilities such as project planning, risk management, resource planning, stakeholder communication, agile, or scrum.
- For managerial and delivery roles, do not output ceremony/process cadence phrases such as 2-week sprints, retrospectives, weekly updates, internal syncs, or similar workflow fragments as skills.
- If the job description has a dedicated skills/requirements/tech stack section, prefer taking skills from there exactly as stated and do not invent additional ones.
- If skills must be inferred from responsibilities, do it conservatively and still output only short hard-skill labels explicitly supported by the text.
- For each skill, fill skill_category when possible.
- Prefer one of these historically used skill_category values when there is a good semantic match:
{KNOWN_SKILL_CATEGORIES_TEXT}
- The historical categories are not fully normalized. Reuse them as-is for compatibility when they fit.
- If multiple historical categories seem possible, prefer the most specific existing one.
- For pure programming languages, prefer `programming_language` unless the text clearly uses a broader bucket.
- If none of the historical categories fit, you may introduce a new concise English category label.
- Do not force a bad match only to stay inside the historical list.
- education should contain structured degree requirements when they are explicitly mentioned.
- For education, degree_normalized must use only one of: secondary, associate, bachelor, master, phd.
- Prefer canonical degree levels in degree_normalized and keep degree_raw close to the wording from the job description.
- If the requirement implies higher education but the exact level is unclear, leave degree_normalized null instead of inventing a new value.
- certifications should contain structured certification requirements when they are explicitly mentioned.
- Keep responsibilities_summary compact, factual, and search-oriented.
- confidence values must be between 0 and 1.
""".strip().format(KNOWN_SKILL_CATEGORIES_TEXT=KNOWN_SKILL_CATEGORIES_TEXT)


class JobSearchPreparationLLMClient:
    """Structured LLM client for extracting search requirements from vacancy text."""

    def __init__(
        self,
        *,
        api_key: str | None = llm_settings.llm_api_key,
        base_url: str | None = llm_settings.llm_base_url,
        model: str | None = None,
    ) -> None:
        resolved_model = (
            model
            or llm_settings.llm_job_search_preparation_model_name
            or llm_settings.llm_cv_extraction_model_name
        )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/") if base_url else None
        self.model = resolved_model
        self.agent = (
            Agent(
                api_key=self.api_key,
                base_url=self.base_url,
            )
            if self.base_url
            else None
        )

    async def extract_requirements(self, raw_text: str) -> JobSearchExtractionLLMOutput:
        """Return structured vacancy requirements extracted from the full job text."""

        return await self.agent.structured_response(
            system_prompt=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": raw_text}],
            model=self.model,
            pydantic_class=JobSearchExtractionLLMOutput,
            temperature=0,
            max_tokens=3000,
        )
