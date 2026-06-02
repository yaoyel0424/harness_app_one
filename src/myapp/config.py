"""应用配置模块，基于 pydantic-settings 加载环境变量。"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用运行时配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="myapp", description="应用名称")
    app_env: Literal["development", "test", "production"] = Field(
        default="development",
        description="运行环境",
    )
    debug: bool = Field(default=False, description="是否开启调试模式")
    log_level: str = Field(default="INFO", description="日志级别")
    host: str = Field(default="127.0.0.1", description="开发服务器绑定地址")
    port: int = Field(default=8000, description="开发服务器端口")
    database_url: str = Field(
        default="postgresql+asyncpg://myapp:myapp@127.0.0.1:5433/myapp",
        description="异步数据库连接 URL",
    )
    otel_enabled: bool = Field(default=False, description="是否启用 OpenTelemetry")
    otel_service_name: str = Field(default="myapp", description="OTel 服务名")
    otel_exporter_endpoint: str = Field(
        default="http://localhost:4317",
        description="OTLP gRPC 导出端点",
    )


@lru_cache
def get_settings() -> Settings:
    """获取缓存的配置单例。"""
    return Settings()
