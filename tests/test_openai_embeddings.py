import pytest

from app.service.embeddings.openai.openai_embeddings import OpenAIEmbeddings


class FakeLangChainEmbeddings:
    def __init__(self) -> None:
        self.document_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls.append(texts)
        return [[0.1, 0.2] for _ in texts]

    async def aembed_query(self, text: str) -> list[float]:
        self.query_calls.append(text)
        return [0.3, 0.4]


@pytest.mark.asyncio
async def test_openai_embeddings_delegate_async_calls() -> None:
    embeddings = OpenAIEmbeddings(
        api_key="test-key",
        base_url="https://api.openai.com/v1/",
        model="text-embedding-3-small",
    )
    fake_client = FakeLangChainEmbeddings()
    embeddings.client = fake_client

    document_vectors = await embeddings.aembed_documents(["a", "b"])
    query_vector = await embeddings.aembed_query("hello")

    assert document_vectors == [[0.1, 0.2], [0.1, 0.2]]
    assert query_vector == [0.3, 0.4]
    assert fake_client.document_calls == [["a", "b"]]
    assert fake_client.query_calls == ["hello"]


def test_openai_embeddings_normalize_base_url() -> None:
    embeddings = OpenAIEmbeddings(
        api_key="test-key",
        base_url="https://api.openai.com/v1/",
        model="text-embedding-3-small",
    )

    assert embeddings.base_url == "https://api.openai.com/v1"
