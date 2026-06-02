# ci.yml — 主 CI 质量门禁

> 对应文件：[`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)

## 作用

项目在 GitHub 上的**主质量门禁**。每次向默认分支提交代码或开 PR 时，在 GitHub 托管 Runner 上执行与本地 `make check` 等价的检查，结果以 Checks 形式展示在 PR 和 commit 页面。

## 何时执行

| 事件 | 条件 |
|------|------|
| `push` | 目标分支为 `main` 或 `master` |
| `pull_request` | 基线分支为 `main` 或 `master` |

**并发控制：**

```yaml
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
```

同一 ref（同一 PR 或同一分支）上若有新的 push，会**取消**尚未完成的旧 CI，避免排队浪费资源。

## 全局环境变量

| 变量 | 值 | 说明 |
|------|-----|------|
| `PYTHON_VERSION` | `3.12` | 与 `.python-version` 一致 |
| `POETRY_VERSION` | `1.8.5` | Poetry 版本 |

## Job 详解

各 Job 除 `docker` 外彼此独立并行；失败任意一个即使整个 Workflow 结论为 `failure`。

### lint — Lint & Format

- **Ruff check**：`poetry run ruff check src tests`
- **Ruff format check**：`poetry run ruff format --check src tests`（只检查格式，不自动改写）

### typecheck — mypy

- 静态类型检查：`poetry run mypy`

### security — Security Scan

| 步骤 | 工具 | 说明 |
|------|------|------|
| Bandit | `bandit -r src` | Python 源码安全扫描 |
| pip-audit | 依赖 CVE 审计 | |
| gitleaks | `gitleaks-action` | 检测密钥泄露，需 `GITHUB_TOKEN` |

### architecture — Architecture

- **import-linter**：`poetry run lint-imports`， enforce 分层依赖（api 不直接 import db）
- **pytest architecture**：`tests/architecture`，架构约束测试

### test — Unit Tests

- `pytest tests/unit -n auto --cov --cov-report=xml`
- 可选上传 Codecov（`continue-on-error: true`，失败不阻断 CI）

### integration — Integration Tests

- `pytest tests/integration -m integration --no-cov`
- 需要 Docker 等集成环境（Runner 上运行）

### sbom — SBOM

- 生成 CycloneDX SBOM：`cyclonedx-py poetry -o sbom.json`
- 上传为 Artifact `sbom`，供供应链审计

### docker — Docker Build

- **依赖**：`needs: [lint, typecheck, test]`，前三项通过后才构建
- 使用 buildx + GHA cache，**仅 build 不 push**（`push: false`）
- 镜像 tag：`myapp:${{ github.sha }}`

### docs — MkDocs

- `mkdocs build --strict`，文档构建失败则 CI 失败

## 与其他工作流的关系

| 下游 | 关系 |
|------|------|
| `ci-auto-fix.yml` | 监听本 Workflow 的 `completed` 事件；失败时可能触发 AI 修复 |
| `auto-merge.yml` | 监听 PR 的 check 完成；本 CI 全绿是自动合并的前提 |
| Cursor Automation | 若配置了 `ciCompleted` 触发器，CI 失败时 Cursor 云端也会启动 Agent（与 `ci-auto-fix.yml` 并行可选） |

## 本地等价命令

```bash
make check   # lint + typecheck + security + arch + test
make integration  # 集成测试需 Docker
```

## 注意事项

- 本 Workflow **不会在** feature 分支 push（未开 PR）时触发，除非该分支是 `main`/`master`。
- Integration、Docker 等 Job 耗时较长；并发取消策略可避免旧 commit 的结果覆盖新 commit 的判断。
