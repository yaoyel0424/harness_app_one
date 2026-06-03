#!/usr/bin/env python3
"""pre-commit gitleaks: 扫描暂存区是否含密钥/Token 泄露。"""

from __future__ import annotations

import shutil
import subprocess
import sys


def main() -> int:
    """运行 gitleaks protect；未安装时跳过（CI gitleaks-action 仍会检查）。"""
    gitleaks = shutil.which("gitleaks")
    if gitleaks is None:
        print(
            "警告: 未找到 gitleaks 可执行文件，跳过本地扫描。"
            "请安装: https://github.com/gitleaks/gitleaks#installing"
            "（CI 仍会运行 gitleaks-action）",
            file=sys.stderr,
        )
        return 0

    completed = subprocess.run(
        [gitleaks, "protect", "--verbose", "--redact", "--staged"],
        check=False,
    )
    return int(completed.returncode)


if __name__ == "__main__":
    sys.exit(main())
