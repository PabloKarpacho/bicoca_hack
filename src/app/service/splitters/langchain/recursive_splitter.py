from loguru import logger
from typing import List
from collections.abc import Callable
from app.service.splitters.base_splitter import BaseSplitter
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


class RecursiveSplitter(BaseSplitter):
    def __init__(
        self,
        chunk_size: int = 300,
        chunk_overlap: int = 50,
        length_function: Callable[[str], int] = len,
    ) -> None:
        """
        Initialize RecursiveCharacterTextSplitter.
        """
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=length_function,
        )

    def split(self, documents: List[Document]) -> List[Document]:
        """
        Split a document using RecursiveCharacterTextSplitter.
        """
        logger.info("Splitting documents using RecursiveCharacterTextSplitter")

        splits = self.splitter.split_documents(documents)

        return splits
