"""使用 pytest-archon 的架构规则测试。"""

import pytest


@pytest.mark.architecture
def test_archon_api_should_not_import_db(archrule) -> None:
    """API 层禁止直接导入 db 包。"""
    (
        archrule("api-no-db", "API 层不得直接依赖 db 层")
        .match("myapp.api.*")
        .should_not_import("myapp.db.*")
    )


@pytest.mark.architecture
def test_archon_core_should_not_import_api(archrule) -> None:
    """Core 层禁止导入 api 包。"""
    (
        archrule("core-no-api", "Core 层不得依赖 api 层")
        .match("myapp.core.*")
        .should_not_import("myapp.api.*")
    )
