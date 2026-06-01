"""Item API 路由。"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from myapp.composition.dependencies import get_external_service, get_item_service
from myapp.core.services.external_service import ExternalService
from myapp.core.services.item_service import ItemService
from myapp.schemas.item import ExternalQuoteResponse, ItemCreate, ItemResponse

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=list[ItemResponse])
async def list_items(
    service: Annotated[ItemService, Depends(get_item_service)],
) -> list[ItemResponse]:
    """获取 Item 列表。"""
    return await service.list_items()


@router.get("/external/quote", response_model=ExternalQuoteResponse)
async def get_external_quote(
    service: Annotated[ExternalService, Depends(get_external_service)],
) -> ExternalQuoteResponse:
    """调用外部 API 获取引言（演示 HTTP 客户端封装）。"""
    return await service.fetch_quote()


@router.get("/{item_id}", response_model=ItemResponse)
async def get_item(
    item_id: int,
    service: Annotated[ItemService, Depends(get_item_service)],
) -> ItemResponse:
    """按 ID 获取 Item。"""
    item = await service.get_item(item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item 不存在")
    return item


@router.post("", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
async def create_item(
    payload: ItemCreate,
    service: Annotated[ItemService, Depends(get_item_service)],
) -> ItemResponse:
    """创建 Item。"""
    return await service.create_item(payload)
