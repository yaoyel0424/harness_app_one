"""统一 API 响应包络模型与构造工具。"""

from typing import Any

from pydantic import BaseModel, Field
from starlette.responses import JSONResponse

# 包络字段名，供中间件与异常处理共用
ENVELOPE_KEYS = frozenset({"code", "message", "data"})


class ApiEnvelope[T](BaseModel):
    """统一 API 响应结构。"""

    code: int = Field(..., description="业务/HTTP 状态码")
    message: str = Field(..., description="提示信息")
    data: T | None = Field(default=None, description="业务数据")


def is_envelope_payload(payload: Any) -> bool:
    """判断 JSON 是否已是统一包络格式。"""
    return isinstance(payload, dict) and ENVELOPE_KEYS.issubset(payload.keys())


def build_envelope(
    *,
    data: Any = None,
    message: str = "success",
    code: int = 200,
) -> dict[str, Any]:
    """构造统一响应字典。"""
    return {"code": code, "message": message, "data": data}


def success_response(
    data: Any,
    *,
    message: str = "success",
    status_code: int = 200,
) -> JSONResponse:
    """构造成功响应（异常处理等场景直接使用）。"""
    return JSONResponse(
        status_code=status_code,
        content=build_envelope(data=data, message=message, code=status_code),
    )


def error_response(
    message: str,
    *,
    status_code: int = 400,
    data: Any = None,
) -> JSONResponse:
    """构造错误响应。"""
    return JSONResponse(
        status_code=status_code,
        content=build_envelope(data=data, message=message, code=status_code),
    )


def normalize_error_message(detail: Any) -> str:
    """将 HTTPException.detail 转为可读字符串。"""
    if isinstance(detail, str):
        return detail
    return str(detail)
