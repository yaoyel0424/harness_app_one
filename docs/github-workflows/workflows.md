## GitHub Actions 怎么跑（共性）

仓库里每个 `.yml` 是一个 **Workflow**。GitHub 在 **触发事件** 发生时：

1. 读 yaml 里的 `on:` 判断是否匹配
2. 在 GitHub 托管的 **ubuntu-latest Runner** 上按 `jobs` 执行
3. 用 `secrets.*` / `vars.*` 注入密钥和变量
4. 结果出现在 PR 的 **Checks** 和 **Actions** 页

---

## 四个 Workflow 总览

```text
                    push/PR ──► ci.yml（质量门禁）
                                    │
                    failure ────────┼──► ci-auto-fix.yml ──► ai_oncall.py
                                    │
                    success + auto-fix 标签 ──► auto-merge.yml ──► gh pr merge

告警 relay / 手动 ──► oncall-dispatch.yml ──► ai_oncall.py ──► 开 PR
                              ▲
                    repository_dispatch（oncall_relay.py）
```

| 文件 | 作用 | 开关 |
|------|------|------|
| `ci.yml` | 主 CI（lint、mypy、测试、安全、Docker 等） | 始终（push/PR） |
| `ci-auto-fix.yml` | CI 失败时 AI 修代码 | `AUTO_FIX_ENABLED != false` |
| `oncall-dispatch.yml` | 告警 / 手动 AI 值班 | `AUTO_FIX_ENABLED != false` |
| `auto-merge.yml` | CI 绿 + allowlist → 自动 squash merge | `AUTO_MERGE_ENABLED == true` |

---

## 1. `ci.yml` — 主 CI

### 作用

等价本地 `make check` 的云端版：Ruff、mypy、Bandit、gitleaks、架构测试、单元/集成测试、SBOM、MkDocs、Docker 构建。

### 调用时机（自动）

```yaml
on:
  push: branches [main, master]
  pull_request: branches [main, master]
```

| 事件 | 何时跑 |
|------|--------|
| 向 main 开 PR | 每次 push 到 PR 分支 |
| 合并 push 到 main | push 事件 |

### 调用方式

- **不能**手动 `workflow_dispatch`（未配置）
- 只能：**push / 开 PR / 更新 PR 分支** 自动触发

### 怎么运行

- **9 个 job 并行**（`docker` 等 `lint`、`typecheck`、`test` 完成）
- `concurrency: ci-${{ github.ref }}` + `cancel-in-progress: true`：同一 PR 新 push 会 **取消** 旧 CI

```
lint ──┐
mypy ──┼──► docker（needs: lint, typecheck, test）
test ──┘
security / architecture / integration / sbom / docs  各自独立并行
```

---

## 2. `ci-auto-fix.yml` — CI 失败自动修复

### 作用

**CI 整次 workflow 失败** 后，跑 `scripts/ai_oncall.py --mode auto-fix`，用 Cursor SDK 分析并开修复 PR。

### 调用时机

```yaml
on:
  workflow_run:
    workflows: [CI]
    types: [completed]
```

| 条件 | 是否跑 |
|------|--------|
| `CI` 结束且 **failure** | 可能跑 |
| 分支是 **main/master** | **不跑** |
| `AUTO_FIX_ENABLED == false` | **不跑** |

### 调用方式

- **仅自动**：CI 失败后链式触发
- **不经过** oncall-relay

### 怎么运行

1. checkout **失败 CI 的分支**
2. 写 `alert-payload.json`（含 `source: ci-failure`、run URL）
3. `poetry run python scripts/ai_oncall.py --mode auto-fix`
4. 需要 Secret **`CURSOR_API_KEY`**（无则降级 `gh issue create`，易失败）

---

## 3. `oncall-dispatch.yml` — 告警 AI 值班

### 作用

处理 **运维告警**（Prometheus/Grafana → relay）或 **人工演练**，跑 `ai_oncall.py`，按 mode 修复或扩容分析。

### 调用时机

```yaml
on:
  repository_dispatch:
    types: [log-alert, metric-alert, scale-advisory]
  workflow_dispatch:  # 手动
```

| 触发源 | 调用方式 |
|--------|----------|
| **oncall_relay.py** | `POST https://api.github.com/repos/.../dispatches`，`event_type` 为上面三种之一 |
| **GitHub 网页** | Actions → Oncall Dispatch → Run workflow |
| **gh CLI** | `gh workflow run oncall-dispatch.yml -f mode=metric-alert` |

relay 链路：

```text
Alertmanager/Grafana → :8787/webhook → dispatch_github(event_type, payload)
```

### 怎么运行

1. 校验 `client_payload.webhook_secret` == Secret **`ONCALL_WEBHOOK_SECRET`**
2. 把 payload 写入 `alert-payload.json`
3. `--mode` = `github.event.action`（即 dispatch 的 `event_type`）
4. `ai_oncall.py`：`metric-alert`/`log-alert` → 修复 prompt；`scale-advisory` → 扩容 prompt
5. 需要 **`CURSOR_API_KEY`**
6. `concurrency: oncall-<mode>`，**不 cancel** 并行（同 mode 可排队）

---

## 4. `auto-merge.yml` — 自动合并 auto-fix PR

### 作用

带 **`auto-fix` 标签** 的 PR，在 **CI 全绿** 且 **allowlist** 通过后，`gh pr merge --squash` 合进 main。

### 调用时机

```yaml
on:
  pull_request: [opened, labeled, synchronize]
  check_suite: [completed]
```

| 事件 | 典型场景 |
|------|----------|
| Agent 开 PR + 打 `auto-fix` 标签 | opened + labeled → 可能触发 2 次（有 concurrency 取消旧的） |
| PR 新 push | synchronize |
| 任意 check 结束 | check_suite completed |

### 调用方式

- **仅自动**（无 workflow_dispatch）
- 前提：仓库 Variable **`AUTO_MERGE_ENABLED=true`**（默认建议 false，否则 job **Skipped**）

### 怎么运行

1. 查 PR 是否有 **`auto-fix` 标签**，无则 skip
2. **`gh run watch`** 等该分支最新 **`ci.yml`** run 成功（避免自等死锁）
3. 对照 **`.github/auto-fix-allowlist.txt`** 检查改动文件
4. **`gh pr merge --squash --delete-branch`**

---

## 它们之间的调用关系

```text
【开发流程】
  开发者/Agent 开 PR
       → ci.yml（自动）
       → auto-merge.yml（若 AUTO_MERGE_ENABLED=true 且有 auto-fix 标签）

【CI 失败】
  ci.yml failure
       → ci-auto-fix.yml（若 AUTO_FIX_ENABLED=true）
       → ai_oncall.py 开新 PR
       → 可能再触发 ci.yml + auto-merge.yml

【生产告警】
  Prometheus/Grafana
       → oncall-relay（Docker，非 GHA）
       → repository_dispatch
       → oncall-dispatch.yml
       → ai_oncall.py 开 PR
       → ci.yml + auto-merge.yml（同上）

【与 Cursor Webhook 并行】
  relay 还可 POST Cursor Automation（不经过上述 GHA，除非再开 PR 触发 ci）
```

---

## Secrets / Variables 汇总

| 名称 | 类型 | 谁用 |
|------|------|------|
| `GITHUB_TOKEN` | 自动 | 所有 workflow（权限内 API） |
| `CURSOR_API_KEY` | Secret | `ci-auto-fix`、`oncall-dispatch` |
| `ONCALL_WEBHOOK_SECRET` | Secret | `oncall-dispatch` 校验 relay |
| `AUTO_FIX_ENABLED` | Variable | `ci-auto-fix`、`oncall-dispatch`（`false` 关闭） |
| `AUTO_MERGE_ENABLED` | Variable | `auto-merge`（须 **`true`** 才跑） |

`.env` 里的 `GITHUB_TOKEN` 给 **本地 relay** 用；GHA 里用的是 GitHub 自动注入的 **`secrets.GITHUB_TOKEN`**（不是 `.env`）。

---

## 手动触发速查

| 想做什么 | 命令 / 操作 |
|----------|-------------|
| 跑完整 CI | push 或更新 PR |
| 演练告警值班 | `gh workflow run oncall-dispatch.yml -f mode=metric-alert` |
| 测 relay 全链路 | `poetry run python scripts/test_oncall_relay.py` |
| 自动合并 | 设 `AUTO_MERGE_ENABLED=true`，PR 带 `auto-fix`，等 CI 绿 |

更细的逐步说明见 [`github-workflows/`](README.md) 各 md 文档。
