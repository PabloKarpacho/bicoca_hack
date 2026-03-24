import pytest
import httpx

from app.models.work_normalization import HHWorkNormalizationResult, HHWorkSuggestion
from app.service.work.hh_work_normalizer import (
    HHWorkAutosuggestClient,
    HHWorkAutosuggestClientError,
    HHWorkNormalizerService,
)
from app.service.skills.hh_skill_normalizer import InMemoryTTLCache


@pytest.mark.asyncio
async def test_hh_work_normalizer_exact_match() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "items": [
                    {"id": 1, "text": "Data Engineer"},
                    {"id": 2, "text": "Data Analyst"},
                ]
            },
        )
    )
    service = HHWorkNormalizerService(
        client=HHWorkAutosuggestClient(transport=transport),
        cache=InMemoryTTLCache(ttl_seconds=60),
    )

    result = await service.normalize_work("Data Engineer")

    assert result.match_type == "exact"
    assert result.normalized_work_text == "Data Engineer"
    assert result.normalized_work_external_id == 1
    assert result.confidence == 0.99


@pytest.mark.asyncio
async def test_hh_work_normalizer_empty_items_response() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"items": []})
    )
    service = HHWorkNormalizerService(
        client=HHWorkAutosuggestClient(transport=transport),
        cache=InMemoryTTLCache(ttl_seconds=60),
    )

    result = await service.normalize_work("Unknown Profession")

    assert result.match_type == "no_match"
    assert result.normalized_work_text is None


@pytest.mark.asyncio
async def test_hh_work_normalizer_filters_out_cyrillic_suggestions() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "items": [
                    {"id": 1, "text": "Дата инженер"},
                    {"id": 2, "text": "Data Engineer"},
                ]
            },
        )
    )
    service = HHWorkNormalizerService(
        client=HHWorkAutosuggestClient(transport=transport),
        cache=InMemoryTTLCache(ttl_seconds=60),
    )

    result = await service.normalize_work("Data Engineer")
    suggestions = await service.suggest_works("Data")

    assert result.normalized_work_text == "Data Engineer"
    assert suggestions == [HHWorkSuggestion(id=2, text="Data Engineer")]


@pytest.mark.asyncio
async def test_hh_work_client_handles_non_200() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(503, json={"error": "unavailable"})
    )
    client = HHWorkAutosuggestClient(transport=transport)

    with pytest.raises(HHWorkAutosuggestClientError):
        await client.autosuggest("Data")


class TimeoutClient:
    async def autosuggest(self, raw_work: str) -> list[HHWorkSuggestion]:
        raise HHWorkAutosuggestClientError("HH work autosuggest request timed out")


@pytest.mark.asyncio
async def test_hh_work_normalizer_timeout_is_graceful() -> None:
    service = HHWorkNormalizerService(
        client=TimeoutClient(),
        cache=InMemoryTTLCache(ttl_seconds=60),
    )

    result = await service.normalize_work("Data Engineer")

    assert result.match_type == "error"
    assert result.error == "HH work autosuggest request timed out"


class CountingClient:
    def __init__(self) -> None:
        self.calls = 0

    async def autosuggest(self, raw_work: str) -> list[HHWorkSuggestion]:
        self.calls += 1
        return [HHWorkSuggestion(id=10, text="Data Engineer")]


@pytest.mark.asyncio
async def test_hh_work_normalizer_cache_hit_behavior() -> None:
    client = CountingClient()
    service = HHWorkNormalizerService(
        client=client,
        cache=InMemoryTTLCache(ttl_seconds=60),
    )

    first = await service.normalize_work(" Data Engineer ")
    second = await service.normalize_work("data engineer")

    assert first.match_type == "exact"
    assert second.match_type == "exact"
    assert client.calls == 1


class FixedResultNormalizer:
    async def normalize_work(self, raw_work: str | None) -> HHWorkNormalizationResult:
        return HHWorkNormalizationResult(
            raw_work=raw_work or "",
            normalized_work_text="Data Engineer",
            normalized_work_external_id=42,
            match_type="exact",
            confidence=0.99,
            alternatives=[HHWorkSuggestion(id=42, text="Data Engineer")],
        )


@pytest.mark.asyncio
async def test_hh_work_normalizer_can_be_used_as_pipeline_dependency() -> None:
    service = FixedResultNormalizer()

    result = await service.normalize_work("Data")

    assert result.normalized_work_text == "Data Engineer"
    assert result.normalized_work_external_id == 42
