"""
最小 E2E：验证微信订阅触发采集不再被 schema 拒绝（422）
运行前请启动服务：uv run uvicorn api.main:app --port 8080
运行：uv run python test/test_subscription_wechat_e2e.py
"""

import asyncio
import sys

import httpx

BASE = "http://localhost:8080/api"


async def main() -> int:
    async with httpx.AsyncClient(timeout=20) as c:
        # 切到 sqlite，确保订阅接口可用
        r = await c.put(f"{BASE}/config", json={"configs": {"SAVE_DATA_OPTION": "sqlite"}})
        if r.status_code != 200:
            print(f"[FAIL] switch to sqlite failed: {r.status_code} {r.text}")
            return 1

        # 创建一个微信订阅
        payload = {
            "platform": "wechat",
            "creator_id": "Mzk0NDc0ODg4Ng==",
            "creator_name": "E2E微信测试号",
        }
        r = await c.post(f"{BASE}/subscribe", json=payload)
        if r.status_code not in (200, 409):
            print(f"[FAIL] create subscription unexpected: {r.status_code} {r.text}")
            return 1

        # 获取该订阅 ID
        r = await c.get(f"{BASE}/subscribe", params={"platform": "wechat", "size": 50})
        if r.status_code != 200:
            print(f"[FAIL] list subscribe failed: {r.status_code} {r.text}")
            return 1

        items = r.json().get("data", {}).get("items", [])
        target = next((x for x in items if x.get("creator_id") == payload["creator_id"]), None)
        if not target:
            print("[FAIL] target subscription not found")
            return 1

        sub_id = target["id"]

        # 触发采集：关键是不能再 422（platform=wechat schema reject）
        r = await c.post(f"{BASE}/subscribe/{sub_id}/crawl")
        if r.status_code == 422:
            print(f"[FAIL] still schema-rejected: {r.text}")
            return 1

        if r.status_code in (200, 409, 500):
            print(f"[PASS] crawl trigger accepted by schema, status={r.status_code}")
        else:
            print(f"[FAIL] unexpected status: {r.status_code} {r.text}")
            return 1

        # 切回 csv，避免污染默认流程
        await c.put(f"{BASE}/config", json={"configs": {"SAVE_DATA_OPTION": "csv"}})

        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
