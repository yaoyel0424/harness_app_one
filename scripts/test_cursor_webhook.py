#!/usr/bin/env python3
"""
测试 Cursor Automation Webhook。

说明:
  HTTP 200 仅表示 Cursor 已接收请求，PR 由 Cloud Agent 异步创建。
  请到 https://cursor.com/automations 查看 Run history。

用法:
  python scripts/test_cursor_webhook.py           # 连通性测试
  python scripts/test_cursor_webhook.py --e2e     # 端到端：要求 Agent 做无害文档改动并开 PR
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def load_env() -> dict[str, str]:
    """读取 .env。"""
    result: dict[str, str] = {}
    if not ENV_FILE.exists():
        return result
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


def build_payload(*, e2e: bool) -> dict:
    """构造测试 payload。"""
    if e2e:
        return {
            "source": "manual-e2e-test",
            "alerts": [
                {
                    "labels": {
                        "alertname": "MyAppHighErrorRate",
                        "oncall_action": "auto-fix",
                    },
                    "annotations": {
                        "summary": "[e2e-test] 模拟 5xx 过高，请做可验证的最小修复",
                        "description": (
                            "这是人工触发的端到端测试。"
                            "请在 docs/runbooks/auto-ops.md 末尾追加一行 "
                            "'<!-- e2e-test -->'，运行 ruff/mypy/pytest 后开 PR。"
                            "禁止新建分支，必须在 Cursor 分配的 cursor/-bc-... "
                            "分支上 commit 并 push。"
                            "标题 [auto-fix] e2e webhook test，标签 auto-fix。不要提交 .env。"
                        ),
                    },
                }
            ],
        }
    return {
        "source": "manual-test",
        "alerts": [
            {
                "labels": {"alertname": "TestAlert"},
                "annotations": {"summary": "webhook 连通性测试（不保证开 PR）"},
            }
        ],
    }


def print_troubleshooting() -> None:
    """输出 PR 未出现时的排查项。"""
    print()
    print("=== 若 Run history 有记录但无 PR，请检查 ===")
    print("1. Automation 顶部是否有 Prompt（Instructions）？空 Prompt 不会修复")
    print("2. Tools 是否添加了 GitHub → Open Pull Request？")
    print("3. 右上角仓库是否为 yaoyel0424/harness_app_one / main？")
    print("4. Cloud Agents 是否已授权 GitHub: https://cursor.com/dashboard?tab=cloud-agents")
    print("5. Run history 里是否有 error / failed？点开看日志")
    print()
    print("=== 端到端测试（更可能产生 PR）===")
    print("  python scripts/test_cursor_webhook.py --e2e")
    print()
    print("查看运行: https://cursor.com/automations")
    print("查看 PR:  https://github.com/yaoyel0424/harness_app_one/pulls")


def main() -> int:
    """发送测试 payload。"""
    parser = argparse.ArgumentParser(description="测试 Cursor Automation Webhook")
    parser.add_argument(
        "--e2e",
        action="store_true",
        help="端到端测试：payload 明确要求做最小文档改动并开 PR",
    )
    args = parser.parse_args()

    env = load_env()
    url = env.get("CURSOR_AUTOMATION_WEBHOOK_URL", "")
    secret = env.get("CURSOR_AUTOMATION_WEBHOOK_SECRET", "")
    if not url or not secret:
        print("错误: .env 缺少 CURSOR_AUTOMATION_WEBHOOK_URL 或 SECRET", file=sys.stderr)
        return 1

    payload = build_payload(e2e=args.e2e)
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {secret}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read().decode()
            print(f"Webhook 已接收: HTTP {resp.status}")
            if body.strip():
                print(f"响应: {body[:500]}")
            print("Agent 在云端异步运行，通常需 2~10 分钟。")
            if not args.e2e:
                print("提示: 普通测试 payload 很模糊，Agent 可能判断「无需修复」而不开 PR。")
            print_troubleshooting()
            return 0
    except urllib.error.HTTPError as err:
        print(f"失败: HTTP {err.code} - {err.read().decode()[:300]}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
