#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# 验证 Git worktree 环境是否满足开发与 CI 要求
# ---------------------------------------------------------------------------
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> 检查 Python 版本"
if command -v pyenv >/dev/null 2>&1; then
  pyenv version
else
  python --version
fi

echo "==> 检查 Poetry"
poetry --version

echo "==> 安装依赖"
poetry install --with dev --no-interaction

echo "==> 运行质量门禁"
make check

echo "==> 启动 Uvicorn 冒烟测试"
poetry run uvicorn myapp.main:app --host 127.0.0.1 --port 8765 &
PID=$!
sleep 3
curl -sf "http://127.0.0.1:8765/health/live" >/dev/null
curl -sf "http://127.0.0.1:8765/metrics" >/dev/null
kill "$PID"
wait "$PID" 2>/dev/null || true

echo "==> worktree 验证通过"
