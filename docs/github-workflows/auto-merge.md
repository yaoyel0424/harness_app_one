# auto-merge.yml — auto-fix PR 自动合并

> 对应文件：`.github/workflows/auto-merge.yml`

## 作用

在 **L2 自动运维策略** 下，当 AI 开的修复 PR 满足安全条件时，在 [ci.yml](ci.md) 全部通过后 **自动 squash merge** 到主分支，并删除 head 分支。

**默认关闭**，需显式设置仓库 Variable `AUTO_MERGE_ENABLED=true`；建议观察自动修复质量 1–2 周后再开启。

## 何时执行

```yaml
on:
  pull_request:
    types: [labeled, synchronize, opened]
  check_suite:
    types: [completed]
```

| 事件 | 典型场景 |
|------|----------|
| PR `opened` / `synchronize` | 新开 auto-fix PR 或 Agent push 新 commit |
| PR `labeled` | 打上 `auto-fix` 标签 |
| `check_suite completed` | [ci.yml](ci.md) 跑完（成功或失败后都会触发，后续步骤会校验） |

**Job 级条件：**

```yaml
if: vars.AUTO_MERGE_ENABLED == 'true'
```

未开启时 Workflow 会触发但 Job 立即跳过。

## 权限

```yaml
permissions:
  contents: write      # merge 需要
  pull-requests: write
  checks: read         # 读取 CI 状态
```

## Job：auto-merge — 步骤详解

### 1. 获取 PR 信息

根据事件类型解析 PR 编号：

- `pull_request` 事件：直接用 `github.event.pull_request.number`
- `check_suite` 事件：用 `gh pr list --head <branch>` 查找

**过滤条件：**

- 找不到 PR → `skip=true`，结束
- PR **没有** `auto-fix` 标签 → `skip=true`
- 有 `auto-fix` 标签 → 继续

### 2. 等待 CI 通过

```bash
gh pr checks "$PR_NUM" --watch --interval 30 --fail-fast
```

阻塞直到所有 required checks 完成；**任一失败则本步骤失败**，不会 merge。

### 3. 检查变更文件 allowlist

读取 `.github/auto-fix-allowlist.txt`（fnmatch 模式），对 PR 中每个变更文件匹配：

```
src/**
tests/**
docs/**
.env.example
README.md
AGENTS.md
observability/**
deploy/**
```

**任一文件不在 allowlist 内 → 失败退出**，防止 Agent 改到 CI 配置、Secrets、workflow 等敏感路径。

### 4. 自动合并

```bash
gh pr merge "$PR_NUM" \
  --squash \
  --delete-branch \
  --subject "chore: auto-fix merge (#$PR_NUM)"
```

- **squash merge**：多条 commit 压成一条
- **delete-branch**：删除 head 分支（含 Cursor 的 `cursor/-bc-...` 分支）

## 在自动运维链路中的位置

```
告警 / CI 失败
    ↓
ai_oncall.py 或 Cursor Automation
    ↓
开 PR，标签 auto-fix
    ↓
ci.yml 验证
    ↓（AUTO_MERGE_ENABLED=true 且 allowlist 通过）
auto-merge.yml
    ↓
代码进入 main
```

## 安全设计要点

| 机制 | 目的 |
|------|------|
| `AUTO_MERGE_ENABLED` 默认关 | 避免未经人工观察就自动合 main |
| 必须 `auto-fix` 标签 | 普通 PR 不会误合并 |
| allowlist | 限制可自动合并的路径 |
| `gh pr checks --fail-fast` | CI 红时不 merge |
| squash + 固定 subject | 主分支历史清晰 |

## 启用前检查清单

- [ ] `AUTO_FIX_ENABLED` 已按需配置
- [ ] 自动修复 PR 质量稳定
- [ ] allowlist 覆盖范围符合团队预期（如需允许改 `.github/workflows/` 需显式加入模式）
- [ ] 分支保护规则允许 `GITHUB_TOKEN` 或 bot 执行 merge

## 注意事项

- 本 Workflow **不会** 给 PR 打 `auto-fix` 标签；标签由 Agent Prompt 要求创建。
- 若 CI 使用 required checks 以外的外部检查，需确认 `gh pr checks` 能正确反映状态。
- 与 Dependabot PR、人工 PR 无关；无 `auto-fix` 标签则全程 skip。
