#!/usr/bin/env python3
"""
测试 oncall-relay 与 GitHub repository_dispatch。

从项目根目录 .env 读取 GITHUB_TOKEN、GITHUB_REPO、ONCALL_WEBHOOK_SECRET。

用法:
  poetry run python scripts/test_oncall_relay.py              # GitHub + relay 全链路
  poetry run python scripts/test_oncall_relay.py --github-only
  poetry run python scripts/test_oncall_relay.py --relay-only
  poetry run python scripts/test_oncall_relay.py --relay-url http://localhost:8787/webhook
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"
DEFAULT_RELAY_URL = "http://localhost:8787/webhook"


def load_env() -> dict[str, str]:
    """读取 .env 键值（不打印敏感值）。"""
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


def build_alertmanager_body(alert_name: str) -> dict[str, Any]:
    """构造 Alertmanager webhook 格式（relay 可识别为 metric-alert）。"""
    return {
        "status": "firing",
        "commonLabels": {"alertname": alert_name},
        "commonAnnotations": {"summary": "scripts/test_oncall_relay.py 手动测试"},
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": alert_name,
                    "alert_type": "metric-alert",
                    "oncall_action": "auto-fix",
                    "severity": "critical",
                },
                "annotations": {
                    "summary": "手动测试 oncall-relay / repository_dispatch",
                    "description": "由 test_oncall_relay.py 触发，可忽略。",
                },
            }
        ],
    }


def test_github_dispatch(
    token: str,
    repo: str,
    webhook_secret: str,
    event_type: str,
    client_payload: dict[str, Any],
) -> int:
    """直接调用 GitHub repository_dispatch API。"""
    payload = dict(client_payload)
    payload["webhook_secret"] = webhook_secret
    url = f"https://api.github.com/repos/{repo}/dispatches"
    body = json.dumps({"event_type": event_type, "client_payload": payload}).encode()
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f"[GitHub] repository_dispatch 成功: event_type={event_type} HTTP {resp.status}")
            print("       请到 GitHub Actions 查看 workflow: Oncall Dispatch")
            return 0
    except urllib.error.HTTPError as err:
        detail = err.read().decode(errors="replace")[:400]
        print(f"[GitHub] 失败: HTTP {err.code}", file=sys.stderr)
        print(f"       {detail}", file=sys.stderr)
        print(
            "       排查: TOKEN 需 repo+workflow 权限；GITHUB_REPO 需与仓库一致。", file=sys.stderr
        )
        return 1


def test_relay_webhook(relay_url: str, body: dict[str, Any]) -> int:
    """POST Alertmanager 格式 payload 到 oncall-relay。"""
    data = json.dumps(body, ensure_ascii=False).encode()
    req = urllib.request.Request(
        relay_url,
        data=data,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode(errors="replace")
            print(f"[Relay] POST {relay_url} 成功: HTTP {resp.status}")
            if raw.strip():
                print(f"       响应: {raw[:500]}")
            return 0
    except urllib.error.HTTPError as err:
        detail = err.read().decode(errors="replace")[:400]
        print(f"[Relay] 失败: HTTP {err.code}", file=sys.stderr)
        print(f"       {detail}", file=sys.stderr)
        print(
            "       排查: observability 栈是否启动；relay 日志 docker compose logs oncall-relay",
            file=sys.stderr,
        )
        return 1
    except urllib.error.URLError as err:
        print(f"[Relay] 无法连接: {err.reason}", file=sys.stderr)
        print(
            "       请先启动: docker compose -f docker-compose.observability.yml "
            "--env-file .env up -d",
            file=sys.stderr,
        )
        return 1


def main() -> int:
    """运行测试。"""
    parser = argparse.ArgumentParser(description="测试 oncall-relay 与 GitHub repository_dispatch")
    parser.add_argument(
        "--github-only",
        action="store_true",
        help="仅测试 GitHub repository_dispatch（不经过 relay）",
    )
    parser.add_argument(
        "--relay-only",
        action="store_true",
        help="仅 POST 到 oncall-relay",
    )
    parser.add_argument(
        "--relay-url",
        default=DEFAULT_RELAY_URL,
        help=f"relay webhook 地址（默认 {DEFAULT_RELAY_URL}）",
    )
    parser.add_argument(
        "--event-type",
        default="metric-alert",
        choices=("metric-alert", "log-alert", "scale-advisory"),
        help="repository_dispatch 的 event_type",
    )
    args = parser.parse_args()

    if args.github_only and args.relay_only:
        print("错误: --github-only 与 --relay-only 不能同时使用", file=sys.stderr)
        return 1

    env = load_env()
    token = env.get("GITHUB_TOKEN", "")
    repo = env.get("GITHUB_REPO", "")
    webhook_secret = env.get("ONCALL_WEBHOOK_SECRET", "")

    if not token or token.startswith("ghp_xxx") or "xxxxxxxx" in token:
        print("错误: .env 中 GITHUB_TOKEN 未配置或为占位符", file=sys.stderr)
        return 1
    if not repo or repo == "your-org/harness":
        print("错误: .env 中 GITHUB_REPO 未配置或为占位符", file=sys.stderr)
        return 1

    run_github = not args.relay_only
    run_relay = not args.github_only

    # 每次测试用唯一 alertname，避免 relay 1h 冷却挡后续测试
    alert_name = f"ManualRelayTest-{int(time.time())}"
    alert_body = build_alertmanager_body(alert_name)
    relay_payload = {
        "source": "manual-test",
        "status": alert_body["status"],
        "alerts": alert_body["alerts"],
        "commonLabels": alert_body["commonLabels"],
        "commonAnnotations": alert_body["commonAnnotations"],
    }

    print(f"仓库: {repo}")
    print(f"告警名: {alert_name}")
    print()

    exit_code = 0

    if run_github:
        code = test_github_dispatch(
            token,
            repo,
            webhook_secret,
            args.event_type,
            relay_payload,
        )
        exit_code = max(exit_code, code)
        print()

    if run_relay:
        code = test_relay_webhook(args.relay_url, alert_body)
        exit_code = max(exit_code, code)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
