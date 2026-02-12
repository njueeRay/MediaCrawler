"""最小 E2E：批量触发订阅采集 + 状态查询 + 配置自检

运行前请启动服务：uv run uvicorn api.main:app --port 8080
运行：uv run python test/test_subscription_batch_crawl_e2e.py

说明：
- 本测试不要求爬虫真正跑完，只验证：
  1) 批量入队接口可用
  2) 状态接口可查询到 queued/running 等状态
  3) config/validate 正常返回结构
"""

import asyncio
import sys

import httpx

BASE = "http://localhost:8080/api"


async def main() -> int:
    async with httpx.AsyncClient(timeout=20) as c:
        # 1) validate should always work
        r = await c.get(f"{BASE}/config/validate")
        if r.status_code != 200 or r.json().get("code") != 0:
            print(f"[FAIL] GET /config/validate: {r.status_code} {r.text}")
            return 1

        # 2) switch to sqlite for subscription endpoints
        r = await c.put(f"{BASE}/config", json={"configs": {"SAVE_DATA_OPTION": "sqlite"}})
        if r.status_code != 200:
            print(f"[FAIL] switch sqlite: {r.status_code} {r.text}")
            return 1

        # 3) create two subscriptions (use bili to avoid special platform constraints)
        for i in range(2):
            payload = {"platform": "bili", "creator_id": f"batch_{i}", "creator_name": f"批量测试{i}"}
            rr = await c.post(f"{BASE}/subscribe", json=payload)
            if rr.status_code not in (200, 409):
                print(f"[FAIL] create sub: {rr.status_code} {rr.text}")
                return 1

        r = await c.get(f"{BASE}/subscribe", params={"platform": "bili", "size": 50})
        if r.status_code != 200:
            print(f"[FAIL] list subs: {r.status_code} {r.text}")
            return 1

        items = r.json().get("data", {}).get("items", [])
        ids = [x["id"] for x in items if x.get("creator_id", "").startswith("batch_")]
        if len(ids) < 2:
            print("[FAIL] expected >=2 subs")
            return 1

        # 4) batch enqueue
        r = await c.post(f"{BASE}/subscribe/crawl/batch", json={"ids": ids})
        if r.status_code != 200 or r.json().get("code") != 0:
            print(f"[FAIL] batch enqueue: {r.status_code} {r.text}")
            return 1

        # 5) status should include these ids
        r = await c.get(f"{BASE}/subscribe/crawl/status", params={"ids": ",".join(str(x) for x in ids)})
        if r.status_code != 200 or r.json().get("code") != 0:
            print(f"[FAIL] crawl status: {r.status_code} {r.text}")
            return 1

        st_items = r.json().get("data", {}).get("items", [])
        st_map = {x["sub_id"]: x["status"] for x in st_items}
        for sid in ids:
            if sid not in st_map:
                print(f"[FAIL] missing status for {sid}")
                return 1

        print("[PASS] batch enqueue + status ok", st_map)

        # 6) best-effort stop crawler to avoid long running
        try:
            await c.post(f"{BASE}/crawler/stop")
        except Exception:
            pass

        # switch back
        await c.put(f"{BASE}/config", json={"configs": {"SAVE_DATA_OPTION": "csv"}})
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
