# ---------------------------------------------------------------------------
# Makefile：统一团队操作入口
# ---------------------------------------------------------------------------

.PHONY: help install check lint format typecheck security arch test cov integration docker-build docs docs-serve docs-up sbom pre-commit

help: ## 显示帮助
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

install: ## 安装依赖（Poetry）
	poetry install --with dev

pre-commit: ## 安装 pre-commit 钩子
	poetry run pre-commit install

check: lint typecheck security arch test ## 运行全部质量门禁

lint: ## Ruff linter
	poetry run ruff check src tests

format: ## Ruff formatter
	poetry run ruff format src tests
	poetry run ruff check --fix src tests

typecheck: ## mypy 静态类型检查
	poetry run mypy

security: ## Bandit + pip-audit 安全扫描
	poetry run bandit -r src -c pyproject.toml
	poetry run pip-audit

arch: ## import-linter 架构约束
	poetry run lint-imports

test: ## 单元测试 + 覆盖率
	poetry run pytest tests/unit tests/architecture -n auto

integration: ## 集成测试（需要 Docker）
	poetry run pytest tests/integration -m integration

cov: test ## 别名：带覆盖率测试

run: ## 开发模式启动
	poetry run myapp

docker-build: ## 构建 Docker 镜像
	docker build -t myapp:latest .

docs: ## 构建 MkDocs 文档
	poetry run mkdocs build --strict

docs-serve: ## 本地预览 MkDocs（http://127.0.0.1:8001）
	poetry run mkdocs serve

docs-up: ## Docker 启动文档站（http://127.0.0.1:8001）
	docker compose up -d docs --build

sbom: ## 生成 CycloneDX SBOM
	poetry run cyclonedx-py poetry -o sbom.json

validate-worktree: ## 验证 worktree 环境
	bash scripts/validate_worktree.sh
