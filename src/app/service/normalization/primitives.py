from __future__ import annotations

import re
from datetime import date

SKILL_SYNONYMS = {
    "py": "python",
    "python3": "python",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "postgre sql": "postgresql",
    "js": "javascript",
    "node.js": "nodejs",
    "node js": "nodejs",
    "ts": "typescript",
    "fast api": "fastapi",
    "golang": "go",
    "c sharp": "c#",
}

SKILL_CATEGORIES = {
    "python": "programming_language",
    "javascript": "programming_language",
    "typescript": "programming_language",
    "go": "programming_language",
    "postgresql": "database",
    "mysql": "database",
    "mongodb": "database",
    "redis": "database",
    "fastapi": "framework",
    "django": "framework",
    "flask": "framework",
    "react": "framework",
    "kubernetes": "infrastructure",
    "docker": "infrastructure",
    "aws": "cloud",
    "gcp": "cloud",
    "azure": "cloud",
}

LANGUAGE_LEVELS = {
    "native": "native",
    "mother tongue": "native",
    "bilingual": "native",
    "c2": "fluent",
    "fluent": "fluent",
    "full professional proficiency": "fluent",
    "professional working proficiency": "professional",
    "advanced": "professional",
    "advanced working proficiency": "professional",
    "c1": "professional",
    "b2+": "professional",
    "upper intermediate": "professional",
    "upper-intermediate": "professional",
    "upper intermediate / advanced working proficiency": "professional",
    "intermediate": "intermediate",
    "b2": "professional",
    "b1": "intermediate",
    "basic": "basic",
    "elementary": "basic",
    "a1": "basic",
    "a2": "basic",
}

PROFICIENCY_CANONICAL = (
    "native",
    "fluent",
    "professional",
    "intermediate",
    "basic",
)

LANGUAGE_NAME_SYNONYMS = {
    "english": "English",
    "italian": "Italian",
    "italiano": "Italian",
    "italian language": "Italian",
    "french": "French",
    "german": "German",
    "spanish": "Spanish",
}

JOB_TITLE_CLUSTERS = {
    "software engineer": "software_engineer",
    "software developer": "software_engineer",
    "backend engineer": "backend_engineer",
    "backend developer": "backend_engineer",
    "python developer": "backend_engineer",
    "frontend engineer": "frontend_engineer",
    "frontend developer": "frontend_engineer",
    "full stack developer": "fullstack_engineer",
    "fullstack developer": "fullstack_engineer",
    "data engineer": "data_engineer",
    "data scientist": "data_scientist",
    "devops engineer": "devops_engineer",
    "qa engineer": "qa_engineer",
    "product manager": "product_manager",
    "project manager": "project_manager",
}

REMOTE_POLICY_CANONICAL = ("remote", "hybrid", "onsite")
EMPLOYMENT_TYPE_CANONICAL = ("full_time", "part_time", "contract", "internship")
SENIORITY_CANONICAL = (
    "intern",
    "junior",
    "middle",
    "senior",
    "lead",
    "manager",
)
EDUCATION_CANONICAL = ("secondary", "associate", "bachelor", "master", "phd")

REMOTE_POLICY_MAP = {
    "remote": "remote",
    "fully remote": "remote",
    "work from home": "remote",
    "wfh": "remote",
    "hybrid": "hybrid",
    "hybrid remote": "hybrid",
    "hybrid work": "hybrid",
    "onsite": "onsite",
    "on-site": "onsite",
    "on site": "onsite",
    "office": "onsite",
    "in office": "onsite",
    "presenza": "onsite",
}

EMPLOYMENT_TYPE_MAP = {
    "full time": "full_time",
    "full-time": "full_time",
    "permanent": "full_time",
    "part time": "part_time",
    "part-time": "part_time",
    "contract": "contract",
    "freelance": "contract",
    "internship": "internship",
    "intern": "internship",
}

DEGREE_SYNONYMS = {
    "secondary": "secondary",
    "high school": "secondary",
    "school diploma": "secondary",
    "secondary school": "secondary",
    "associate": "associate",
    "associate degree": "associate",
    "college diploma": "associate",
    "diploma": "associate",
    "vocational": "associate",
    "bachelor": "bachelor",
    "bachelor's": "bachelor",
    "bsc": "bachelor",
    "bs": "bachelor",
    "undergraduate": "bachelor",
    "master": "master",
    "master's": "master",
    "msc": "master",
    "ms": "master",
    "specialist": "master",
    "mba": "master",
    "phd": "phd",
    "doctorate": "phd",
    "doctoral": "phd",
}

EDUCATION_LEVEL_RANK = {
    "secondary": 1,
    "associate": 2,
    "bachelor": 3,
    "master": 4,
    "phd": 5,
}

SENIORITY_LEVELS = {
    "intern": "intern",
    "junior": "junior",
    "jr": "junior",
    "middle": "middle",
    "mid": "middle",
    "senior": "senior",
    "lead": "lead",
    "staff": "lead",
    "principal": "lead",
    "manager": "manager",
    "head": "manager",
}


def normalize_skill_name(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"[_/]+", " ", value.strip().lower())
    normalized = re.sub(r"\s+", " ", normalized)
    return SKILL_SYNONYMS.get(normalized, normalized)


def normalize_language_level(value: str | None) -> str | None:
    """Map free-form language proficiency text to one canonical level.

    Only the project's canonical levels are returned:
    `native`, `fluent`, `professional`, `intermediate`, `basic`.

    Returning the original unknown string is intentionally avoided, because several
    Pydantic models use `Literal` typing for proficiency fields. Keeping an
    unrecognized value such as "a plus" would otherwise leak invalid data into later
    validation steps and fail the whole pipeline.
    """
    if not value:
        return None
    normalized = value.strip().lower()
    return LANGUAGE_LEVELS.get(normalized)


def normalize_language_name(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = re.sub(r"\s+", " ", value).strip()
    if not cleaned:
        return None
    canonical = LANGUAGE_NAME_SYNONYMS.get(cleaned.lower(), cleaned)
    return canonical if canonical[:1].isupper() else canonical.title()


def normalize_job_title(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    for synonym, canonical in JOB_TITLE_CLUSTERS.items():
        if synonym in normalized:
            return canonical
    return normalized.replace(" ", "_") if normalized else None


def normalize_degree(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    for synonym, canonical in DEGREE_SYNONYMS.items():
        if synonym in normalized:
            return canonical
    return normalized


def education_level_rank(value: str | None) -> int | None:
    normalized = normalize_degree(value)
    if not normalized:
        return None
    return EDUCATION_LEVEL_RANK.get(normalized)


def normalize_remote_policy(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    return REMOTE_POLICY_MAP.get(normalized, normalized.replace(" ", "_"))


def extract_remote_policies(value: str | list[str] | None) -> list[str] | None:
    if value is None:
        return None

    raw_values = value if isinstance(value, list) else [value]
    extracted: list[str] = []
    seen: set[str] = set()

    for raw_value in raw_values:
        if not raw_value:
            continue
        lowered = re.sub(r"\s+", " ", str(raw_value).strip().lower())
        if not lowered:
            continue

        matches: list[str] = []
        if re.search(r"\b(remote|fully remote|work from home|wfh)\b", lowered):
            matches.append("remote")
        if re.search(r"\bhybrid\b", lowered):
            matches.append("hybrid")
        if re.search(r"\b(onsite|on-site|on site|office|in office|presenza)\b", lowered):
            matches.append("onsite")

        normalized_direct = normalize_remote_policy(lowered)
        if normalized_direct in REMOTE_POLICY_CANONICAL:
            matches.append(normalized_direct)

        for match in matches:
            if match not in seen:
                seen.add(match)
                extracted.append(match)

    return extracted or None


def normalize_employment_type(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"\s+", " ", value.strip().lower())
    return EMPLOYMENT_TYPE_MAP.get(normalized, normalized.replace(" ", "_"))


def extract_employment_types(value: str | list[str] | None) -> list[str] | None:
    if value is None:
        return None

    raw_values = value if isinstance(value, list) else [value]
    extracted: list[str] = []
    seen: set[str] = set()

    for raw_value in raw_values:
        if not raw_value:
            continue
        lowered = re.sub(r"\s+", " ", str(raw_value).strip().lower())
        if not lowered:
            continue

        matches: list[str] = []
        if re.search(r"\b(full[- ]time|full time|permanent|regular)\b", lowered):
            matches.append("full_time")
        if re.search(r"\b(part[- ]time|part time)\b", lowered):
            matches.append("part_time")
        if re.search(r"\b(contract|contractor|freelance|consultant)\b", lowered):
            matches.append("contract")
        if re.search(r"\b(intern|internship|trainee)\b", lowered):
            matches.append("internship")

        normalized_direct = normalize_employment_type(lowered)
        if normalized_direct in EMPLOYMENT_TYPE_CANONICAL:
            matches.append(normalized_direct)

        for match in matches:
            if match not in seen:
                seen.add(match)
                extracted.append(match)

    return extracted or None


def infer_seniority(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().lower()
    for synonym, canonical in SENIORITY_LEVELS.items():
        if re.search(rf"\b{re.escape(synonym)}\b", normalized):
            return canonical
    return None


def parse_partial_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.strip()
    if not text:
        return None
    if looks_current(text):
        return None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        year, month, day = map(int, text.split("-"))
        return safe_date(year, month, day)
    if re.fullmatch(r"\d{4}-\d{2}", text):
        year, month = map(int, text.split("-"))
        return safe_date(year, month, 1)
    if re.fullmatch(r"\d{4}", text):
        return safe_date(int(text), 1, 1)
    return None


def compute_duration_months(
    *,
    start_date: date | None,
    end_date: date | None,
    is_current: bool,
) -> int | None:
    if not start_date:
        return None
    effective_end = date.today() if is_current else end_date
    if not effective_end:
        return None
    months = (effective_end.year - start_date.year) * 12 + (
        effective_end.month - start_date.month
    )
    return max(months, 0)


def looks_current(value: str | None) -> bool:
    if not value:
        return False
    return value.strip().lower() in {"present", "current", "now", "oggi", "attuale"}


def safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None
