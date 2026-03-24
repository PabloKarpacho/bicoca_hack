from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import asyncio
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from app.config import settings
from database.postgres.schema import Base

db_semaphore = asyncio.Semaphore(150)

async_engine = create_async_engine(
    settings.db_postgres_url_async,
    pool_size=50,
    max_overflow=100,
    pool_timeout=120,
    pool_recycle=1800,
    pool_pre_ping=True,
    echo_pool=settings.debug,
    pool_use_lifo=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


@asynccontextmanager
async def get_db():
    async with db_semaphore:
        async with AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()


async def get_db_session() -> AsyncIterator:
    async with get_db() as session:
        yield session


def get_sessionmaker():
    return AsyncSessionLocal
