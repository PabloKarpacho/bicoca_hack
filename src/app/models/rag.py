from io import BytesIO

from pydantic import BaseModel, HttpUrl


class SearchPayload(BaseModel):
    file_id: str | None = None
    page_content: str | None = None
    page_number: int | None = None
    file_description: str | None = None


class SearchResponse(BaseModel):
    payload: SearchPayload
    score: float


class NamedBuffer(BaseModel):
    filename: str
    buf: BytesIO

    model_config = {"arbitrary_types_allowed": True}


class IngestFileResponse(BaseModel):
    file_id: str


class DeleteFileResponse(BaseModel):
    file_id: str
    deleted: bool = True


class FileUploadStatusResponse(BaseModel):
    file_id: str
    status: str


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


class SearchPayloadRequest(BaseModel):
    query: str
    url: HttpUrl | None = None
