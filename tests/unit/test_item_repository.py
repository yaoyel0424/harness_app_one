"""ItemRepository 单元测试。"""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from myapp.db.models import Base, ItemModel
from myapp.db.repositories.item_repository import ItemRepository
from myapp.db.session import create_session_factory


@pytest.fixture
async def repo_session() -> AsyncSession:
    """提供带初始 schema 的数据库会话。"""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = create_session_factory(engine)
    async with factory() as session:
        yield session
    await engine.dispose()


@pytest.mark.asyncio
async def test_repository_create_and_get(repo_session: AsyncSession) -> None:
    """Repository 应能创建并查询 Item。"""
    repo = ItemRepository(repo_session)
    created = await repo.create("仓库测试", "描述")
    assert created.id is not None

    fetched = await repo.get_by_id(created.id)
    assert fetched is not None
    assert fetched.name == "仓库测试"


@pytest.mark.asyncio
async def test_repository_list_items(repo_session: AsyncSession) -> None:
    """Repository 应返回全部 Item。"""
    repo = ItemRepository(repo_session)
    await repo.create("A", None)
    await repo.create("B", None)

    items = await repo.list_items()
    assert len(items) == 2


@pytest.mark.asyncio
async def test_item_model_fields() -> None:
    """ItemModel 字段应可正常赋值。"""
    item = ItemModel(
        id=1,
        name="模型",
        description=None,
        created_at=datetime.now(UTC),
    )
    assert item.name == "模型"
