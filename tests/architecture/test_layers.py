"""架构约束测试。"""

import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.architecture
def test_import_linter_contracts() -> None:
    """import-linter 分层契约应全部通过。"""
    lint_imports = shutil.which("lint-imports")
    cmd = [lint_imports] if lint_imports else ["poetry", "run", "lint-imports"]
    result = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


@pytest.mark.architecture
def test_api_modules_do_not_import_db_directly() -> None:
    """API 模块源码中不得出现 myapp.db 直接导入。"""
    api_dir = PROJECT_ROOT / "src" / "myapp" / "api"
    violations: list[str] = []
    for py_file in api_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8")
        if "from myapp.db" in content or "import myapp.db" in content:
            violations.append(str(py_file.relative_to(PROJECT_ROOT)))
    assert not violations, f"API 层违规导入 db: {violations}"


@pytest.mark.architecture
def test_service_classes_live_in_core_package() -> None:
    """所有 Service 类应位于 core.services 包下。"""
    core_services = PROJECT_ROOT / "src" / "myapp" / "core" / "services"
    service_files = list(core_services.glob("*_service.py"))
    assert len(service_files) >= 1, "至少应有一个 Service 实现"

    for path in service_files:
        content = path.read_text(encoding="utf-8")
        assert "class" in content and "Service" in content
