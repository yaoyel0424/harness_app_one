"""外部 API 调用业务服务。"""

from myapp.schemas.item import ExternalQuoteResponse
from myapp.utils.http_client import HttpClient


class ExternalService:
    """演示通过封装 HTTP 客户端调用外部 API。"""

    def __init__(self, http_client: HttpClient) -> None:
        self._http_client = http_client

    async def fetch_quote(self) -> ExternalQuoteResponse:
        """从外部 API 获取示例数据（quotable.io）。"""
        response = await self._http_client.get("/random")
        response.raise_for_status()
        data = response.json()
        return ExternalQuoteResponse(
            quote=data.get("content", "默认引言"),
            source=data.get("author", "unknown"),
        )
