"""最小验证：订阅采集状态持久化（落库 + 恢复）

运行：uv run python test/test_subscription_crawl_status_persistence.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import config as _cfg
from api.services.subscription_crawl_manager import SubscriptionCrawlManager
from api.services.subscription_service import subscription_service
from database.db_session import create_tables, get_session
from database.webui_models import Subscription


async def main() -> int:
    _cfg.SAVE_DATA_OPTION = "sqlite"
    await create_tables("sqlite")

    async with get_session() as session:
        if session is None:
            print("[FAIL] session unavailable")
            return 1

        payload = {
            "platform": "bili",
            "creator_id": "persist_test_creator",
            "creator_name": "持久化测试账号",
            "creator_url": "",
            "creator_avatar": "",
            "creator_meta": {},
            "crawl_config": {},
            "auto_crawl": True,
            "is_active": True,
            "tags": [],
            "notes": "",
        }

        sub = await subscription_service.get_by_platform_creator(
            session, payload["platform"], payload["creator_id"]
        )
        if not sub:
            sub = await subscription_service.create(session, payload)

        sub_id = sub.id

    manager_a = SubscriptionCrawlManager()
    await manager_a._save_status(sub_id, "queued", "持久化测试入队")

    # 用新实例模拟“重启后恢复”
    manager_b = SubscriptionCrawlManager()
    status = await manager_b.get_status([sub_id])
    items = status.get("items", [])
    if not items:
        print("[FAIL] no restored status item")
        return 1

    st = items[0]
    if st.get("status") != "queued":
        print(f"[FAIL] invalid restored status: {st}")
        return 1

    print("[PASS] subscription crawl status persistence ok", st)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
