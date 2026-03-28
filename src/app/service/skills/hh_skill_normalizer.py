from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Generic, TypeVar

import httpx
from loguru import logger

from app.config.config import settings
from app.models.skill_normalization import HHSkillNormalizationResult, HHSkillSuggestion

CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")


class HHSkillAutosuggestClientError(RuntimeError):
    pass


CacheValueT = TypeVar("CacheValueT")


@dataclass(slots=True)
class InMemoryTTLCache(Generic[CacheValueT]):
    ttl_seconds: int
    _store: dict[str, tuple[float, CacheValueT]] = field(default_factory=dict)

    def get(self, key: str) -> CacheValueT | None:
        now = time.monotonic()
        value = self._store.get(key)
        if value is None:
            return None
        expires_at, result = value
        if expires_at <= now:
            self._store.pop(key, None)
            return None
        return result

    def set(self, key: str, value: CacheValueT) -> None:
        self._store[key] = (time.monotonic() + self.ttl_seconds, value)


DEFAULT_HH_SKILL_CACHE = InMemoryTTLCache(
    ttl_seconds=settings.hh_autosuggest_cache_ttl_seconds
)


class HHSkillAutosuggestClient:
    def __init__(
        self,
        *,
        base_url: str = settings.hh_autosuggest_base_url,
        timeout_seconds: int = settings.hh_autosuggest_timeout_seconds,
        user_agent: str = settings.hh_autosuggest_user_agent,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent
        self.transport = transport

    async def autosuggest(self, raw_skill: str) -> list[HHSkillSuggestion]:
        headers = {"User-Agent": self.user_agent}
        params = {"q": raw_skill, "d": "key_skill"}
        url = f"{self.base_url}/autosuggest/multiprefix/v2"

        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.get(url, params=params)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise HHSkillAutosuggestClientError(
                "HH autosuggest request timed out"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise HHSkillAutosuggestClientError(
                f"HH autosuggest request failed with status {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise HHSkillAutosuggestClientError(
                "HH autosuggest request failed due to network error"
            ) from exc

        payload = response.json()
        logger.debug(
            "HH skill autosuggest response raw_skill={raw_skill}, payload={payload}",
            raw_skill=raw_skill,
            payload=payload,
        )
        items = payload.get("items", [])
        suggestions: list[HHSkillSuggestion] = []
        for item in items:
            try:
                suggestion = HHSkillSuggestion.model_validate(item)
            except Exception:
                continue
            if _contains_cyrillic(suggestion.text):
                continue
            suggestions.append(suggestion)
        logger.debug(
            "HH skill autosuggest parsed raw_skill={raw_skill}, suggestions={suggestions}",
            raw_skill=raw_skill,
            suggestions=[suggestion.model_dump() for suggestion in suggestions],
        )
        return suggestions


class HHSkillNormalizerService:
    def __init__(
        self,
        *,
        client: HHSkillAutosuggestClient | None = None,
        cache: InMemoryTTLCache | None = None,
        enabled: bool = settings.hh_autosuggest_enabled,
        max_items_to_consider: int = settings.hh_autosuggest_max_items_to_consider,
        min_confidence_threshold: float = settings.hh_autosuggest_min_confidence_threshold,
    ) -> None:
        self.client = client or HHSkillAutosuggestClient()
        self.cache = cache or DEFAULT_HH_SKILL_CACHE
        self.enabled = enabled
        self.max_items_to_consider = max_items_to_consider
        self.min_confidence_threshold = min_confidence_threshold

    async def normalize_skill(
        self, raw_skill: str | None
    ) -> HHSkillNormalizationResult:
        normalized_input = _clean_skill(raw_skill)
        logger.info(
            "HH skill normalization: start raw_skill={raw_skill}",
            raw_skill=normalized_input,
        )
        if not normalized_input:
            return HHSkillNormalizationResult(
                raw_skill="",
                match_type="no_match",
                confidence=0.0,
            )

        if not self.enabled:
            logger.info(
                "HH skill normalization: disabled raw_skill={raw_skill}",
                raw_skill=normalized_input,
            )
            return HHSkillNormalizationResult(
                raw_skill=normalized_input,
                match_type="disabled",
                confidence=0.0,
            )

        cache_key = _cache_key(normalized_input)
        cached = self.cache.get(cache_key)
        if cached is not None:
            logger.info(
                "HH skill normalization: cache hit raw_skill={raw_skill}, match_type={match_type}",
                raw_skill=normalized_input,
                match_type=cached.match_type,
            )
            return cached
        logger.info(
            "HH skill normalization: cache miss raw_skill={raw_skill}",
            raw_skill=normalized_input,
        )

        try:
            suggestions = await self.client.autosuggest(normalized_input)
            logger.info(
                "HH skill normalization: request success raw_skill={raw_skill}, items_count={items_count}",
                raw_skill=normalized_input,
                items_count=len(suggestions),
            )
        except HHSkillAutosuggestClientError as exc:
            logger.warning(
                "HH skill normalization: request failed raw_skill={raw_skill}, error={error}",
                raw_skill=normalized_input,
                error=str(exc),
            )
            return HHSkillNormalizationResult(
                raw_skill=normalized_input,
                match_type="error",
                confidence=0.0,
                error=str(exc),
            )

        result = self._select_best_match(normalized_input, suggestions)
        if result.match_type in {"exact", "prefix", "top_result", "no_match"}:
            self.cache.set(cache_key, result)
        logger.info(
            "HH skill normalization: selected match raw_skill={raw_skill}, match_type={match_type}, confidence={confidence}",
            raw_skill=normalized_input,
            match_type=result.match_type,
            confidence=result.confidence,
        )
        return result

    async def suggest_skills(self, raw_skill: str | None) -> list[HHSkillSuggestion]:
        normalized_input = _clean_skill(raw_skill)
        logger.info(
            "HH skill suggestions: start raw_skill={raw_skill}",
            raw_skill=normalized_input,
        )
        if not normalized_input or not self.enabled:
            return []

        try:
            suggestions = await self.client.autosuggest(normalized_input)
        except HHSkillAutosuggestClientError as exc:
            logger.warning(
                "HH skill suggestions: request failed raw_skill={raw_skill}, error={error}",
                raw_skill=normalized_input,
                error=str(exc),
            )
            return []

        unique: list[HHSkillSuggestion] = []
        seen_ids: set[int] = set()
        seen_texts: set[str] = set()
        for suggestion in suggestions[: self.max_items_to_consider]:
            normalized_text = _match_key(suggestion.text)
            if suggestion.id in seen_ids or normalized_text in seen_texts:
                continue
            seen_ids.add(suggestion.id)
            seen_texts.add(normalized_text)
            unique.append(suggestion)
        logger.info(
            "HH skill suggestions: completed raw_skill={raw_skill}, suggestions_count={count}",
            raw_skill=normalized_input,
            count=len(unique),
        )
        return unique

    def _select_best_match(
        self,
        raw_skill: str,
        suggestions: list[HHSkillSuggestion],
    ) -> HHSkillNormalizationResult:
        considered = suggestions[: self.max_items_to_consider]
        if not considered:
            return HHSkillNormalizationResult(
                raw_skill=raw_skill,
                match_type="no_match",
                confidence=0.0,
                alternatives=[],
            )

        normalized_query = _match_key(raw_skill)
        exact = next(
            (item for item in considered if _match_key(item.text) == normalized_query),
            None,
        )
        if exact is not None:
            return self._build_result(
                raw_skill=raw_skill,
                match=exact,
                match_type="exact",
                confidence=0.99,
                alternatives=considered,
            )

        prefix = next(
            (
                item
                for item in considered
                if _match_key(item.text).startswith(normalized_query)
                or normalized_query.startswith(_match_key(item.text))
            ),
            None,
        )
        if prefix is not None:
            return self._build_result(
                raw_skill=raw_skill,
                match=prefix,
                match_type="prefix",
                confidence=0.82,
                alternatives=considered,
            )

        top_result = considered[0]
        return self._build_result(
            raw_skill=raw_skill,
            match=top_result,
            match_type="top_result",
            confidence=0.62,
            alternatives=considered,
        )

    def _build_result(
        self,
        *,
        raw_skill: str,
        match: HHSkillSuggestion,
        match_type: str,
        confidence: float,
        alternatives: list[HHSkillSuggestion],
    ) -> HHSkillNormalizationResult:
        if confidence < self.min_confidence_threshold:
            return HHSkillNormalizationResult(
                raw_skill=raw_skill,
                match_type="no_match",
                confidence=confidence,
                alternatives=alternatives,
            )
        return HHSkillNormalizationResult(
            raw_skill=raw_skill,
            normalized_skill_text=match.text,
            normalized_skill_external_id=match.id,
            match_type=match_type,
            confidence=confidence,
            alternatives=alternatives,
        )


def _clean_skill(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def _cache_key(value: str) -> str:
    return _match_key(value)


def _match_key(value: str) -> str:
    normalized = value.strip().lower()
    normalized = re.sub(r"[_/]+", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _contains_cyrillic(value: str) -> bool:
    return bool(CYRILLIC_RE.search(value))
