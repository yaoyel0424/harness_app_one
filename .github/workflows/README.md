# GitHub Actions 工作流

本目录包含仓库的 CI/CD 与自动运维 Workflow 定义（YAML）。

## 文件说明

| 文件 | 说明 | 详细文档 |
|------|------|----------|
| [`ci.yml`](ci.yml) | 主 CI 质量门禁 | [docs/github-workflows/ci.md](../docs/github-workflows/ci.md) |
| [`ci-auto-fix.yml`](ci-auto-fix.yml) | CI 失败自动修复 | [docs/github-workflows/ci-auto-fix.md](../docs/github-workflows/ci-auto-fix.md) |
| [`oncall-dispatch.yml`](oncall-dispatch.yml) | 告警 AI 值班 | [docs/github-workflows/oncall-dispatch.md](../docs/github-workflows/oncall-dispatch.md) |
| [`auto-merge.yml`](auto-merge.yml) | auto-fix PR 自动合并 | [docs/github-workflows/auto-merge.md](../docs/github-workflows/auto-merge.md) |

完整索引见 [docs/github-workflows/README.md](../docs/github-workflows/README.md)。

## 相关配置

- [`.github/auto-fix-allowlist.txt`](../auto-fix-allowlist.txt) — 自动合并允许的文件模式
- [`.cursor/automations/`](../.cursor/automations/) — Cursor Automation 等价配置（云端执行）
- [`docs/runbooks/auto-ops.md`](../docs/runbooks/auto-ops.md) — 自动运维 Runbook
