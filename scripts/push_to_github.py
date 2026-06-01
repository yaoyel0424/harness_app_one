#!/usr/bin/env python3
"""
将本地仓库推送到 GitHub（创建远程仓库 + 设置 origin + push）。

从 .env 读取:
  GITHUB_TOKEN  - PAT，需 repo 权限
  GITHUB_REPO   - owner/repo，例如 myuser/harness

用法:
  poetry run python scripts/push_to_github.py
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"


def load_env(path: Path) -> dict[str, str]:
    """解析 .env 键值。"""
    if not path.exists():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


def github_request(
    method: str,
    url: str,
    token: str,
    body: dict | None = None,
) -> dict:
    """调用 GitHub REST API。"""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else {}


def run_git(*args: str) -> None:
    """运行 git 命令。"""
    subprocess.run(["git", *args], cwd=PROJECT_ROOT, check=True)


def main() -> int:
    """入口。"""
    env = load_env(ENV_FILE)
    token = env.get("GITHUB_TOKEN", "")
    repo = env.get("GITHUB_REPO", "")

    if not token or "xxxx" in token or not (
        token.startswith("ghp_") or token.startswith("github_pat_")
    ):
        print("错误: 请在 .env 中配置有效的 GITHUB_TOKEN", file=sys.stderr)
        return 1

    if not repo or repo == "your-org/harness" or "/" not in repo:
        user = github_request("GET", "https://api.github.com/user", token)
        login = user["login"]
        repo = f"{login}/harness"
        print(f"未设置 GITHUB_REPO，将使用: {repo}")

    owner, name = repo.split("/", 1)
    repo_api = f"https://api.github.com/repos/{owner}/{name}"

    # 检查仓库是否存在
    try:
        github_request("GET", repo_api, token)
        print(f"远程仓库已存在: {repo}")
    except urllib.error.HTTPError as err:
        if err.code != 404:
            print(f"错误: 查询仓库失败 HTTP {err.code}", file=sys.stderr)
            return 1
        print(f"正在创建仓库: {repo}")
        github_request(
            "POST",
            "https://api.github.com/user/repos",
            token,
            {
                "name": name,
                "description": "FastAPI 全栈工程模板（harness）",
                "private": False,
                "auto_init": False,
            },
        )

    remote_url = f"https://{token}@github.com/{owner}/{name}.git"

    # 设置 remote
    remotes = subprocess.run(
        ["git", "remote"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    if "origin" in remotes.stdout.split():
        run_git("remote", "set-url", "origin", remote_url)
    else:
        run_git("remote", "add", "origin", remote_url)

    run_git("branch", "-M", "main")
    print("正在推送到 origin main ...")
    run_git("push", "-u", "origin", "main")

    # 恢复不含 token 的 remote URL（避免 token 写入 git config 明文）
    run_git("remote", "set-url", "origin", f"https://github.com/{owner}/{name}.git")

    print(f"完成: https://github.com/{owner}/{name}")
    print(f"请更新 .env: GITHUB_REPO={repo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
