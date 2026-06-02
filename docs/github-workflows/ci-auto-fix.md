# ci-auto-fix.yml — CI 失败自动修复

> 对应文件：`.github/workflows/ci-auto-fix.yml`

## 作用

当 **[ci.yml](ci.md) 在 feature/PR 分支上失败** 时，自动调用 `scripts/ai_oncall.py`，通过 **Cursor Cloud Agent（SDK）** 分析失败原因、修复代码并创建带 `auto-fix` 标签的 PR。

这是 **GitHub Actions + CURSOR_API_KEY** 路径；与 Cursor Automation 的 `ciCompleted` 触发器功能类似，可二选一或并存。

## 何时执行

```yaml
on:
  workflow_run:
    workflows: [CI]
    types: [completed]
```

| 条件 | 说明 |
|------|------|
| `ci.yml` 跑完 | 无论成功或失败都会收到 `completed` 事件 |
| `conclusion == 'failure'` | **仅 CI 失败时** 继续 |
| `head_branch != 'main'` 且 `!= 'master'` | **排除默认分支**；main 上 CI 红不会触发本 Workflow |
| `vars.AUTO_FIX_ENABLED != 'false'` | 仓库 Variable 总开关 |

> **注意**：部分文档写「主分支 CI 失败也会修复」与本文件实际逻辑不符；本 Workflow 刻意只处理 **PR/feature 分支** 上的失败，避免在 main 上直接自动改代码。

## 权限

```yaml
permissions:
  contents: write
  pull-requests: write
  actions: read
```

需要写权限以便 checkout 分支、Agent 后续开 PR；`actions: read` 用于读取关联的 CI run 信息。

## Job：trigger-fix

### 1. Checkout

```yaml
ref: ${{ github.event.workflow_run.head_branch }}
```

检出 **触发失败 CI 的那条分支**（非 main），Agent 在同一分支上下文修复。

### 2. 构造 alert-payload.json

写入 JSON，供 `ai_oncall.py` 嵌入 Prompt：

| 字段 | 来源 | 含义 |
|------|------|------|
| `source` | 固定 `ci-failure` | 标识告警类型 |
| `workflow` | `workflow_run.name` | 通常为 `CI` |
| `run_id` | `workflow_run.id` | 失败 run 的 ID |
| `url` | `workflow_run.html_url` | Actions 日志链接 |
| `branch` | `workflow_run.head_branch` | 失败所在分支 |

### 3. 运行 AI 修复

```bash
poetry run python scripts/ai_oncall.py \
  --mode auto-fix \
  --payload-file alert-payload.json
```

**环境变量：**

| 名称 | 来源 | 说明 |
|------|------|------|
| `CURSOR_API_KEY` | Secret | 启动 Cursor Cloud Agent；未配置则降级为 `gh issue create` |
| `GITHUB_TOKEN` | Secret | Agent / 降级 Issue 创建 |

`ai_oncall.py` 会读取 `AGENTS.md`，构造修复 Prompt，调用 `Agent.create(...).send(prompt)` 开 PR。

## 与其他组件的关系

```
ci.yml 失败（非 main 分支）
    ↓ workflow_run completed
ci-auto-fix.yml
    ↓
scripts/ai_oncall.py (--mode auto-fix)
    ↓
Cursor Cloud Agent → PR [auto-fix] ...
    ↓
ci.yml 再次验证新 PR
    ↓（可选）
auto-merge.yml
```

**并行方案：** `.cursor/automations/ci-failure-auto-fix.yaml` 使用 Cursor 平台 `ciCompleted` 触发，**不需要** `CURSOR_API_KEY`，由 Cursor 直接启动 Agent。

## 手动测试

无法直接 `workflow_dispatch` 本文件；需让 `ci.yml` 在 non-main 分支失败，或临时在 feature 分支引入可修复的失败。

## 注意事项

- 若同时开启 Cursor Automation `ciCompleted` 与本文 Workflow，**同一次 CI 失败可能触发两个 Agent**，产生重复 PR；建议二选一或加去重策略。
- `AUTO_FIX_ENABLED=false` 时整个 Job 被跳过。
- Agent Prompt（SDK 路径）允许 `fix/auto-{timestamp}` 分支；Cursor Automation 路径则要求使用 `cursor/-bc-...` 预分配分支（见 automations README）。
