"""
Phase 4 — 端到端集成测试
从 CSV 模式启动 → 切换 SQLite → 验证所有 DB 依赖端点
"""
import asyncio
import httpx
import os
import sys
import uuid

BASE = os.getenv("WEBUI_API_BASE", "http://127.0.0.1:8080/api").rstrip("/")

async def main():
    async with httpx.AsyncClient(timeout=15) as c:
        passed = 0
        failed = 0

        def check(name, ok, detail=""):
            nonlocal passed, failed
            if ok:
                passed += 1
                print(f"  ✓ {name}")
            else:
                failed += 1
                print(f"  ✗ {name} — {detail}")

        # ==== Phase A: CSV mode tests ====
        print("\n=== Phase A: CSV 模式 ===")

        r = await c.get(f"{BASE}/config/groups")
        check("GET /config/groups", r.status_code == 200 and r.json()["code"] == 0)

        data = r.json()["data"]["groups"]
        group_keys = [g["key"] for g in data]
        check("Config has 6+ groups", len(data) >= 6, f"got {len(data)}: {group_keys}")

        # database group should have SAVE_DATA_OPTION field with value "csv"
        db_group = next((g for g in data if g["key"] == "database"), None)
        sdo = next((f for f in db_group["fields"] if f["key"] == "SAVE_DATA_OPTION"), None) if db_group else None
        check("SAVE_DATA_OPTION shows csv", sdo and sdo["value"] == "csv", f"got: {sdo['value'] if sdo else 'N/A'}")

        # DB-dependent endpoints should 400
        r = await c.get(f"{BASE}/subscribe")
        check("GET /subscribe → 400 in CSV mode", r.status_code == 400)

        r = await c.get(f"{BASE}/scheduler/tasks")
        check("GET /scheduler/tasks → 400 in CSV mode", r.status_code == 400)

        # PUT /config should work even in CSV mode (the fix!)
        r = await c.put(f"{BASE}/config", json={"configs": {"KEYWORDS": "test123"}})
        check("PUT /config works in CSV mode", r.status_code == 200 and r.json()["code"] == 0)

        # Config history should return empty (no DB), not 400
        r = await c.get(f"{BASE}/config/history")
        check("GET /config/history → 200 in CSV mode", r.status_code == 200)

        # Dashboard should always work
        r = await c.get(f"{BASE}/dashboard")
        check("GET /dashboard", r.status_code == 200)

        # Data files should always work
        r = await c.get(f"{BASE}/data/files")
        check("GET /data/files", r.status_code == 200)

        # ==== Phase B: Switch to SQLite ====
        print("\n=== Phase B: 切换到 SQLite ===")

        r = await c.put(f"{BASE}/config", json={"configs": {"SAVE_DATA_OPTION": "sqlite"}})
        check("PUT /config SAVE_DATA_OPTION=sqlite", r.status_code == 200)
        body = r.json()
        check("db_switched=true", body["data"].get("db_switched") == True)

        # ==== Phase C: SQLite mode tests ====
        print("\n=== Phase C: SQLite 模式 ===")

        r = await c.get(f"{BASE}/subscribe")
        check("GET /subscribe → 200", r.status_code == 200 and r.json()["code"] == 0)

        r = await c.get(f"{BASE}/scheduler/tasks")
        check("GET /scheduler/tasks → 200", r.status_code == 200 and r.json()["code"] == 0)

        r = await c.get(f"{BASE}/mapping/schemes")
        check("GET /mapping/schemes → 200", r.status_code == 200)
        schemes = r.json()["data"]
        check("System mapping schemes seeded", schemes["total"] >= 4, f"got {schemes['total']}")

        r = await c.get(f"{BASE}/feishu/status")
        check("GET /feishu/status → 200", r.status_code == 200)

        r = await c.get(f"{BASE}/config/history")
        check("GET /config/history → 200 with DB", r.status_code == 200)

        # Test connection (database)
        r = await c.post(f"{BASE}/config/test", json={"type": "database"})
        check("POST /config/test database", r.status_code == 200 and r.json()["data"]["success"])

        # Create a subscription
        creator_id = f"test_{uuid.uuid4().hex[:8]}"
        r = await c.post(f"{BASE}/subscribe", json={
            "platform": "bili",
            "creator_id": creator_id,
            "creator_name": f"测试用户_{creator_id}",
        })
        check("POST /subscribe create", r.status_code == 200 and r.json()["code"] == 0)

        # List subscriptions
        r = await c.get(f"{BASE}/subscribe")
        items = r.json()["data"]["items"]
        check("GET /subscribe returns created item", len(items) >= 1)

        # Create scheduled task
        task_name = f"测试任务_{uuid.uuid4().hex[:8]}"
        r = await c.post(f"{BASE}/scheduler/tasks", json={
            "name": task_name,
            "task_type": "crawl",
            "platform": "bili",
            "schedule_type": "interval",
            "schedule_config": {"hours": 6},
        })
        check("POST /scheduler/tasks create", r.status_code == 200 and r.json()["code"] == 0)

        # Toggle task
        r = await c.get(f"{BASE}/scheduler/tasks")
        tasks = r.json()["data"]["items"]
        if tasks:
            tid = tasks[0]["id"]
            r = await c.put(f"{BASE}/scheduler/tasks/{tid}", json={"is_active": False})
            check("PUT /scheduler/tasks toggle", r.status_code == 200)

        # Config groups should now show sqlite
        r = await c.get(f"{BASE}/config/groups")
        db_group = next((g for g in r.json()["data"]["groups"] if g["key"] == "database"), None)
        sdo = next((f for f in db_group["fields"] if f["key"] == "SAVE_DATA_OPTION"), None) if db_group else None
        check("Config now shows sqlite", sdo and sdo["value"] == "sqlite", f"got: {sdo['value'] if sdo else 'N/A'}")

        # ==== Phase D: Switch back to CSV ====
        print("\n=== Phase D: 切换回 CSV ===")

        r = await c.put(f"{BASE}/config", json={"configs": {"SAVE_DATA_OPTION": "csv"}})
        check("PUT /config SAVE_DATA_OPTION=csv", r.status_code == 200)

        r = await c.get(f"{BASE}/subscribe")
        check("GET /subscribe → 400 after switch back", r.status_code == 400)

        # ==== Summary ====
        print(f"\n{'='*40}")
        print(f"结果: {passed} passed, {failed} failed")
        print(f"{'='*40}")
        sys.exit(0 if failed == 0 else 1)

asyncio.run(main())
