from __future__ import annotations

from typing import List

from langchain_openai import OpenAIEmbeddings as LangChainOpenAIEmbeddings
from pydantic import SecretStr

from app.config.llm_config import llm_settings
from app.service.embeddings.base_embeddings import BaseEmbeddings


class OpenAIEmbeddings(BaseEmbeddings):
    def __init__(
        self,
        api_key: str | None = llm_settings.llm_api_key,
        base_url: str = llm_settings.llm_base_url,
        model: str | None = llm_settings.embedding_model_name,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.client = LangChainOpenAIEmbeddings(
            api_key=SecretStr(api_key) if api_key else None,
            base_url=self.base_url,
            model=self.model or "text-embedding-3-small",
        )

    async def aembed_documents(
        self,
        texts: List[str],
    ) -> List[List[float]]:
        return await self.client.aembed_documents(texts)

    async def aembed_query(self, text: str) -> List[float]:
        return await self.client.aembed_query(text)
