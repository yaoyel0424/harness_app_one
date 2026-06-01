#!/usr/bin/env python3
"""
AI 值班脚本：根据告警自动修复、扩容分析、提交 PR。

用法：
  python scripts/ai_oncall.py --mode auto-fix --payload-file alert.json
  python scripts/ai_oncall.py --mode scale-advisory --payload-file alert.json

环境变量：
  CURSOR_API_KEY       - Cursor API Key（Cloud Agent 自动修复）
  GITHUB_TOKEN         - 创建 Issue/PR 备用
  AUTO_FIX_ENABLED     - true/false
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENTS_MD = PROJECT_ROOT / "AGENTS.md"


def load_payload(path: Path | None, raw: str | None) -> dict[str, Any]:
    """加载告警 payload。"""
    if path and path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if raw:
        return json.loads(raw)
    if not sys.stdin.isatty():
        return json.load(sys.stdin)
    return {}


def build_fix_prompt(payload: dict[str, Any]) -> str:
    """构造自动修复 Agent prompt。"""
    agents = AGENTS_MD.read_text(encoding="utf-8") if AGENTS_MD.exists() else ""
    return f"""你是 myapp 项目的值班 SRE，负责根据告警自动修复代码。

## 项目约定（AGENTS.md 摘要）
{agents[:4000]}

## 告警信息
```json
{json.dumps(payload, ensure_ascii=False, indent=2)[:6000]}
```

## 任务
1. 根据告警分析根因（优先检查 config、database_url、docker-compose 端口、health check）
2. 在 src/ 或 tests/ 中修复问题，遵守 import-linter 分层（api 不直接 import db）
3. 若改配置，同步更新 .env.example 和 docs/
4. 运行并通过：
   - poetry run ruff check src tests
   - poetry run mypy
   - poetry run lint-imports
   - poetry run pytest tests/unit tests/architecture -n auto --cov-fail-under=80
5. 创建分支 fix/auto-{{timestamp}}，提交并开 PR
6. PR 标题格式：[auto-fix] <简短描述>
7. PR 正文说明：根因、修复内容、验证命令
8. 给 PR 打标签：auto-fix

## 禁止
- 不要提交 .env 或任何密钥
- 不要直接 merge 到 main
- 修复不了时在 PR 中说明原因，不要胡乱改代码
"""


def build_scale_prompt(payload: dict[str, Any]) -> str:
    """构造扩容分析 Agent prompt。"""
    return f"""你是 myapp 项目的 SRE，负责分析是否需要扩容及如何调整 HPA。

## 告警信息
```json
{json.dumps(payload, ensure_ascii=False, indent=2)[:6000]}
```

## 任务
1. 阅读 deploy/k8s/deployment-hpa.yaml 与 observability/prometheus/alerts.yml
2. 判断是「应扩容」还是「代码/DB 瓶颈不应扩容」
3. 若应扩容：调整 deploy/k8s/deployment-hpa.yaml 的 minReplicas/maxReplicas 与 metrics 目标
4. 若不应扩容：修复真正瓶颈（如 DB 连接池、慢查询）
5. 开 PR，标题 [auto-scale] 或 [auto-fix]，标签 auto-fix
6. 在 PR 描述中给出 Prometheus 指标依据
"""


def run_cursor_agent(prompt: str, *, auto_create_pr: bool = True) -> int:
    """通过 Cursor SDK Cloud Agent 执行。"""
    api_key = os.environ.get("CURSOR_API_KEY", "")
    if not api_key:
        print("未设置 CURSOR_API_KEY，跳过 Cloud Agent", file=sys.stderr)
        return 1

    try:
        from cursor_sdk import Agent, CloudAgentOptions, CursorAgentError
    except ImportError:
        print("请安装 cursor-sdk: pip install cursor-sdk", file=sys.stderr)
        return 1

    try:
        with Agent.create(
            model="composer-2.5",
            api_key=api_key,
            cloud=CloudAgentOptions(
                auto_create_pr=auto_create_pr,
                skip_reviewer_request=True,
            ),
        ) as agent:
            run = agent.send(prompt)
            result = run.wait()
            print(f"Agent 完成: status={result.status}, run_id={run.id}")
            if result.status == "error":
                return 2
            return 0
    except CursorAgentError as err:
        print(f"Agent 启动失败: {err.message}", file=sys.stderr)
        return 1


def run_local_fallback(payload: dict[str, Any], mode: str) -> int:
    """无 Cursor API Key 时的降级：创建 GitHub Issue。"""
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not repo:
        print("缺少 GITHUB_TOKEN / GITHUB_REPOSITORY，无法创建 Issue", file=sys.stderr)
        return 1

    title = f"[oncall/{mode}] {payload.get('commonAnnotations', {}).get('summary', '告警')}"
    body = f"""## 自动值班（降级模式）

未配置 CURSOR_API_KEY，已记录告警，请人工处理或配置 API Key 后重试。

### 告警 payload
```json
{json.dumps(payload, ensure_ascii=False, indent=2)}
```

### 建议命令
```bash
poetry run myapp
poetry run pytest tests/unit tests/architecture
```
"""
    cmd = [
        "gh",
        "issue",
        "create",
        "--repo",
        repo,
        "--title",
        title,
        "--body",
        body,
        "--label",
        "auto-fix",
    ]
    subprocess.run(cmd, check=True)
    return 0


def main() -> int:
    """入口。"""
    parser = argparse.ArgumentParser(description="AI 值班：自动修复 / 扩容分析")
    parser.add_argument(
        "--mode",
        choices=["auto-fix", "log-alert", "metric-alert", "scale-advisory"],
        default="auto-fix",
    )
    parser.add_argument("--payload-file", type=Path, default=None)
    parser.add_argument("--payload-json", type=str, default=None)
    args = parser.parse_args()

    if os.getenv("AUTO_FIX_ENABLED", "true").lower() != "true":
        print("AUTO_FIX_ENABLED=false，跳过")
        return 0

    payload = load_payload(args.payload_file, args.payload_json)
    mode = args.mode

    if mode in ("auto-fix", "log-alert", "metric-alert"):
        prompt = build_fix_prompt(payload)
    else:
        prompt = build_scale_prompt(payload)

    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    prompt = prompt.replace("{timestamp}", timestamp)

    exit_code = run_cursor_agent(prompt)
    if exit_code != 0:
        return run_local_fallback(payload, mode)
    return 0


if __name__ == "__main__":
    sys.exit(main())
