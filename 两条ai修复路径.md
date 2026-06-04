下面按**代码实际行为**说明两条「开 PR 自动修复」路径，并补充第三条独立入口（CI 失败），避免和 relay 混在一起。

---

## 总览：三条入口，两条「告警 → 开 PR」

```text
┌─────────────────────────────────────────────────────────────────┐
│ 入口 1：Prometheus / Grafana 告警                                │
│   Alertmanager / Grafana → POST :8787/webhook → oncall_relay.py │
└───────────────────────────────┬─────────────────────────────────┘
                                │
              ┌─────────────────┴─────────────────┐
              ▼                                   ▼
    路径 A：Cursor Automation              路径 B：GitHub Actions
    dispatch_cursor_automation()           dispatch_github()
              │                                   │
              ▼                                   ▼
    Cursor 云端 Webhook                    repository_dispatch
    Prompt 在 Automation UI              oncall-dispatch.yml
              │                                   │
              ▼                                   ▼
    gitPr 工具开 PR                        ai_oncall.py + cursor_sdk
                                           CloudAgentOptions 开 PR

┌─────────────────────────────────────────────────────────────────┐
│ 入口 2：CI 失败（不经过 relay）                                   │
│   ci.yml 失败 → ci-auto-fix.yml → ai_oncall.py（仅路径 B 同款）   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ 入口 3：本地测试 Cursor（绕过 relay）                             │
│   test_cursor_webhook.py → 直连 CURSOR_AUTOMATION_WEBHOOK_URL     │
└─────────────────────────────────────────────────────────────────┘
```

---

## 共同起点：告警怎么进 relay

**Prometheus 链** — Alertmanager 把 webhook 打到 relay：

```20:24:d:\cursor\harness\observability\alertmanager\alertmanager.yml
receivers:
  - name: oncall-relay
    webhook_configs:
      - url: http://oncall-relay:8787/webhook
        send_resolved: true
```

**Loki 链** — Grafana Contact Point 同样指向 relay（仅 `MyAppErrorLogSpike`）：

```6:14:d:\cursor\harness\observability\grafana\provisioning\alerting\contact-points.yaml
contactPoints:
  - orgId: 1
    name: oncall-relay
    receivers:
      - uid: oncall_relay_webhook
        type: webhook
        settings:
          url: http://oncall-relay:8787/webhook
```

relay 容器从 **本地 `.env`** 注入变量（不是 GitHub Secrets）：

```28:36:d:\cursor\harness\docker-compose.observability.yml
    environment:
      GITHUB_TOKEN: ${GITHUB_TOKEN:-}
      GITHUB_REPO: ${GITHUB_REPO:-}
      ONCALL_WEBHOOK_SECRET: ${ONCALL_WEBHOOK_SECRET:-}
      ...
      CURSOR_AUTOMATION_WEBHOOK_URL: ${CURSOR_AUTOMATION_WEBHOOK_URL:-}
      CURSOR_AUTOMATION_WEBHOOK_SECRET: ${CURSOR_AUTOMATION_WEBHOOK_SECRET:-}
```

---

## relay 内部：分叉点（核心）

`oncall_relay.py` 收到 POST 后，先做**冷却 / 过滤**，再**先 GitHub、后 Cursor**：

```195:213:d:\cursor\harness\scripts\oncall_relay.py
        if is_cooled_down(str(alert_key), DEFAULT_COOLDOWN):
            ...
        try:
            dispatch_github(event_type, payload)
            try:
                dispatch_cursor_automation(payload)
            except urllib.error.HTTPError:
                logger.exception("Cursor Automation 转发失败（GitHub dispatch 已成功）")
            self._json_response(200, {"status": "dispatched", "event_type": event_type})
        except (urllib.error.HTTPError, RuntimeError) as exc:
            ...
            self._json_response(502, ...)
```

含义：

| 行为 | 代码含义 |
|------|----------|
| **GitHub 失败** | 整个 relay 返回 **502**，Cursor **不会被调用** |
| **GitHub 成功、Cursor 失败** | 仍返回 **200**（只打 exception 日志） |
| **未配 `CURSOR_AUTOMATION_WEBHOOK_URL`** | `dispatch_cursor_automation` **直接 return**，只走路径 B |

所以：**不是「relay 自己开 PR」**，而是 relay **转发**；当前实现里 **GitHub dispatch 仍是硬前置**。

---

## 路径 A：Cursor Automation Webhook

### A1. 代码：`dispatch_cursor_automation`

```128:145:d:\cursor\harness\scripts\oncall_relay.py
def dispatch_cursor_automation(client_payload: dict[str, Any]) -> None:
    url = os.environ.get("CURSOR_AUTOMATION_WEBHOOK_URL", "")
    if not url:
        return
    ...
    headers["Authorization"] = f"Bearer {secret}"
    data = json.dumps(client_payload).encode()
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
```

特点：

- **凭证**：`.env` 的 `CURSOR_AUTOMATION_WEBHOOK_URL` + `SECRET`（Bearer）
- **不需要** `CURSOR_API_KEY`
- **payload**：relay 解析后的 JSON（含 `source`、`alerts`、`commonLabels` 等），**原样 JSON POST**
- **不经过** GitHub Actions、**不跑** `ai_oncall.py`

### A2. Prompt 在哪定义？

**不在 Python 里**，在 Cursor 云端 Automation（仓库里只是草稿）：

```8:22:d:\cursor\harness\.cursor\automations\oncall-auto-fix.yaml
workflow:
  triggers:
    - webhook: {}
  actions:
    - gitPr: {}
  prompts:
    - prompt: |
        你是 myapp 项目的值班 SRE...
        使用 Webhook 触发器传入的 JSON payload...
```

开 PR 靠 Automation 的 **`gitPr`** 工具，不是 SDK 的 `CloudAgentOptions`。

### A3. 本地直连测试（绕过 relay）

`test_cursor_webhook.py` 和 relay 的 Cursor 分支**做同一件事**（POST + Bearer），但**不经过**冷却、不经过 GitHub：

```103:118:d:\cursor\harness\scripts\test_cursor_webhook.py
    url = env.get("CURSOR_AUTOMATION_WEBHOOK_URL", "")
    secret = env.get("CURSOR_AUTOMATION_WEBHOOK_SECRET", "")
    ...
    req = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {secret}",
        },
    )
```

你 `--e2e` 成功 = **路径 A 的 Cursor 侧是通的**。

---

## 路径 B：GitHub Actions + `cursor_sdk`

### B1. 代码：`dispatch_github`

```101:125:d:\cursor\harness\scripts\oncall_relay.py
def dispatch_github(event_type: str, client_payload: dict[str, Any]) -> None:
    ...
    client_payload["webhook_secret"] = secret
    url = f"https://api.github.com/repos/{repo}/dispatches"
    data = json.dumps({"event_type": event_type, "client_payload": client_payload}).encode()
```

- **凭证**：`.env` 的 `GITHUB_TOKEN` + `GITHUB_REPO`
- **`event_type`**：由告警解析决定 — Prometheus 用 `alert_type` label（`metric-alert` / `scale-advisory`），Grafana 固定 `log-alert`：

```63:84:d:\cursor\harness\scripts\oncall_relay.py
def parse_alertmanager_payload(...):
    alert_type = labels.get("alert_type", "metric-alert")
    ...
def parse_grafana_payload(...):
    return "log-alert", payload
```

### B2. Workflow 接住 dispatch

```4:9:d:\cursor\harness\.github\workflows\oncall-dispatch.yml
on:
  repository_dispatch:
    types:
      - log-alert
      - metric-alert
      - scale-advisory
```

先校验 relay 塞进 payload 的密钥（GitHub **Secrets**，不是 `.env`）：

```32:41:d:\cursor\harness\.github\workflows\oncall-dispatch.yml
      - name: 校验 Webhook 密钥
        env:
          EXPECTED: ${{ secrets.ONCALL_WEBHOOK_SECRET }}
          RECEIVED: ${{ github.event.client_payload.webhook_secret }}
        run: |
          if [ -n "$EXPECTED" ] && [ "$EXPECTED" != "$RECEIVED" ]; then
            echo "Webhook 密钥不匹配"
            exit 1
          fi
```

再把 `client_payload` 写入文件，调用 **`ai_oncall.py`**：

```67:75:d:\cursor\harness\.github\workflows\oncall-dispatch.yml
      - name: 运行 AI 值班
        env:
          CURSOR_API_KEY: ${{ secrets.CURSOR_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          poetry run python scripts/ai_oncall.py \
            --mode "$mode" \
            --payload-file alert-payload.json
```

### B3. `ai_oncall.py`：Prompt 在仓库里 + SDK 开 PR

Prompt **运行时从仓库读 `AGENTS.md`** 拼进字符串：

```41:72:d:\cursor\harness\scripts\ai_oncall.py
def build_fix_prompt(payload: dict[str, Any]) -> str:
    agents = AGENTS_MD.read_text(encoding="utf-8") if AGENTS_MD.exists() else ""
    return f"""你是 myapp 项目的值班 SRE...
## 项目约定（AGENTS.md 摘要）
{agents[:4000]}
## 告警信息
```json
{json.dumps(payload, ...)}
```...
```

启动 Agent 用 **`cursor_sdk`**，**必须** `CURSOR_API_KEY`（GitHub Secret）：

```94:121:d:\cursor\harness\scripts\ai_oncall.py
def run_cursor_agent(prompt: str, *, auto_create_pr: bool = True) -> int:
    api_key = os.environ.get("CURSOR_API_KEY", "")
    if not api_key:
        print("未设置 CURSOR_API_KEY，跳过 Cloud Agent", file=sys.stderr)
        return 1
    ...
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
```

没有 API Key 时**降级**为 `gh issue create`（你 CI 里看到的失败）：

```195:197:d:\cursor\harness\scripts\ai_oncall.py
    exit_code = run_cursor_agent(prompt)
    if exit_code != 0:
        return run_local_fallback(payload, mode)
```

---

## 路径对比表（按代码）

| 维度 | 路径 A：Automation Webhook | 路径 B：GHA + SDK |
|------|---------------------------|-------------------|
| **触发函数** | `dispatch_cursor_automation()` | `dispatch_github()` → workflow → `ai_oncall.py` |
| **本地配置** | `.env`：`CURSOR_AUTOMATION_WEBHOOK_*` | `.env`：`GITHUB_TOKEN`、`GITHUB_REPO`、`ONCALL_WEBHOOK_SECRET` |
| **云端配置** | Cursor UI 里 Automation | GitHub Secrets：`CURSOR_API_KEY`、`ONCALL_WEBHOOK_SECRET` |
| **Prompt 来源** | `.cursor/automations/*.yaml` → 粘贴到 Cursor UI | `ai_oncall.py` + 仓库 `AGENTS.md` |
| **开 PR 机制** | Automation `gitPr: {}` | `CloudAgentOptions(auto_create_pr=True)` |
| **运行环境** | Cursor 云端 VM | GitHub Actions Runner（先 `poetry install`） |
| **日志在哪看** | [cursor.com/automations](https://cursor.com/automations) | GitHub Actions → Oncall Dispatch |
| **relay 是否必需** | 告警场景：经 relay 转发；也可 `test_cursor_webhook.py` 直连 | 告警场景：经 relay；也可 `gh api .../dispatches` 直连 |
| **失败时 relay 行为** | 失败不影响 200（若 GitHub 已成功） | **失败 → relay 502** |

---

## 第三条：`ci-auto-fix.yml`（只属于路径 B）

CI 红掉时**完全不经过 relay**：

```3:6:d:\cursor\harness\.github\workflows\ci-auto-fix.yml
on:
  workflow_run:
    workflows: [CI]
    types: [completed]
```

自己构造 payload（`source: ci-failure`），同样调 `ai_oncall.py`：

```48:55:d:\cursor\harness\.github\workflows\ci-auto-fix.yml
      - name: 运行 AI 修复
        env:
          CURSOR_API_KEY: ${{ secrets.CURSOR_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          poetry run python scripts/ai_oncall.py \
            --mode auto-fix \
            --payload-file alert-payload.json
```

所以：**CI 自动修复只认路径 B**；你配了 Webhook 也**帮不了** `ci-auto-fix`，除非另做 Cursor 的 `ci-failure-auto-fix` Automation（`.cursor/automations/ci-failure-auto-fix.yaml`）。

---

## 配置读哪、跑在哪（易混点）

```text
                    本地 .env              GitHub Secrets
                    ─────────              ──────────────
路径 A Webhook      WEBHOOK_URL/SECRET     （不需要）
路径 B dispatch     GITHUB_TOKEN           ONCALL_WEBHOOK_SECRET
路径 B Agent        （.env 不参与 GHA）     CURSOR_API_KEY
```

`.env` **不会**上传 GitHub；GHA 里的 `ai_oncall.py` **读不到** `CURSOR_AUTOMATION_WEBHOOK_*`。

---

## 为何仓库两套都保留？

从代码看是**刻意并行**，不是重复实现同一函数：

1. **relay 双发**：GitHub 主路 + Cursor 可选附加（见 `do_POST` 顺序）。
2. **Prompt 维护方式不同**：Automation 在 Cursor UI；SDK 路径 Prompt 跟 Git 版本走。
3. **CI 修复**只有 GHA 入口（`ci-auto-fix.yml`），Webhook 路径有单独的 Automation 草稿。
4. **运维偏好**：有人要在 Actions 里看全链路 + 校验 `webhook_secret`；有人只想配 Webhook、不要 `CURSOR_API_KEY`。

---

## 结合你现状的结论

- **`test_cursor_webhook.py --e2e` 成功** → 路径 A（Cursor 收 webhook、能开 PR）OK。
- **relay 502 / GHA 报 `未设置 CURSOR_API_KEY`** → 路径 B 在 GitHub 侧还缺 Secret，或 relay 的 `GITHUB_TOKEN` 未 `--force-recreate` 注入。
- **若只想要路径 A**：理论上可不要 `oncall-dispatch` + `CURSOR_API_KEY`，但**当前代码仍强制先 `dispatch_github` 成功**，所以 `GITHUB_TOKEN` 仍要有；要「纯 Webhook」需改 relay 逻辑。
- **CI 失败修复**：要么在 GitHub 配 **`CURSOR_API_KEY`**，要么用 Cursor **`ciCompleted` Automation** 并关掉 `ci-auto-fix.yml`。

若你希望「只保留 Webhook、GitHub dispatch 改为可选」，可以说一下，我可以按代码帮你改 `oncall_relay.py` 的分支逻辑。
