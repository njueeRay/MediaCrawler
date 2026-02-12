"""最小 E2E：DB 浏览 API

运行前请启动服务：
  uv run uvicorn api.main:app --host 127.0.0.1 --port 8080 --reload

运行：
  uv run python test/test_db_browse_e2e.py

验证：
  - CSV 模式下 /data/db/* 返回 400（数据库未配置）
  - 切到 sqlite 后 /data/db/tables 与 /data/db/records 可用
"""

import asyncio
import os

import httpx


def _base() -> str:
    host = os.environ.get("WEBUI_HOST", "127.0.0.1")
    port = os.environ.get("WEBUI_PORT", "8080")
    return f"http://{host}:{port}/api"


async def main() -> int:
    base = _base()
    async with httpx.AsyncClient(timeout=20) as c:
        # 1) validate should always work
        r = await c.get(f"{base}/config/validate")
        if r.status_code != 200 or r.json().get("code") != 0:
            print(f"[FAIL] GET /config/validate: {r.status_code} {r.text}")
            return 1

        # 2) Force CSV mode then assert DB browse is blocked
        await c.put(f"{base}/config", json={"configs": {"SAVE_DATA_OPTION": "csv"}})

        r = await c.get(f"{base}/data/db/tables")
        if r.status_code != 400:
            print(f"[FAIL] expected 400 in CSV mode: {r.status_code} {r.text}")
            return 1

        # 3) Switch to sqlite
        r = await c.put(f"{base}/config", json={"configs": {"SAVE_DATA_OPTION": "sqlite"}})
        if r.status_code != 200:
            print(f"[FAIL] switch sqlite: {r.status_code} {r.text}")
            return 1

        # 4) Tables
        r = await c.get(f"{base}/data/db/tables")
        if r.status_code != 200:
            print(f"[FAIL] GET /data/db/tables: {r.status_code} {r.text}")
            return 1
        body = r.json()
        if body.get("code") != 0:
            print(f"[FAIL] /data/db/tables code!=0: {body}")
            return 1
        items = body.get("data", {}).get("items", [])
        if not isinstance(items, list) or len(items) == 0:
            print(f"[FAIL] /data/db/tables items empty: {body}")
            return 1

        # 5) Records preview for first known table
        table = items[0].get("table")
        if not table:
            print(f"[FAIL] invalid table entry: {items[0]}")
            return 1

        r = await c.get(f"{base}/data/db/records", params={"table": table, "limit": 5, "offset": 0})
        if r.status_code != 200:
            print(f"[FAIL] GET /data/db/records: {r.status_code} {r.text}")
            return 1
        body = r.json()
        if body.get("code") != 0:
            print(f"[FAIL] /data/db/records code!=0: {body}")
            return 1

        print(f"[PASS] tables={len(items)} preview_table={table} preview_records={len(body.get('data', {}).get('records', []))}")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
