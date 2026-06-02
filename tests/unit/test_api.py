"""API 层单元测试。"""

import pytest
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from myapp.config import Settings
from myapp.main import create_app


@pytest.mark.asyncio
async def test_liveness(client: AsyncClient) -> None:
    """存活探针应返回 alive。"""
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "alive"


@pytest.mark.asyncio
async def test_readiness(client: AsyncClient) -> None:
    """就绪探针在数据库可用时应返回 ready。"""
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


@pytest.mark.asyncio
async def test_liveness_survives_unavailable_database() -> None:
    """数据库不可达时应用应启动，存活探针成功且就绪探针失败。"""
    settings = Settings(
        app_env="development",
        database_url="postgresql+asyncpg://myapp:myapp@127.0.0.1:1/myapp",
        otel_enabled=False,
    )
    application = create_app(settings)

    async with LifespanManager(application):
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            live_response = await client.get("/health/live")
            ready_response = await client.get("/health/ready")

    assert live_response.status_code == 200
    assert live_response.json()["status"] == "alive"
    assert ready_response.status_code == 503
    assert ready_response.json()["status"] == "not_ready"


@pytest.mark.asyncio
async def test_create_and_list_items(client: AsyncClient) -> None:
    """创建 Item 后应能在列表中查询到。"""
    create_resp = await client.post("/items", json={"name": "集成测试项", "description": "desc"})
    assert create_resp.status_code == 201
    item_id = create_resp.json()["id"]

    list_resp = await client.get("/items")
    assert list_resp.status_code == 200
    ids = [item["id"] for item in list_resp.json()]
    assert item_id in ids


@pytest.mark.asyncio
async def test_metrics_endpoint(client: AsyncClient) -> None:
    """Prometheus metrics 端点应可访问。"""
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "http" in response.text.lower() or len(response.text) > 0
