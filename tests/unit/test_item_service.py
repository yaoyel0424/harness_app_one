"""ItemService 单元测试。"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from myapp.core.services.item_service import ItemService
from myapp.db.models import ItemModel
from myapp.schemas.item import ItemCreate


@pytest.mark.asyncio
async def test_list_items_returns_responses() -> None:
    """list_items 应返回 Pydantic 响应列表。"""
    repo = MagicMock()
    repo.list_items = AsyncMock(
        return_value=[
            ItemModel(
                id=1,
                name="测试",
                description="描述",
                created_at=datetime.now(UTC),
            ),
        ]
    )
    service = ItemService(repo)

    items = await service.list_items()

    assert len(items) == 1
    assert items[0].name == "测试"


@pytest.mark.asyncio
async def test_create_item_delegates_to_repository() -> None:
    """create_item 应委托仓储层创建记录。"""
    repo = MagicMock()
    repo.create = AsyncMock(
        return_value=ItemModel(
            id=2,
            name="新建",
            description=None,
            created_at=datetime.now(UTC),
        ),
    )
    service = ItemService(repo)

    result = await service.create_item(ItemCreate(name="新建"))

    assert result.id == 2
    repo.create.assert_awaited_once_with("新建", None)
