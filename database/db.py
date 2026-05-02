import os
from typing import AsyncGenerator
from dotenv import load_dotenv

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

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
