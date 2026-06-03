"""临时脚本：测试数据库连接。"""

import asyncio
import os

import asyncpg

# Docker PostgreSQL 宿主机映射端口（默认 5433）
DOCKER_PG_PORT = int(os.getenv("DOCKER_PG_PORT", "5433"))


async def main() -> None:
    for host in ("127.0.0.1", "localhost"):
        try:
            conn = await asyncpg.connect(
                host=host,
                port=DOCKER_PG_PORT,
                user="myapp",
                password="myapp",
                database="myapp",
            )
            val = await conn.fetchval("SELECT 1")
            await conn.close()
            print(f"{host}:{DOCKER_PG_PORT} OK -> {val}")
        except Exception as exc:
            print(f"{host}:{DOCKER_PG_PORT} FAIL -> {exc!r}")


if __name__ == "__main__":
    asyncio.run(main())
