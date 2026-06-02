# GitHub Actions 工作流说明

本目录为 [`.github/workflows/`](../../.github/workflows/) 下每个 YAML 工作流的**独立注释文档**，说明触发条件、Job 职责、依赖的 Secrets/Variables 及与其他组件的关系。

## 工作流一览

| 文件 | 文档 | 类别 | 简要说明 |
|------|------|------|----------|
| `ci.yml` | [ci.md](ci.md) | 质量门禁 | push/PR 时跑 lint、测试、安全、构建等 |
| `ci-auto-fix.yml` | [ci-auto-fix.md](ci-auto-fix.md) | 自动修复 | 非 main 分支 CI 失败时调 Cursor Agent |
| `oncall-dispatch.yml` | [oncall-dispatch.md](oncall-dispatch.md) | 自动运维 | 告警 relay 或手动触发 AI 值班 |
| `auto-merge.yml` | [auto-merge.md](auto-merge.md) | 自动合并 | CI 全绿后合并带 `auto-fix` 标签的 PR |

## 执行顺序（自动运维链路）

```
ci.yml（质量检查）
    ↓ 失败且非 main
ci-auto-fix.yml → ai_oncall.py → 开 auto-fix PR
    ↓
ci.yml（再次验证 PR）
    ↓ 全绿 + AUTO_MERGE_ENABLED
auto-merge.yml

oncall-dispatch.yml（独立入口：告警 → relay → dispatch）
```

## 全局开关

| 名称 | 类型 | 作用 |
|------|------|------|
| `AUTO_FIX_ENABLED` | Repository Variable | 不为 `false` 时启用 `ci-auto-fix` 与 `oncall-dispatch` |
| `AUTO_MERGE_ENABLED` | Repository Variable | 为 `true` 时启用 `auto-merge`（默认建议关闭） |

## 相关文档

- [自动运维 Runbook](../runbooks/auto-ops.md)
- [Cursor Automation 配置](../../.cursor/automations/README.md)
