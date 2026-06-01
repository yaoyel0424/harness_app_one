"""组合根：FastAPI 依赖注入（允许跨层 wiring）。"""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from myapp.config import Settings, get_settings
from myapp.core.services.external_service import ExternalService
from myapp.core.services.item_service import ItemService
from myapp.db.repositories.item_repository import ItemRepository
from myapp.db.session import get_session
from myapp.utils.http_client import HttpClient


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    """从应用状态获取会话工厂。"""
    factory: async_sessionmaker[AsyncSession] = request.app.state.session_factory
    return factory


async def get_db_session(
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> AsyncGenerator[AsyncSession, None]:
    """提供数据库会话依赖。"""
    async for session in get_session(session_factory):
        yield session


def get_item_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ItemService:
    """提供 Item 业务服务。"""
    return ItemService(ItemRepository(session))


def get_http_client(settings: Annotated[Settings, Depends(get_settings)]) -> HttpClient:
    """提供 HTTP 客户端。"""
    _ = settings
    return HttpClient(base_url="https://api.quotable.io")


def get_external_service(
    http_client: Annotated[HttpClient, Depends(get_http_client)],
) -> ExternalService:
    """提供外部 API 业务服务。"""
    return ExternalService(http_client)
