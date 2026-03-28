from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

from database.postgres.crud.cv import (
    CandidateExperienceRepository,
    CandidateLanguageRepository,
    CandidateProfileRepository,
    CandidateSkillRepository,
)
from app.models.candidate_vector import CandidateDocumentChunkData


@dataclass(slots=True)
class CandidateChunkBuilderService:
    profiles: CandidateProfileRepository
    languages: CandidateLanguageRepository
    experiences: CandidateExperienceRepository
    skills: CandidateSkillRepository

    async def build_document_chunks(
        self,
        document_id: str,
    ) -> list[CandidateDocumentChunkData]:
        profile = await self.profiles.get_by_document_id(document_id)
        if profile is None:
            return []

        languages = await self.languages.list_by_document_id(document_id)
        experiences = await self.experiences.list_by_document_id(document_id)
        skills = await self.skills.list_by_document_id(document_id)

        chunks: list[CandidateDocumentChunkData] = []
        role_profile_chunk = self._build_role_profile_chunk(
            profile=profile,
            languages=languages,
            experiences=experiences,
            skills=skills,
        )
        if role_profile_chunk is not None:
            chunks.append(role_profile_chunk)

        for experience in experiences:
            chunk = self._build_experience_role_chunk(
                candidate_id=profile.candidate_id,
                document_id=document_id,
                experience=experience,
            )
            if chunk is not None:
                chunks.append(chunk)

        skills_chunk = self._build_skills_profile_chunk(
            candidate_id=profile.candidate_id,
            document_id=document_id,
            skills=skills,
            experiences=experiences,
        )
        if skills_chunk is not None:
            chunks.append(skills_chunk)
        return chunks

    def _build_role_profile_chunk(
        self,
        *,
        profile,
        languages,
        experiences,
        skills,
    ) -> CandidateDocumentChunkData | None:
        profession_tags = self._collect_profession_tags(
            profile=profile, experiences=experiences
        )
        explicit_skills = self._collect_skills(skills, source_types={"explicit"})
        language_tags = self._collect_languages(languages)
        language_descriptions = self._collect_language_descriptions(languages)
        domain_tags = self._collect_domains(experiences)
        parts = [
            _sentence(
                "Current role",
                _humanize_role_value(
                    _first_non_empty(
                        profile.current_title_normalized, profile.current_title_raw
                    )
                ),
            ),
            _sentence("Related roles", _join_values(profession_tags[1:])),
            _sentence("Seniority", profile.seniority_normalized),
            _sentence(
                "Total experience",
                (
                    f"{profile.total_experience_months} months"
                    if profile.total_experience_months is not None
                    else None
                ),
            ),
            _sentence("Headline", _trim_sentence(profile.headline)),
            _sentence("Profile summary", _trim_sentence(profile.summary, limit=280)),
            _sentence("Domains", _join_values(domain_tags)),
            _sentence("Languages", _join_values(language_descriptions)),
            _sentence("Core skills", _join_values(explicit_skills[:10])),
        ]
        chunk_text = " ".join(part for part in parts if part).strip()
        if not chunk_text:
            return None
        return CandidateDocumentChunkData(
            candidate_id=profile.candidate_id,
            document_id=profile.document_id,
            chunk_type="role_profile",
            chunk_text=chunk_text,
            chunk_hash=_chunk_hash("role_profile", chunk_text, "profile"),
            source_entity_type="candidate_profile",
            source_entity_id=getattr(profile, "profile_id", None),
            chunk_metadata={
                "current_title_normalized": profile.current_title_normalized,
                "profession_tags": profession_tags,
                "seniority_normalized": profile.seniority_normalized,
                "skill_tags": explicit_skills,
                "language_tags": language_tags,
                "domain_tags": domain_tags,
                "total_experience_months": profile.total_experience_months,
            },
        )

    def _build_experience_role_chunk(
        self,
        *,
        candidate_id: str,
        document_id: str,
        experience,
    ) -> CandidateDocumentChunkData | None:
        technologies = _normalize_csv_values(experience.technologies_text)
        parts = [
            _sentence(
                "Role", experience.job_title_normalized or experience.job_title_raw
            ),
            _sentence("Company", experience.company_name_raw),
            _sentence(
                "Period",
                _format_date_range(
                    experience.start_date, experience.end_date, experience.is_current
                ),
            ),
            _sentence(
                "Duration",
                (
                    f"{experience.duration_months} months"
                    if experience.duration_months is not None
                    else None
                ),
            ),
            _sentence("Domain", experience.domain_hint),
            _sentence("Responsibilities", experience.responsibilities_text),
            _sentence("Technologies", _join_values(technologies)),
        ]
        chunk_text = " ".join(part for part in parts if part).strip()
        if not chunk_text:
            return None
        return CandidateDocumentChunkData(
            candidate_id=candidate_id,
            document_id=document_id,
            chunk_type="experience_role",
            chunk_text=chunk_text,
            chunk_hash=_chunk_hash(
                "experience_role",
                chunk_text,
                getattr(experience, "experience_id", ""),
            ),
            source_entity_type="candidate_experience",
            source_entity_id=getattr(experience, "experience_id", None),
            chunk_metadata={
                "company_name": experience.company_name_raw,
                "job_title_normalized": experience.job_title_normalized,
                "profession_tags": (
                    [experience.job_title_normalized]
                    if experience.job_title_normalized
                    else []
                ),
                "skill_tags": technologies,
                "domain_tags": (
                    [experience.domain_hint] if experience.domain_hint else []
                ),
                "is_current_role": experience.is_current,
                "start_date": (
                    experience.start_date.isoformat() if experience.start_date else None
                ),
                "end_date": (
                    experience.end_date.isoformat() if experience.end_date else None
                ),
                "duration_months": experience.duration_months,
            },
        )

    def _build_skills_profile_chunk(
        self,
        *,
        candidate_id: str,
        document_id: str,
        skills,
        experiences,
    ) -> CandidateDocumentChunkData | None:
        explicit_skills = self._collect_skills(skills, source_types={"explicit"})
        inferred_skills = self._collect_skills(
            skills, source_types={"inferred_from_experience"}
        )
        experience_confirmed = self._collect_experience_confirmed_skills(
            explicit_skills=explicit_skills,
            inferred_skills=inferred_skills,
            experiences=experiences,
        )
        all_skills = sorted({*explicit_skills, *inferred_skills, *experience_confirmed})
        if not all_skills:
            return None
        parts = [
            _sentence("Core skills", _join_values(explicit_skills[:14])),
            _sentence(
                "Confirmed in experience", _join_values(experience_confirmed[:14])
            ),
            _sentence(
                "Additional tools",
                _join_values(
                    _diff_values(all_skills, explicit_skills, experience_confirmed)[:10]
                ),
            ),
        ]
        chunk_text = " ".join(part for part in parts if part).strip()
        return CandidateDocumentChunkData(
            candidate_id=candidate_id,
            document_id=document_id,
            chunk_type="skills_profile",
            chunk_text=chunk_text,
            chunk_hash=_chunk_hash("skills_profile", chunk_text, "skills"),
            source_entity_type="candidate_skill",
            source_entity_id=None,
            chunk_metadata={
                "skill_tags": all_skills,
                "explicit_skill_tags": explicit_skills,
                "experience_confirmed_skill_tags": experience_confirmed,
            },
        )

    def _collect_profession_tags(self, *, profile, experiences) -> list[str]:
        profession_tags: list[str] = []

        for value in [
            profile.current_title_normalized,
            profile.current_title_raw,
            *[experience.job_title_normalized for experience in experiences],
            *[experience.job_title_raw for experience in experiences],
        ]:
            normalized = _normalize_profession_tag(value)
            if normalized and normalized not in profession_tags:
                profession_tags.append(normalized)
        return profession_tags

    def _collect_skills(
        self, skills, source_types: set[str] | None = None
    ) -> list[str]:
        values: list[str] = []
        for skill in skills:
            if source_types and skill.source_type not in source_types:
                continue
            normalized = _normalize_skill_tag(skill.normalized_skill)
            if normalized and normalized not in values:
                values.append(normalized)
        return values

    def _collect_experience_confirmed_skills(
        self,
        *,
        explicit_skills: list[str],
        inferred_skills: list[str],
        experiences,
    ) -> list[str]:
        technologies = {
            skill
            for experience in experiences
            for skill in _normalize_csv_values(experience.technologies_text)
        }
        confirmed = [
            skill
            for skill in [*explicit_skills, *inferred_skills]
            if skill in technologies
        ]
        return list(dict.fromkeys(confirmed))

    def _collect_languages(self, languages) -> list[str]:
        values: list[str] = []
        for language in languages:
            normalized = _normalize_language_tag(language.language_normalized)
            if normalized and normalized not in values:
                values.append(normalized)
        return values

    def _collect_language_descriptions(self, languages) -> list[str]:
        values: list[str] = []
        for language in languages:
            name = _normalize_language_tag(language.language_normalized)
            if not name:
                continue
            proficiency = _clean_token(language.proficiency_normalized)
            values.append(f"{name} ({proficiency})" if proficiency else name)
        return values

    def _collect_domains(self, experiences) -> list[str]:
        values: list[str] = []
        for experience in experiences:
            domain = _clean_token(experience.domain_hint)
            if domain and domain not in values:
                values.append(domain)
        return values


def _chunk_hash(chunk_type: str, chunk_text: str, source: str) -> str:
    return hashlib.sha256(
        f"{chunk_type}|{source}|{chunk_text}".encode("utf-8")
    ).hexdigest()


def _sentence(label: str, value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).strip().split())
    if not cleaned:
        return None
    return f"{label}: {cleaned}."


def _format_date_range(start_date, end_date, is_current: bool) -> str | None:
    if start_date is None and end_date is None and not is_current:
        return None
    start = start_date.isoformat() if start_date else "unknown"
    end = "present" if is_current else (end_date.isoformat() if end_date else "unknown")
    return f"{start} to {end}"


def _normalize_profession_tag(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).replace("_", " ").strip().lower().split())
    return cleaned or None


def _humanize_role_value(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).replace("_", " ").strip().split())
    return cleaned or None


def _normalize_skill_tag(value: str | None) -> str | None:
    return _clean_token(value)


def _normalize_language_tag(value: str | None) -> str | None:
    return _clean_token(value)


def _clean_token(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).replace("_", " ").strip().lower().split())
    return cleaned or None


def _trim_sentence(value: str | None, limit: int = 220) -> str | None:
    cleaned = _clean_whitespace(value)
    if not cleaned:
        return None
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 3].rstrip(" ,;:.") + "..."


def _clean_whitespace(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = " ".join(str(value).strip().split())
    return cleaned or None


def _join_values(values: list[str] | None) -> str | None:
    if not values:
        return None
    cleaned = [item for item in values if item]
    if not cleaned:
        return None
    return ", ".join(cleaned)


def _first_non_empty(*values: str | None) -> str | None:
    for value in values:
        cleaned = _clean_whitespace(value)
        if cleaned:
            return cleaned
    return None


def _normalize_csv_values(value: str | None) -> list[str]:
    cleaned = _clean_whitespace(value)
    if not cleaned:
        return []
    parts = re.split(r"[,/;|]+", cleaned)
    result: list[str] = []
    for part in parts:
        normalized = _normalize_skill_tag(part)
        if normalized and normalized not in result:
            result.append(normalized)
    return result


def _diff_values(source: list[str], *exclude_groups: list[str]) -> list[str]:
    exclude = {item for group in exclude_groups for item in group}
    return [item for item in source if item not in exclude]
