import asyncio
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import create_app
from app.service.cv.storage import CVStorageService
from database.postgres.db import get_db_session
from database.postgres.schema import Base


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.base_url = "https://fake-s3.local"

    async def create_bucket(self, bucket_name: str) -> None:
        return None

    async def upload_bytes(
        self,
        data: bytes,
        key: str,
        bucket_name: str,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> None:
        self.objects[f"{bucket_name}/{key}"] = data

    async def delete_file(
        self,
        key: str,
        bucket_name: str,
    ) -> None:
        self.objects.pop(f"{bucket_name}/{key}", None)

    async def generate_presigned_download_url(
        self,
        *,
        key: str,
        bucket_name: str,
        url_expiry: int = 3600,
    ) -> str:
        return (
            f"{self.base_url}/{bucket_name}/{key}"
            f"?expires_in={url_expiry}"
        )


class FakeQdrant:
    def __init__(self) -> None:
        self.collections: dict[str, dict[str, dict]] = {}

    async def create_collection(
        self,
        collection_name: str,
        vector_size: int,
        metadata: dict | None = None,
    ) -> None:
        self.collections.setdefault(collection_name, {})

    async def delete_vectors_by_document_id(
        self,
        collection_name: str,
        document_id: str,
    ) -> None:
        collection = self.collections.setdefault(collection_name, {})
        for point_id in [
            key
            for key, value in collection.items()
            if value["payload"].get("document_id") == document_id
        ]:
            collection.pop(point_id, None)

    async def upsert_points(self, collection_name: str, points: list[dict]) -> None:
        collection = self.collections.setdefault(collection_name, {})
        for point in points:
            collection[point["id"]] = {
                "vector": point["vector"],
                "payload": point["payload"],
            }

    async def delete_points_by_ids(self, collection_name: str, point_ids: list[str]) -> None:
        collection = self.collections.setdefault(collection_name, {})
        for point_id in point_ids:
            collection.pop(point_id, None)

    async def search_points(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int,
        candidate_ids: list[str] | None = None,
        chunk_types: list[str] | None = None,
        score_threshold: float = 0.0,
    ) -> list[dict]:
        return []


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture
async def db_sessionmaker():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    yield maker
    await engine.dispose()


@pytest_asyncio.fixture
async def app(db_sessionmaker) -> AsyncIterator[FastAPI]:
    application = create_app()
    application.state.db_sessionmaker = db_sessionmaker
    application.state.s3 = FakeS3()
    application.state.qdrant = FakeQdrant()
    application.state.cv_storage = CVStorageService(s3=application.state.s3)

    async def override_get_db_session():
        async with db_sessionmaker() as session:
            yield session

    application.dependency_overrides[get_db_session] = override_get_db_session
    yield application
