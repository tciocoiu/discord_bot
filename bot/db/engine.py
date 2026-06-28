from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from bot.config import Config, sqlite_db_path
from bot.db.models import Base

_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_db(config: Config) -> None:
    global _engine, _session_factory

    connect_args: dict = {}
    if config.database_url.startswith("sqlite"):
        db_path = sqlite_db_path(config.database_url)
        if db_path is not None:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        connect_args["timeout"] = 30
    elif config.database_url.startswith("postgresql"):
        # Railway private network (.railway.internal) does not use SSL
        if "railway.internal" not in config.database_url:
            connect_args["ssl"] = "require"

    _engine = create_async_engine(
        config.database_url,
        echo=False,
        connect_args=connect_args,
    )
    _session_factory = async_sessionmaker(_engine, expire_on_commit=False)


async def create_tables() -> None:
    if _engine is None:
        raise RuntimeError("Database not initialized")
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    if _session_factory is None:
        raise RuntimeError("Database not initialized")
    async with _session_factory() as session:
        yield session


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Database not initialized")
    return _session_factory
