from __future__ import annotations

from dataclasses import dataclass

from app.config.llm_config import llm_settings
from app.service.embeddings.base_embeddings import BaseEmbeddings
from app.service.embeddings.openai.openai_embeddings import OpenAIEmbeddings


@dataclass(slots=True)
class CandidateEmbeddingService:
    embeddings: BaseEmbeddings | None = None
    model_version: str | None = llm_settings.embedding_model_name

    def __post_init__(self) -> None:
        if self.embeddings is None:
            self.embeddings = OpenAIEmbeddings()

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return await self.embeddings.aembed_documents(texts)

    async def embed_query(self, text: str) -> list[float]:
        return await self.embeddings.aembed_query(text)
