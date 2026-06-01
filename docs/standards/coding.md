# 编码规范

## 格式化与 Lint

- 使用 **Ruff** 统一 lint 与 format，行宽 100
- 提交前通过 `pre-commit` 自动检查

## 类型注解

- 所有公开函数必须有类型注解
- 启用 mypy `strict` 模式
- Pydantic 模型用于 API 边界验证

## 分层约定

- API 层只做参数校验与响应映射，不含业务逻辑
- 业务逻辑放在 `core/services/`
- 数据库操作封装在 `db/repositories/`
- 禁止在业务层直接使用 `requests`，须通过 `utils/http_client.py`

## 日志

- 使用 `myapp.utils.logging.get_logger()` 获取日志器
- 生产环境输出 JSON 格式，便于 Loki 索引

## 命名

- 文件：kebab-case（脚本）或 snake_case（Python 模块）
- 类：PascalCase
- 函数/变量：snake_case
