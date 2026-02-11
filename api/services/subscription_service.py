# -*- coding: utf-8 -*-
"""
订阅管理服务 — CRUD + 平台创作者搜索
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.webui_models import Subscription


class SubscriptionService:
    """订阅管理"""

    # ------ CRUD ------

    async def create(self, session: AsyncSession, data: dict) -> Subscription:
        sub = Subscription(**data)
        session.add(sub)
        await session.flush()
        await session.refresh(sub)
        return sub

    async def get_by_id(self, session: AsyncSession, sub_id: int) -> Optional[Subscription]:
        result = await session.execute(
            select(Subscription).where(Subscription.id == sub_id)
        )
        return result.scalars().first()

    async def list(
        self,
        session: AsyncSession,
        platform: Optional[str] = None,
        is_active: Optional[bool] = None,
        tag: Optional[str] = None,
        keyword: Optional[str] = None,
        page: int = 1,
        size: int = 20,
    ) -> Tuple[List[Subscription], int]:
        q = select(Subscription)
        count_q = select(func.count()).select_from(Subscription)

        if platform:
            q = q.where(Subscription.platform == platform)
            count_q = count_q.where(Subscription.platform == platform)
        if is_active is not None:
            q = q.where(Subscription.is_active == is_active)
            count_q = count_q.where(Subscription.is_active == is_active)
        if keyword:
            like = f"%{keyword}%"
            q = q.where(Subscription.creator_name.ilike(like))
            count_q = count_q.where(Subscription.creator_name.ilike(like))

        total = (await session.execute(count_q)).scalar() or 0
        result = await session.execute(
            q.order_by(Subscription.updated_at.desc())
            .offset((page - 1) * size)
            .limit(size)
        )
        return result.scalars().all(), total

    async def update(self, session: AsyncSession, sub_id: int, data: dict) -> Optional[Subscription]:
        sub = await self.get_by_id(session, sub_id)
        if not sub:
            return None
        for k, v in data.items():
            if v is not None:
                setattr(sub, k, v)
        await session.flush()
        await session.refresh(sub)
        return sub

    async def delete(self, session: AsyncSession, sub_id: int) -> bool:
        result = await session.execute(
            delete(Subscription).where(Subscription.id == sub_id)
        )
        return result.rowcount > 0

    async def get_by_platform_creator(
        self, session: AsyncSession, platform: str, creator_id: str
    ) -> Optional[Subscription]:
        result = await session.execute(
            select(Subscription).where(
                Subscription.platform == platform,
                Subscription.creator_id == creator_id,
            )
        )
        return result.scalars().first()

    async def get_stats(self, session: AsyncSession) -> Dict:
        """订阅统计"""
        total = (await session.execute(
            select(func.count()).select_from(Subscription)
        )).scalar() or 0
        active = (await session.execute(
            select(func.count()).select_from(Subscription)
            .where(Subscription.is_active == True)
        )).scalar() or 0

        # per-platform counts
        rows = (await session.execute(
            select(Subscription.platform, func.count())
            .group_by(Subscription.platform)
        )).all()
        by_platform = {r[0]: r[1] for r in rows}

        return {"total": total, "active": active, "by_platform": by_platform}

    # ------ 平台创作者搜索 (TODO: 接入各平台 Client) ------

    async def search_creators(
        self, session: AsyncSession, platform: str, keyword: str
    ) -> List[dict]:
        """
        搜索创作者 — Phase 2 时实现各平台适配器。
        目前返回空列表。
        """
        # TODO Phase 2: 根据 platform 调用对应的搜索逻辑
        # - xhs: media_platform/xhs/client.py → search_creators
        # - wechat: wechat-article-exporter API
        # - dy / bili / wb / ks / tieba / zhihu: 各平台 client
        return []


subscription_service = SubscriptionService()
