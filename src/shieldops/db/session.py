"""Async database session management."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine as _create_engine,
)


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def create_async_engine(database_url: str, pool_size: int = 20) -> AsyncEngine:
    """Create and cache the async SQLAlchemy engine."""
    global _engine, _session_factory
    _engine = _create_engine(
        database_url,
        pool_size=pool_size,
        max_overflow=10,
        echo=False,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the cached session factory."""
    if _session_factory is None:
        raise RuntimeError("Database engine not initialized. Call create_async_engine() first.")
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """Async generator yielding a database session (for FastAPI Depends)."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
