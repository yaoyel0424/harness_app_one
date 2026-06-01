"""使用 testcontainers 的 PostgreSQL 集成测试。"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.postgres import PostgresContainer

from myapp.config import Settings
from myapp.db.session import create_session_factory, init_db
from myapp.main import create_app


@pytest.mark.integration
@pytest.mark.asyncio
async def test_postgres_integration_crud() -> None:
    """在真实 PostgreSQL 容器中验证 CRUD 流程。"""
    with PostgresContainer("postgres:16-alpine") as postgres:
        raw_url = postgres.get_connection_url()
        async_url = raw_url.replace("postgresql://", "postgresql+asyncpg://")

        settings = Settings(app_env="test", database_url=async_url, otel_enabled=False)
        engine = create_async_engine(async_url)
        await init_db(engine)
        session_factory = create_session_factory(engine)

        app = create_app(settings)
        app.state.engine = engine
        app.state.session_factory = session_factory

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/items", json={"name": "PG Item", "description": "from tc"}
            )
            assert response.status_code == 201
            assert response.json()["name"] == "PG Item"

        await engine.dispose()
