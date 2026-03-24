from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.config import settings
from app.routers.rag.rag import router as rag_router
from app.service.cv.storage import CVStorageService
from app.service.vector_db.qdrant.qdrant_api import QdrantAPI
from database.postgres.db import AsyncSessionLocal
from database.s3.db import S3


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up CV service")

    app.state.db_sessionmaker = AsyncSessionLocal
    qdrant = QdrantAPI(url=settings.qdrant_url) if settings.qdrant_url else None
    app.state.qdrant = qdrant

    s3 = S3(
        s3_access_key_id=settings.s3_access_key_id,
        s3_secret_access_key=settings.s3_secret_access_key,
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.s3_region_name,
    )
    await s3.create_bucket(bucket_name=settings.s3_files_bucket_name)
    app.state.s3 = s3
    app.state.cv_storage = CVStorageService(s3=s3)

    yield
    logger.info("Shutting down CV service")


def create_app() -> FastAPI:
    app = FastAPI(
        title="CV Processing API",
        lifespan=lifespan,
        docs_url=settings.docs_url,
        redoc_url=settings.redoc_url,
    )
    app.state.db_sessionmaker = AsyncSessionLocal
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"],
        allow_headers=["*"],
    )
    app.include_router(rag_router)

    @app.get("/", tags=["Root"])
    async def root():
        return {"status": "online", "message": "CV Processing API is running"}

    return app


app = create_app()
