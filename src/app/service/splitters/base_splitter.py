from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List
from langchain_core.documents import Document


class BaseSplitter(ABC):
    """Абстрактный loader: обязан выдать список Document."""

    @abstractmethod
    def split(self) -> List[Document]:
        raise NotImplementedError
