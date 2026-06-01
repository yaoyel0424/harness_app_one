"""HTTP 客户端封装，禁止业务层直接使用 requests。"""

from typing import Any

import httpx


class HttpClient:
    """基于 httpx 的异步 HTTP 客户端。"""

    def __init__(self, base_url: str = "", timeout: float = 30.0) -> None:
        self._client = httpx.AsyncClient(base_url=base_url.rstrip("/"), timeout=timeout)

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        """发送 GET 请求。"""
        return await self._client.get(path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        """发送 POST 请求。"""
        return await self._client.post(path, **kwargs)

    async def aclose(self) -> None:
        """关闭底层连接池。"""
        await self._client.aclose()
