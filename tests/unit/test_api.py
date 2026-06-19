"""API 层单元测试。"""

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from myapp.composition.dependencies import get_db_session


def _data(response_json: dict[str, Any]) -> Any:
    """从统一包络中取出 data 字段。"""
    assert "code" in response_json
    assert "message" in response_json
    assert "data" in response_json
    return response_json["data"]


@pytest.mark.asyncio
async def test_liveness(client: AsyncClient) -> None:
    """存活探针应返回 alive。"""
    response = await client.get("/health/live")
    assert response.status_code == 200
    body = response.json()
    assert body["code"] == 200
    assert _data(body)["status"] == "alive"


@pytest.mark.asyncio
async def test_readiness(client: AsyncClient) -> None:
    """就绪探针在数据库可用时应返回 ready。"""
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert _data(response.json())["status"] == "ready"


@pytest.mark.asyncio
async def test_readiness_returns_503_when_database_unavailable(
    app: FastAPI,
    client: AsyncClient,
) -> None:
    """就绪探针在数据库不可用时应返回 not_ready。"""

    class FailingSession:
        """模拟执行数据库探测失败的会话。"""

        async def execute(self, statement: object) -> None:
            """执行健康检查 SQL 时抛出连接异常。"""
            _ = statement
            raise ConnectionError("数据库不可用")

    async def failing_db_session() -> AsyncGenerator[FailingSession, None]:
        """提供固定失败的数据库会话依赖。"""
        yield FailingSession()

    app.dependency_overrides[get_db_session] = failing_db_session
    try:
        response = await client.get("/health/ready")
    finally:
        app.dependency_overrides.pop(get_db_session, None)

    assert response.status_code == 503
    assert _data(response.json())["status"] == "not_ready"


@pytest.mark.asyncio
async def test_create_and_list_items(client: AsyncClient) -> None:
    """创建 Item 后应能在列表中查询到。"""
    create_resp = await client.post("/items", json={"name": "集成测试项", "description": "desc"})
    assert create_resp.status_code == 201
    item_id = _data(create_resp.json())["id"]

    list_resp = await client.get("/items")
    assert list_resp.status_code == 200
    ids = [item["id"] for item in _data(list_resp.json())]
    assert item_id in ids


@pytest.mark.asyncio
async def test_metrics_endpoint(client: AsyncClient) -> None:
    """Prometheus metrics 端点应可访问且不被 JSON 包络包装。"""
    response = await client.get("/metrics")
    assert response.status_code == 200
    assert "http" in response.text.lower() or len(response.text) > 0


@pytest.mark.asyncio
async def test_http_exception_returns_404(client: AsyncClient) -> None:
    """不存在的 Item 应返回 404 且使用统一错误包络。"""
    response = await client.get("/items/999999")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == 404
    assert body["message"] == "Item 不存在"
    assert body["data"] is None


@pytest.mark.asyncio
async def test_unhandled_exception_returns_500(app: FastAPI, client: AsyncClient) -> None:
    """未捕获异常应返回 500 且不泄露内部信息。"""

    @app.get("/test/unhandled-boom")
    async def boom() -> None:
        raise RuntimeError("测试用未处理异常")

    response = await client.get("/test/unhandled-boom")
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == 500
    assert body["message"] == "服务器内部错误"
    assert body["data"] is None
