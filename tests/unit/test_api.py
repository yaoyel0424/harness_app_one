"""API 层单元测试。"""

import pytest
from httpx import ASGITransport, AsyncClient

from myapp.composition.dependencies import get_health_service


class UnreadyHealthService:
    """测试用健康检查服务，模拟数据库不可用。"""

    async def is_database_ready(self) -> bool:
        """返回数据库不可用状态。"""
        return False


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
async def test_readiness_when_database_unavailable(app) -> None:
    """就绪探针在数据库不可用时应返回 503。"""
    app.dependency_overrides[get_health_service] = lambda: UnreadyHealthService()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


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
