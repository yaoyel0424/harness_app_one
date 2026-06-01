"""respx HTTP mock 演示测试。"""

import httpx
import pytest
import respx


@pytest.mark.asyncio
async def test_respx_mock_external_api() -> None:
    """respx 应能 mock httpx 异步请求。"""
    with respx.mock:
        respx.get("https://example.com/data").respond(json={"ok": True})
        async with httpx.AsyncClient() as client:
            response = await client.get("https://example.com/data")
    assert response.json()["ok"] is True
