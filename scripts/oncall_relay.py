#!/usr/bin/env python3
"""
Grafana / Alertmanager Webhook 中继：转发至 GitHub repository_dispatch。

环境变量：
  GITHUB_TOKEN      - 具有 repo + actions 权限的 PAT
  GITHUB_REPO       - owner/repo
  ONCALL_WEBHOOK_SECRET - 与 GitHub Secrets 一致的校验密钥
  ONCALL_ENABLED    - true/false，熔断开关
  ONCALL_COOLDOWN_SEC - 同类告警冷却时间（默认 3600）
  LOG_ALERT_AUTO_FIX_ENABLED - true 时 Loki 规则 MyAppErrorLogSpike 才 dispatch（默认 true）
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("oncall-relay")

COOLDOWN_FILE = Path(os.getenv("ONCALL_STATE_FILE", "/tmp/oncall_cooldown.json"))
DEFAULT_COOLDOWN = int(os.getenv("ONCALL_COOLDOWN_SEC", "3600"))
LOG_ALERT_AUTO_FIX_ENABLED = os.getenv("LOG_ALERT_AUTO_FIX_ENABLED", "true").lower() == "true"
# 仅 Loki 激增规则走 auto-fix；Promtail 通知规则不应指向 relay
AUTO_FIX_LOG_ALERT_NAMES = frozenset({"MyAppErrorLogSpike"})


def load_cooldown() -> dict[str, float]:
    """加载告警冷却状态。"""
    if not COOLDOWN_FILE.exists():
        return {}
    try:
        return json.loads(COOLDOWN_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_cooldown(state: dict[str, float]) -> None:
    """持久化冷却状态。"""
    COOLDOWN_FILE.parent.mkdir(parents=True, exist_ok=True)
    COOLDOWN_FILE.write_text(json.dumps(state), encoding="utf-8")


def is_cooled_down(alert_key: str, cooldown_sec: int) -> bool:
    """检查是否在冷却期内。"""
    state = load_cooldown()
    last = state.get(alert_key, 0)
    if time.time() - last < cooldown_sec:
        return True
    state[alert_key] = time.time()
    save_cooldown(state)
    return False


def parse_alertmanager_payload(body: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """解析 Alertmanager webhook 格式。"""
    alerts = body.get("alerts", [])
    if not alerts:
        return "metric-alert", body

    first = alerts[0]
    labels = first.get("labels", {})
    alert_type = labels.get("alert_type", "metric-alert")
    oncall_action = labels.get("oncall_action", "auto-fix")

    if oncall_action == "scale-advisory":
        alert_type = "scale-advisory"

    payload = {
        "source": "alertmanager",
        "status": body.get("status"),
        "alerts": alerts,
        "commonLabels": body.get("commonLabels", {}),
        "commonAnnotations": body.get("commonAnnotations", {}),
    }
    return alert_type, payload


def parse_grafana_payload(body: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """解析 Grafana Unified Alerting webhook 格式。"""
    alerts = body.get("alerts", body.get("evalMatches", []))
    payload = {
        "source": "grafana",
        "status": body.get("status", body.get("state", "alerting")),
        "title": body.get("title", body.get("ruleName", "")),
        "message": body.get("message", ""),
        "alerts": alerts if isinstance(alerts, list) else [alerts],
    }
    # Grafana Loki 日志告警默认走 auto-fix
    return "log-alert", payload


def dispatch_github(event_type: str, client_payload: dict[str, Any]) -> None:
    """调用 GitHub repository_dispatch API。"""
    token = os.environ.get("GITHUB_TOKEN", "")
    repo = os.environ.get("GITHUB_REPO", "")
    if not token or not repo:
        raise RuntimeError("缺少 GITHUB_TOKEN 或 GITHUB_REPO 环境变量")

    secret = os.environ.get("ONCALL_WEBHOOK_SECRET", "")
    client_payload["webhook_secret"] = secret

    url = f"https://api.github.com/repos/{repo}/dispatches"
    data = json.dumps({"event_type": event_type, "client_payload": client_payload}).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        logger.info("GitHub dispatch 成功: %s %s", event_type, resp.status)


def dispatch_cursor_automation(client_payload: dict[str, Any]) -> None:
    """可选：转发至 Cursor Automation Webhook。"""
    url = os.environ.get("CURSOR_AUTOMATION_WEBHOOK_URL", "")
    if not url:
        return

    secret = os.environ.get("CURSOR_AUTOMATION_WEBHOOK_SECRET", "")
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if secret:
        headers["Authorization"] = f"Bearer {secret}"

    data = json.dumps(client_payload).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        logger.info("Cursor Automation webhook 成功: %s", resp.status)


class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP Webhook 处理器。"""

    def do_POST(self) -> None:
        if self.path not in ("/webhook", "/"):
            self.send_error(404)
            return

        if os.getenv("ONCALL_ENABLED", "true").lower() != "true":
            logger.warning("ONCALL_ENABLED=false，忽略告警")
            self._json_response(200, {"status": "disabled"})
            return

        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length)
        try:
            body = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            self.send_error(400, "invalid json")
            return

        # 区分 Alertmanager vs Grafana
        if "alerts" in body and "commonLabels" in body:
            event_type, payload = parse_alertmanager_payload(body)
        else:
            event_type, payload = parse_grafana_payload(body)

        if event_type == "log-alert":
            alert_name = str(payload.get("title", ""))
            if alert_name not in AUTO_FIX_LOG_ALERT_NAMES:
                logger.info(
                    "log-alert %s 为 Promtail 仅通知规则，忽略 auto-fix dispatch",
                    alert_name or "(unknown)",
                )
                self._json_response(
                    200,
                    {"status": "ignored", "reason": "notify-only log alert"},
                )
                return
            if not LOG_ALERT_AUTO_FIX_ENABLED:
                logger.info("log-alert 已禁用（LOG_ALERT_AUTO_FIX_ENABLED=false），忽略 dispatch")
                self._json_response(
                    200,
                    {"status": "ignored", "reason": "log-alert auto-fix disabled"},
                )
                return

        alert_key = payload.get("commonLabels", {}).get("alertname") or payload.get(
            "title", event_type
        )
        if is_cooled_down(str(alert_key), DEFAULT_COOLDOWN):
            logger.info("告警 %s 在冷却期内，跳过", alert_key)
            self._json_response(200, {"status": "cooldown", "alert": alert_key})
            return

        try:
            dispatch_github(event_type, payload)
            # 可选：同时转发至 Cursor Automation（见 .cursor/automations/）
            try:
                dispatch_cursor_automation(payload)
            except urllib.error.HTTPError:
                logger.exception("Cursor Automation 转发失败（GitHub dispatch 已成功）")
            self._json_response(200, {"status": "dispatched", "event_type": event_type})
        except (urllib.error.HTTPError, RuntimeError) as exc:
            logger.exception("转发失败")
            self._json_response(502, {"status": "error", "detail": str(exc)})

    def _json_response(self, code: int, data: dict[str, Any]) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def log_message(self, fmt: str, *args: object) -> None:
        logger.info(fmt, *args)


def main() -> None:
    """启动 webhook 中继服务。"""
    port = int(os.getenv("ONCALL_RELAY_PORT", "8787"))
    server = HTTPServer(("0.0.0.0", port), WebhookHandler)
    logger.info("oncall-relay 监听 :%s → GitHub %s", port, os.getenv("GITHUB_REPO", "(未配置)"))
    server.serve_forever()


if __name__ == "__main__":
    main()
