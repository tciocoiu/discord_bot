import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///data/loot.db"


@dataclass(frozen=True)
class Config:
    discord_token: str
    database_url: str
    base_weight: float
    bad_luck_weight: float
    activity_weight: float


def _normalize_database_url(url: str) -> str:
    if url.startswith("sqlite:///") and "+aiosqlite" not in url:
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url


def sqlite_db_path(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite"):
        return None
    return Path(database_url.split("///", 1)[-1])


def load_config() -> Config:
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise RuntimeError("DISCORD_TOKEN environment variable is required")

    database_url = _normalize_database_url(
        os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    )

    return Config(
        discord_token=token,
        database_url=database_url,
        base_weight=float(os.getenv("BASE_WEIGHT", "1.0")),
        bad_luck_weight=float(os.getenv("BAD_LUCK_WEIGHT", "0.5")),
        activity_weight=float(os.getenv("ACTIVITY_WEIGHT", "0.1")),
    )
