import pytest
import httpx

from app.models.skill_normalization import HHSkillNormalizationResult, HHSkillSuggestion
from app.service.skills.hh_skill_normalizer import (
    HHSkillAutosuggestClient,
    HHSkillAutosuggestClientError,
    HHSkillNormalizerService,
    InMemoryTTLCache,
)


@pytest.mark.asyncio
async def test_hh_skill_normalizer_exact_match() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "items": [
                    {"id": 1, "text": "Python"},
                    {"id": 2, "text": "Python Core"},
                ]
            },
        )
    )
    service = HHSkillNormalizerService(
        client=HHSkillAutosuggestClient(transport=transport),
        cache=InMemoryTTLCache(ttl_seconds=60),
    )

    result = await service.normalize_skill("Python")

    assert result.match_type == "exact"
    assert result.normalized_skill_text == "Python"
    assert result.normalized_skill_external_id == 1
    assert result.confidence == 0.99


@pytest.mark.asyncio
async def test_hh_skill_normalizer_empty_items_response() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, json={"items": []})
    )
    service = HHSkillNormalizerService(
        client=HHSkillAutosuggestClient(transport=transport),
        cache=InMemoryTTLCache(ttl_seconds=60),
    )

    result = await service.normalize_skill("Unknown Skill")

    assert result.match_type == "no_match"
    assert result.normalized_skill_text is None


@pytest.mark.asyncio
async def test_hh_skill_normalizer_filters_out_cyrillic_suggestions() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "items": [
                    {"id": 1, "text": "Питон"},
                    {"id": 2, "text": "Python"},
                ]
            },
        )
    )
    service = HHSkillNormalizerService(
        client=HHSkillAutosuggestClient(transport=transport),
        cache=InMemoryTTLCache(ttl_seconds=60),
    )

    result = await service.normalize_skill("Python")
    suggestions = await service.suggest_skills("Py")

    assert result.normalized_skill_text == "Python"
    assert suggestions == [HHSkillSuggestion(id=2, text="Python")]


@pytest.mark.asyncio
async def test_hh_skill_client_handles_non_200() -> None:
    transport = httpx.MockTransport(
        lambda request: httpx.Response(503, json={"error": "unavailable"})
    )
    client = HHSkillAutosuggestClient(transport=transport)

    with pytest.raises(HHSkillAutosuggestClientError):
        await client.autosuggest("Python")


class TimeoutClient:
    async def autosuggest(self, raw_skill: str) -> list[HHSkillSuggestion]:
        raise HHSkillAutosuggestClientError("HH autosuggest request timed out")


@pytest.mark.asyncio
async def test_hh_skill_normalizer_timeout_is_graceful() -> None:
    service = HHSkillNormalizerService(
        client=TimeoutClient(),
        cache=InMemoryTTLCache(ttl_seconds=60),
    )

    result = await service.normalize_skill("Python")

    assert result.match_type == "error"
    assert result.error == "HH autosuggest request timed out"


class CountingClient:
    def __init__(self) -> None:
        self.calls = 0

    async def autosuggest(self, raw_skill: str) -> list[HHSkillSuggestion]:
        self.calls += 1
        return [HHSkillSuggestion(id=10, text="Python")]


@pytest.mark.asyncio
async def test_hh_skill_normalizer_cache_hit_behavior() -> None:
    client = CountingClient()
    service = HHSkillNormalizerService(
        client=client,
        cache=InMemoryTTLCache(ttl_seconds=60),
    )

    first = await service.normalize_skill(" Python ")
    second = await service.normalize_skill("python")

    assert first.match_type == "exact"
    assert second.match_type == "exact"
    assert client.calls == 1


class FixedResultNormalizer:
    async def normalize_skill(self, raw_skill: str | None) -> HHSkillNormalizationResult:
        return HHSkillNormalizationResult(
            raw_skill=raw_skill or "",
            normalized_skill_text="Python",
            normalized_skill_external_id=42,
            match_type="exact",
            confidence=0.99,
            alternatives=[HHSkillSuggestion(id=42, text="Python")],
        )


@pytest.mark.asyncio
async def test_hh_skill_normalizer_can_be_used_as_pipeline_dependency() -> None:
    service = FixedResultNormalizer()

    result = await service.normalize_skill("Py")

    assert result.normalized_skill_text == "Python"
    assert result.normalized_skill_external_id == 42
