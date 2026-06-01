#!/usr/bin/env python3
"""清理 Agent 会话产生的临时文件。"""

from __future__ import annotations

import shutil
from pathlib import Path

# 需要清理的临时目录/文件模式
CLEANUP_TARGETS = [
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "htmlcov",
    "coverage.xml",
    ".coverage",
    "site",
]


def cleanup(root: Path | None = None) -> int:
    """删除项目中的临时构建/测试产物。"""
    project_root = root or Path(__file__).resolve().parents[1]
    removed = 0
    for name in CLEANUP_TARGETS:
        target = project_root / name
        if target.is_dir():
            shutil.rmtree(target)
            removed += 1
            print(f"已删除目录: {target}")
        elif target.is_file():
            target.unlink()
            removed += 1
            print(f"已删除文件: {target}")
    print(f"清理完成，共移除 {removed} 项")
    return removed


if __name__ == "__main__":
    cleanup()
