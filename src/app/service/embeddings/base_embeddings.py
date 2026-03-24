from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List


class BaseEmbeddings(ABC):
    """Абстрактные embeddings: обязан выдать список float."""

    @abstractmethod
    async def aembed_documents(self, texts: List[str]) -> List[List[float]]:
        raise NotImplementedError

    @abstractmethod
    async def aembed_query(self, text: str) -> List[float]:
        raise NotImplementedError
