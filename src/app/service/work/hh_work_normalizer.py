from __future__ import annotations

import re
from dataclasses import dataclass

import httpx
from loguru import logger

from app.config.config import settings
from app.models.work_normalization import HHWorkNormalizationResult, HHWorkSuggestion
from app.service.skills.hh_skill_normalizer import InMemoryTTLCache

CYRILLIC_RE = re.compile(r"[А-Яа-яЁё]")


class HHWorkAutosuggestClientError(RuntimeError):
    pass


DEFAULT_HH_WORK_CACHE = InMemoryTTLCache[HHWorkNormalizationResult](
    ttl_seconds=settings.hh_autosuggest_cache_ttl_seconds
)


class HHWorkAutosuggestClient:
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

    async def autosuggest(self, raw_work: str) -> list[HHWorkSuggestion]:
        headers = {"User-Agent": self.user_agent}
        params = {"q": raw_work}
        url = f"{self.base_url}/shards/autosuggest/professions"

        try:
            async with httpx.AsyncClient(
                headers=headers,
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.get(url, params=params)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise HHWorkAutosuggestClientError(
                "HH work autosuggest request timed out"
            ) from exc
        except httpx.HTTPStatusError as exc:
            raise HHWorkAutosuggestClientError(
                f"HH work autosuggest request failed with status {exc.response.status_code}"
            ) from exc
        except httpx.HTTPError as exc:
            raise HHWorkAutosuggestClientError(
                "HH work autosuggest request failed due to network error"
            ) from exc

        payload = response.json()
        logger.debug(
            "HH work autosuggest response raw_work={raw_work}, payload={payload}",
            raw_work=raw_work,
            payload=payload,
        )
        items = payload.get("items", [])
        suggestions: list[HHWorkSuggestion] = []
        for item in items:
            try:
                suggestion = HHWorkSuggestion.model_validate(item)
            except Exception:
                continue
            if _contains_cyrillic(suggestion.text):
                continue
            suggestions.append(suggestion)
        logger.debug(
            "HH work autosuggest parsed raw_work={raw_work}, suggestions={suggestions}",
            raw_work=raw_work,
            suggestions=[suggestion.model_dump() for suggestion in suggestions],
        )
        return suggestions


@dataclass(slots=True)
class HHWorkNormalizerService:
    client: HHWorkAutosuggestClient | None = None
    cache: InMemoryTTLCache[HHWorkNormalizationResult] | None = None
    enabled: bool = settings.hh_autosuggest_enabled
    max_items_to_consider: int = settings.hh_autosuggest_max_items_to_consider
    min_confidence_threshold: float = settings.hh_autosuggest_min_confidence_threshold

    def __post_init__(self) -> None:
        self.client = self.client or HHWorkAutosuggestClient()
        self.cache = self.cache or DEFAULT_HH_WORK_CACHE

    async def normalize_work(self, raw_work: str | None) -> HHWorkNormalizationResult:
        normalized_input = _clean_work(raw_work)
        logger.info(
            "HH work normalization: start raw_work={raw_work}",
            raw_work=normalized_input,
        )
        if not normalized_input:
            return HHWorkNormalizationResult(
                raw_work="",
                match_type="no_match",
                confidence=0.0,
            )

        if not self.enabled:
            return HHWorkNormalizationResult(
                raw_work=normalized_input,
                match_type="disabled",
                confidence=0.0,
            )

        cache_key = _cache_key(normalized_input)
        cached = self.cache.get(cache_key)
        if cached is not None:
            logger.info(
                "HH work normalization: cache hit raw_work={raw_work}, match_type={match_type}",
                raw_work=normalized_input,
                match_type=cached.match_type,
            )
            return cached

        try:
            suggestions = await self.client.autosuggest(normalized_input)
        except HHWorkAutosuggestClientError as exc:
            logger.warning(
                "HH work normalization: request failed raw_work={raw_work}, error={error}",
                raw_work=normalized_input,
                error=str(exc),
            )
            return HHWorkNormalizationResult(
                raw_work=normalized_input,
                match_type="error",
                confidence=0.0,
                error=str(exc),
            )

        result = self._select_best_match(normalized_input, suggestions)
        if result.match_type in {"exact", "prefix", "top_result", "no_match"}:
            self.cache.set(cache_key, result)
        return result

    async def suggest_works(self, raw_work: str | None) -> list[HHWorkSuggestion]:
        normalized_input = _clean_work(raw_work)
        if not normalized_input or not self.enabled:
            return []
        try:
            suggestions = await self.client.autosuggest(normalized_input)
        except HHWorkAutosuggestClientError as exc:
            logger.warning(
                "HH work suggestions: request failed raw_work={raw_work}, error={error}",
                raw_work=normalized_input,
                error=str(exc),
            )
            return []

        unique: list[HHWorkSuggestion] = []
        seen_ids: set[int] = set()
        seen_texts: set[str] = set()
        for suggestion in suggestions[: self.max_items_to_consider]:
            normalized_text = _match_key(suggestion.text)
            if suggestion.id in seen_ids or normalized_text in seen_texts:
                continue
            seen_ids.add(suggestion.id)
            seen_texts.add(normalized_text)
            unique.append(suggestion)
        return unique

    def _select_best_match(
        self,
        raw_work: str,
        suggestions: list[HHWorkSuggestion],
    ) -> HHWorkNormalizationResult:
        considered = suggestions[: self.max_items_to_consider]
        if not considered:
            return HHWorkNormalizationResult(
                raw_work=raw_work,
                match_type="no_match",
                confidence=0.0,
                alternatives=[],
            )

        normalized_query = _match_key(raw_work)
        exact = next(
            (item for item in considered if _match_key(item.text) == normalized_query),
            None,
        )
        if exact is not None:
            return self._build_result(
                raw_work=raw_work,
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
                raw_work=raw_work,
                match=prefix,
                match_type="prefix",
                confidence=0.82,
                alternatives=considered,
            )

        top_result = considered[0]
        return self._build_result(
            raw_work=raw_work,
            match=top_result,
            match_type="top_result",
            confidence=0.62,
            alternatives=considered,
        )

    def _build_result(
        self,
        *,
        raw_work: str,
        match: HHWorkSuggestion,
        match_type: str,
        confidence: float,
        alternatives: list[HHWorkSuggestion],
    ) -> HHWorkNormalizationResult:
        if confidence < self.min_confidence_threshold:
            return HHWorkNormalizationResult(
                raw_work=raw_work,
                match_type="no_match",
                confidence=confidence,
                alternatives=alternatives,
            )
        return HHWorkNormalizationResult(
            raw_work=raw_work,
            normalized_work_text=match.text,
            normalized_work_external_id=match.id,
            match_type=match_type,
            confidence=confidence,
            alternatives=alternatives,
        )


def _clean_work(value: str | None) -> str:
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
