"""API 横切处理器（异常、中间件等，非路由）。"""

from myapp.api.handlers.exception_handlers import register_exception_handlers
from myapp.api.handlers.response_middleware import register_response_middleware

__all__ = ["register_exception_handlers", "register_response_middleware"]
