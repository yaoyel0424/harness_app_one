"""统一响应格式中间件：路由直接返回对象，由中间件包装为 ApiEnvelope。"""

import json
from collections.abc import Awaitable, Callable
from typing import cast

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.types import ASGIApp

from myapp.schemas.response import build_envelope, is_envelope_payload

# 不参与包装的 path（指标、OpenAPI 文档等）
SKIP_PATH_PREFIXES = ("/docs", "/redoc")
SKIP_PATHS = frozenset({"/metrics", "/openapi.json"})


def _should_skip(path: str) -> bool:
    """判断是否跳过统一包装。"""
    if path in SKIP_PATHS:
        return True
    return any(path.startswith(prefix) for prefix in SKIP_PATH_PREFIXES)


class UnifiedResponseMiddleware(BaseHTTPMiddleware):
    """将 JSON 成功响应包装为 {code, message, data} 格式。"""

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """处理请求并在出站时包装 JSON  body。"""
        if _should_skip(request.url.path):
            next_response = await call_next(request)
            return next_response

        response = await call_next(request)
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        stream_response = cast(StreamingResponse, response)
        body = b""
        async for chunk in stream_response.body_iterator:
            if isinstance(chunk, bytes):
                piece = chunk
            elif isinstance(chunk, memoryview):
                piece = chunk.tobytes()
            else:
                piece = chunk.encode()
            body += piece

        if not body:
            return response

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            return Response(
                content=body,
                status_code=response.status_code,
                headers=_strip_content_length(dict(response.headers)),
                media_type=response.media_type,
            )

        if is_envelope_payload(payload):
            return JSONResponse(
                content=payload,
                status_code=response.status_code,
                headers=_strip_content_length(dict(response.headers)),
            )

        message = "success" if response.status_code < 400 else "error"
        envelope = build_envelope(
            data=payload,
            message=message,
            code=response.status_code,
        )
        return JSONResponse(
            content=envelope,
            status_code=response.status_code,
            headers=_strip_content_length(dict(response.headers)),
        )


def _strip_content_length(headers: dict[str, str]) -> dict[str, str]:
    """重建 body 后移除原 Content-Length，避免长度不一致。"""
    return {key: value for key, value in headers.items() if key.lower() != "content-length"}


def register_response_middleware(app: FastAPI) -> None:
    """注册统一响应中间件。"""
    app.add_middleware(UnifiedResponseMiddleware)
