"""Pydantic 请求/响应模型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ItemCreate(BaseModel):
    """创建 Item 请求体。"""

    name: str = Field(..., min_length=1, max_length=255, description="名称")
    description: str | None = Field(default=None, max_length=1024, description="描述")


class ItemResponse(BaseModel):
    """Item 响应体。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    created_at: datetime


class HealthResponse(BaseModel):
    """健康检查响应。"""

    status: str
    service: str


class ExternalQuoteResponse(BaseModel):
    """外部 API 调用示例响应。"""

    quote: str
    source: str
