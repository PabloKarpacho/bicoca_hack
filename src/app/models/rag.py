from io import BytesIO

from pydantic import BaseModel, Field


class SearchPayload(BaseModel):
    file_id: str | None = Field(default=None, description="Document or file identifier associated with the payload item.")
    page_content: str | None = Field(default=None, description="Extracted page or chunk text content.")
    page_number: int | None = Field(default=None, description="Page number associated with the payload item, when available.")
    file_description: str | None = Field(default=None, description="Optional human-readable description of the source file.")


class SearchResponse(BaseModel):
    payload: SearchPayload = Field(description="Payload returned for the search result item.")
    score: float = Field(description="Search relevance score for the payload item.")


class NamedBuffer(BaseModel):
    filename: str = Field(description="Filename associated with the in-memory buffer.")
    buf: BytesIO = Field(description="In-memory binary buffer.")

    model_config = {"arbitrary_types_allowed": True}


class DeleteFileResponse(BaseModel):
    file_id: str = Field(description="Deleted file identifier.")
    deleted: bool = Field(default=True, description="Whether deletion succeeded.")


class SearchRequest(BaseModel):
    query: str = Field(description="Search query text.")
    limit: int = Field(default=5, description="Maximum number of results to return.")
