# Cursor Automation 配置

本目录包含 **Cursor Automation** 的工作流定义（YAML 草稿），与 `scripts/ai_oncall.py` 中的 prompt 逻辑一一对应。

> Cursor Automation 保存在 Cursor 云端，不在 Git 里自动同步。本目录用于**版本化管理**和**导入 Automations 编辑器**。

## 包含的 Automation

| 文件 | 名称 | 触发器 | 用途 |
|------|------|--------|------|
| `oncall-auto-fix.yaml` | Oncall 自动修复 | Webhook | 指标/日志告警 → 分析并开 PR |
| `oncall-scale-advisory.yaml` | Oncall 扩容分析 | Webhook | 高延迟/QPS → HPA 调整或根因修复 |
| `ci-failure-auto-fix.yaml` | CI 失败自动修复 | Git CI 完成 | 主分支 CI 红 → 自动修复 PR |

## 安装步骤

### 1. 在 Cursor 中创建 Automation

1. 打开 Cursor → **Automations**（或命令面板搜索 "Automations"）
2. 点击 **New automation**
3. 对照本目录 YAML 填写：
   - **Trigger**（触发器）
   - **Tools**（工具，勾选 Open or update PRs / `gitPr`）
   - **Instructions**（指令，复制 YAML 中 `prompts` 段落）
   - **Repository & branch**（仓库与分支，替换 `YOUR_ORG/harness`）

也可在 Agents 窗口中说：**「按 `.cursor/automations/oncall-auto-fix.yaml` 帮我创建 Cursor Automation」**，让 Agent 打开编辑器并预填。

### 2. 保存后获取 Webhook URL

Webhook 类 Automation 保存后，Cursor 会生成：

- **Webhook URL**（例如 `https://api.cursor.com/...`）
- **Auth Header / Secret**（若启用）

将 URL 填入 `.env`：

```env
CURSOR_AUTOMATION_WEBHOOK_URL=https://api.cursor.com/automations/xxx/webhook
CURSOR_AUTOMATION_WEBHOOK_SECRET=your-secret
```

### 3. 接入告警链路

**方式 A — 经 oncall-relay（推荐，带冷却与双路转发）**

在 `.env` 中设置 `CURSOR_AUTOMATION_WEBHOOK_URL`（见 `.env.example` 底部），relay 会在转发 GitHub dispatch 的同时 POST 到 Cursor Automation。

**方式 B — Alertmanager 直连**

复制 `observability/alertmanager/alertmanager-cursor.example.yml` 中的 receiver，将 URL 改为 Cursor Webhook。

**方式 C — 保留 GitHub Actions 路径**

不配置 Cursor Webhook，继续使用 `.github/workflows/oncall-dispatch.yml` + `scripts/ai_oncall.py`（Cursor SDK）。与 Cursor Automation **二选一或并存**。

## 与 GitHub Actions 方案对比

| 维度 | Cursor Automation | GHA + cursor-sdk |
|------|-------------------|------------------|
| 配置位置 | Cursor UI + 本目录 YAML | `.github/workflows/` |
| 需要 CURSOR_API_KEY | 否（Cursor 账号授权） | 是 |
| PR 创建 | 内置 `gitPr` | SDK `CloudAgentOptions` |
| 冷却/熔断 | 需在 Alertmanager/relay 层 | oncall-relay 已内置 |
| 可见性 | Cursor Dashboard | GitHub Actions 日志 |

## 占位符

创建 Automation 前请替换 YAML 中的：

- `YOUR_ORG/harness` → 你的 GitHub 仓库（如 `acme/harness`）
- `main` → 默认分支（若不同）

## Cloud Agent

Cloud 计算在 [Cursor Dashboard → Cloud Agents](https://cursor.com/dashboard?tab=cloud-agents) 配置，确保仓库已授权 Cursor 访问 GitHub。
