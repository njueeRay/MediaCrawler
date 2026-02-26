"""最小 E2E：字段映射预览

运行前请启动服务：
  uv run uvicorn api.main:app --host 127.0.0.1 --port 8080 --reload

运行：
  uv run python test/test_field_mapping_preview_e2e.py

验证：
  - sqlite 模式下 /mapping/schemes 可用
  - /mapping/preview 可返回结构（允许 sample_count=0）
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
        # Ensure DB mode so mapping endpoints are usable
        r = await c.put(f"{base}/config", json={"configs": {"SAVE_DATA_OPTION": "sqlite"}})
        if r.status_code != 200:
            print(f"[FAIL] switch sqlite: {r.status_code} {r.text}")
            return 1

        r = await c.get(f"{base}/mapping/schemes", params={"page": 1, "size": 5})
        if r.status_code != 200 or r.json().get("code") != 0:
            print(f"[FAIL] list schemes: {r.status_code} {r.text}")
            return 1
        items = r.json().get("data", {}).get("items", [])
        if not items:
            print("[FAIL] no schemes found (expected seeded system schemes)")
            return 1
        scheme_id = items[0]["id"]

        r = await c.post(f"{base}/mapping/preview", json={"scheme_id": scheme_id, "limit": 1})
        if r.status_code != 200 or r.json().get("code") != 0:
            print(f"[FAIL] preview: {r.status_code} {r.text}")
            return 1

        data = r.json().get("data", {})
        for k in ("original", "mapped", "details", "feishu_fields", "sample_count"):
            if k not in data:
                print(f"[FAIL] missing key: {k}")
                return 1

        print(f"[PASS] scheme_id={scheme_id} sample_count={data.get('sample_count')}")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
