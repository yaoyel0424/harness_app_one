"""FastAPI 应用入口。"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.exc import SQLAlchemyError

from myapp.api import health_router, items_router
from myapp.config import Settings, get_settings
from myapp.db.session import create_engine, create_session_factory, init_db
from myapp.utils.logging import get_logger, setup_logging
from myapp.utils.telemetry import setup_telemetry

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """应用生命周期：初始化数据库连接池。"""
    settings: Settings = app.state.settings
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    app.state.engine = engine
    app.state.session_factory = session_factory

    if settings.app_env != "production":
        try:
            await init_db(engine)
        except (SQLAlchemyError, OSError) as exc:
            logger.warning(
                "数据库初始化失败, 应用保持启动并由就绪探针报告状态",
                extra={"app_env": settings.app_env, "error": str(exc)},
            )

    setup_telemetry(app, settings, engine)
    logger.info("应用启动完成", extra={"app_env": settings.app_env})
    yield
    await engine.dispose()
    logger.info("应用已关闭")


def create_app(settings: Settings | None = None) -> FastAPI:
    """创建并配置 FastAPI 应用实例。"""
    resolved_settings = settings or get_settings()
    setup_logging(resolved_settings.log_level)

    app = FastAPI(
        title=resolved_settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings

    app.include_router(health_router)
    app.include_router(items_router)

    # Prometheus /metrics 端点
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    return app


def run() -> None:
    """通过 uvicorn 启动应用（开发模式）。"""
    settings = get_settings()
    uvicorn.run(
        "myapp.main:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        reload=settings.app_env == "development",
        log_level=settings.log_level.lower(),
    )


# 供 uvicorn/gunicorn 直接引用
app = create_app()

if __name__ == "__main__":
    run()
