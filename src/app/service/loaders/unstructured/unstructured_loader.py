from typing import List
from pydantic import HttpUrl

from langchain_unstructured import UnstructuredLoader as unstructured_converter
from langchain_core.documents import Document

from app.service.loaders.base_loader import BaseLoader
from app.service.loaders.unstructured.tools import parse_to_markdown
from app.config.llm_config import llm_settings
from app.models.rag import NamedBuffer


class UnstructuredLoader(BaseLoader):
    def __init__(self, file_source: NamedBuffer | HttpUrl) -> None:
        """
        Initialize UnstructuredLoader.
        """
        self.file_source = file_source

        api_key = llm_settings.unstructured_api_key

        if not api_key:
            raise ValueError("settings.unstructured_api_key is not set")

        loader_kwargs: dict = {
            "api_key": api_key,
            "partition_via_api": True,
            "strategy": "hi_res",
            "extract_image_block_types": ["Image", "Table"],
            "include_page_breaks": True,
        }

        if isinstance(file_source, NamedBuffer):
            loader_kwargs["file"] = file_source.buf
            self.converter = unstructured_converter(**loader_kwargs)
        elif isinstance(file_source, HttpUrl):
            loader_kwargs["web_url"] = str(file_source)
            loader_kwargs["partition_via_api"] = (
                False  # При загруке URL через API падает ошибка
            )
            self.converter = unstructured_converter(**loader_kwargs)
        else:
            raise ValueError(
                f"file_source argument type: {type(file_source)} is not supported"
            )

    def load_raw_documents(self) -> List[Document]:
        """Load raw unstructured elements before markdown normalization."""
        if isinstance(self.file_source, NamedBuffer):
            self.file_source.buf.seek(0)
        return self.converter.load()

    async def load(self) -> List[Document]:
        """
        Load documents using UnstructuredLoader.

        Returns:
            List of Document objects
        """
        documents = self.load_raw_documents()

        # Convert to markdown
        markdown_content = await parse_to_markdown(
            documents=documents,
        )

        pages = markdown_content.split("<!-- page break -->")

        result = [
            Document(
                page_content=page_content,
                metadata={"page_number": idx},
            )
            for idx, page_content in enumerate(pages, start=1)
        ]

        return result
