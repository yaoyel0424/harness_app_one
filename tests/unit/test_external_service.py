"""ExternalService 单元测试。"""

import httpx
import pytest

from myapp.core.services.external_service import ExternalService
from myapp.utils.http_client import HttpClient


@pytest.mark.asyncio
async def test_fetch_quote_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """fetch_quote 应正确解析外部 API 响应。"""
    request = httpx.Request("GET", "https://api.quotable.io/random")
    mock_response = httpx.Response(
        200,
        json={"content": "Hello", "author": "Author"},
        request=request,
    )

    async def mock_get(_self: HttpClient, _path: str, **_kwargs: object) -> httpx.Response:
        return mock_response

    monkeypatch.setattr(HttpClient, "get", mock_get)
    service = ExternalService(HttpClient(base_url="https://api.quotable.io"))

    quote = await service.fetch_quote()

    assert quote.quote == "Hello"
    assert quote.source == "Author"
