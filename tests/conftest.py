"""pytest 全局 fixtures。"""

from collections.abc import AsyncGenerator

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from myapp.config import Settings
from myapp.main import create_app


@pytest.fixture
def test_settings() -> Settings:
    """测试环境配置。"""
    return Settings(
        app_env="test",
        debug=False,
        database_url="sqlite+aiosqlite:///:memory:",
        otel_enabled=False,
    )


@pytest.fixture
async def app(test_settings: Settings):
    """FastAPI 测试应用（通过 LifespanManager 触发 lifespan）。"""
    application = create_app(test_settings)
    async with LifespanManager(application):
        yield application


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """异步 HTTP 测试客户端。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
