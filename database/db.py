import os
from typing import AsyncGenerator
from dotenv import load_dotenv

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from sqlalchemy import text

load_dotenv()

# We get the database URL from environment or fallback to default SQLite
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///barbercrm.db")

# Create the async engine
engine = create_async_engine(DATABASE_URL, echo=False)

# Create an async session factory
async_session_maker = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db(base=None):
    """
    Initialize the database by creating all tables.
    If base is None, imports Base from models automatically.
    """
    if base is None:
        from database.models import Base
        base = Base
    async with engine.begin() as conn:
        await conn.run_sync(base.metadata.create_all)

        # Lightweight auto-migrations for existing SQLite DBs
        if str(engine.url).startswith("sqlite"):
            await conn.run_sync(_run_sqlite_migrations)


def _run_sqlite_migrations(sync_conn):
    """Idempotent SQLite schema upgrades for existing databases."""

    def _table_columns(table_name: str) -> set[str]:
        rows = sync_conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        # PRAGMA table_info: cid, name, type, notnull, dflt_value, pk
        return {r[1] for r in rows}

    def _add_column_if_missing(table: str, column: str, ddl: str):
        cols = _table_columns(table)
        if column in cols:
            return
        sync_conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))

    # users
    try:
        _add_column_if_missing("users", "birthday", "birthday DATE")
        _add_column_if_missing(
            "users",
            "birthday_notified_this_year",
            "birthday_notified_this_year BOOLEAN NOT NULL DEFAULT 0",
        )
        _add_column_if_missing(
            "users",
            "language",
            "language VARCHAR(10) NOT NULL DEFAULT 'uz'",
        )
    except Exception:
        # If table doesn't exist yet or migration fails, ignore.
        pass

    # appointments
    try:
        _add_column_if_missing(
            "appointments",
            "cancellation_reason",
            "cancellation_reason VARCHAR(256)",
        )
        _add_column_if_missing(
            "appointments",
            "cancelled_by",
            "cancelled_by VARCHAR(20)",
        )
    except Exception:
        pass


async def close_db():
    """
    Dispose of the database engine.
    """
    await engine.dispose()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async generator yielding a database session.
    Useful for dependency injection or context managers.
    """
    async with async_session_maker() as session:
        yield session
