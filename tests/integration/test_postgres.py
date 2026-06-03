"""使用 testcontainers 的 PostgreSQL 集成测试。"""

import pytest
from httpx import ASGITransport, AsyncClient
from testcontainers.postgres import PostgresContainer

from myapp.config import Settings
from myapp.db.session import create_engine, create_session_factory, init_db
from myapp.main import create_app


def _to_asyncpg_url(raw_url: str) -> str:
    """将 testcontainers 返回的 URL 转为 asyncpg 驱动。"""
    if "+asyncpg" in raw_url:
        return raw_url
    if raw_url.startswith("postgresql+psycopg2://"):
        return raw_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
    if raw_url.startswith("postgresql://"):
        return raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return raw_url


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_integration_crud() -> None:
    """在真实 PostgreSQL 容器中验证 CRUD 流程。"""
    with PostgresContainer("postgres:16-alpine") as postgres:
        async_url = _to_asyncpg_url(postgres.get_connection_url())

        settings = Settings(app_env="test", database_url=async_url, otel_enabled=False)
        engine = create_engine(settings)
        await init_db(engine)
        session_factory = create_session_factory(engine)

        app = create_app(settings)
        app.state.engine = engine
        app.state.session_factory = session_factory

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/items", json={"name": "PG Item", "description": "from tc"}
            )
            assert response.status_code == 201
            assert response.json()["data"]["name"] == "PG Item"

        await engine.dispose()
