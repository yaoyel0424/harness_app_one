"""全局异常处理：结构化 JSON 日志供 Loki 排查，HTTP 4xx 记 WARNING 避免误触发日志告警。"""

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from starlette.responses import JSONResponse

from myapp.schemas.response import error_response, normalize_error_message
from myapp.utils.logging import get_logger

logger = get_logger(__name__)


def _request_context(request: Request) -> dict[str, Any]:
    """提取请求上下文，写入结构化日志。"""
    return {
        "path": request.url.path,
        "method": request.method,
    }


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。"""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        """HTTP 业务异常（含 4xx/5xx）：记 WARNING，不写入 ERROR 级别。"""
        logger.warning(
            "HTTP 异常",
            extra={
                **_request_context(request),
                "status_code": exc.status_code,
                "detail": exc.detail,
            },
        )
        return error_response(
            normalize_error_message(exc.detail),
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """请求体验证失败：记 WARNING。"""
        logger.warning(
            "请求参数校验失败",
            extra={
                **_request_context(request),
                "status_code": 422,
                "errors": exc.errors(),
            },
        )
        return error_response(
            "请求参数校验失败",
            status_code=422,
            data=exc.errors(),
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """未捕获异常：记 ERROR（供 Loki 人工排查），响应通用 500。"""
        logger.error(
            "未处理的服务器异常",
            exc_info=True,
            extra={
                **_request_context(request),
                "exception_type": type(exc).__name__,
            },
        )
        return error_response("服务器内部错误", status_code=500)
