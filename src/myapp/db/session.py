"""数据库连接与会话管理。"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from myapp.config import Settings
from myapp.db.models import Base


def create_engine(settings: Settings) -> AsyncEngine:
    """创建异步数据库引擎。"""
    return create_async_engine(
        settings.database_url,
        echo=settings.debug,
        pool_pre_ping=True,
    )


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """创建异步会话工厂。"""
    return async_sessionmaker(engine, expire_on_commit=False)


async def init_db(engine: AsyncEngine) -> None:
    """初始化数据库表结构（开发/测试用）。"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncGenerator[AsyncSession, None]:
    """FastAPI 依赖: 提供数据库会话。"""
    async with session_factory() as session:
        yield session
