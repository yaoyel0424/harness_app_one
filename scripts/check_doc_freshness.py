#!/usr/bin/env python3
"""检查文档是否与代码变更同步（基于 git diff 启发式）。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# 代码变更时需要同步更新的文档
DOC_PATHS = [
    "docs/architecture/overview.md",
    "AGENTS.md",
    "README.md",
]


def get_changed_files() -> set[str]:
    """获取当前分支相对 main 的变更文件列表。"""
    result = subprocess.run(
        ["git", "diff", "--name-only", "main...HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        # 无 main 分支时检查暂存区
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def check_doc_freshness(root: Path | None = None) -> int:
    """若 src/ 有变更但文档未更新，则返回非零退出码。"""
    _ = root or Path(__file__).resolve().parents[1]
    changed = get_changed_files()
    src_changed = any(f.startswith("src/") for f in changed)
    doc_changed = any(f in changed or f.startswith("docs/") for f in changed)

    if src_changed and not doc_changed:
        print("警告: 检测到 src/ 变更但未更新文档，请同步 docs/ 或 AGENTS.md")
        return 1

    print("文档新鲜度检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(check_doc_freshness())
