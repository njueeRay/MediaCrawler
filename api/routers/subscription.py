# -*- coding: utf-8 -*-
"""订阅管理路由"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps import get_db
from api.schemas.common import ok, fail, page_ok
from api.schemas.subscription import (
    CreatorSearchRequest,
    SubscriptionCreateRequest,
    SubscriptionUpdateRequest,
)
from api.services.subscription_service import subscription_service

router = APIRouter(prefix="/subscribe", tags=["订阅管理"])


@router.post("/search")
async def search_creators(
    body: CreatorSearchRequest,
    session: AsyncSession = Depends(get_db),
):
    """搜索各平台创作者"""
    results = await subscription_service.search_creators(
        session, body.platform, body.keyword
    )
    return ok({"items": results})


@router.get("")
async def list_subscriptions(
    platform: Optional[str] = None,
    is_active: Optional[bool] = None,
    keyword: Optional[str] = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
):
    """获取订阅列表"""
    items, total = await subscription_service.list(
        session, platform=platform, is_active=is_active,
        keyword=keyword, page=page, size=size,
    )
    rows = []
    for sub in items:
        rows.append({
            "id": sub.id,
            "platform": sub.platform,
            "creator_id": sub.creator_id,
            "creator_name": sub.creator_name,
            "creator_avatar": sub.creator_avatar,
            "creator_url": sub.creator_url,
            "is_active": sub.is_active,
            "auto_crawl": sub.auto_crawl,
            "content_count": sub.content_count,
            "tags": sub.tags or [],
            "last_crawled_at": str(sub.last_crawled_at) if sub.last_crawled_at else None,
            "last_content_at": str(sub.last_content_at) if sub.last_content_at else None,
            "created_at": str(sub.created_at) if sub.created_at else None,
        })
    return page_ok(rows, total, page, size)


@router.post("")
async def create_subscription(
    body: SubscriptionCreateRequest,
    session: AsyncSession = Depends(get_db),
):
    """订阅创作者"""
    existing = await subscription_service.get_by_platform_creator(
        session, body.platform, body.creator_id
    )
    if existing:
        return fail(409, "该创作者已订阅")

    sub = await subscription_service.create(session, body.model_dump())
    return ok({"id": sub.id, "creator_name": sub.creator_name}, message="订阅成功")


@router.get("/stats")
async def subscription_stats(session: AsyncSession = Depends(get_db)):
    """订阅统计"""
    stats = await subscription_service.get_stats(session)
    return ok(stats)


@router.get("/{sub_id}")
async def get_subscription(sub_id: int, session: AsyncSession = Depends(get_db)):
    """获取单个订阅详情"""
    sub = await subscription_service.get_by_id(session, sub_id)
    if not sub:
        raise HTTPException(404, "订阅不存在")
    return ok({
        "id": sub.id,
        "platform": sub.platform,
        "creator_id": sub.creator_id,
        "creator_name": sub.creator_name,
        "creator_avatar": sub.creator_avatar,
        "creator_url": sub.creator_url,
        "creator_meta": sub.creator_meta or {},
        "is_active": sub.is_active,
        "auto_crawl": sub.auto_crawl,
        "crawl_config": sub.crawl_config or {},
        "content_count": sub.content_count,
        "tags": sub.tags or [],
        "notes": sub.notes or "",
        "last_crawled_at": str(sub.last_crawled_at) if sub.last_crawled_at else None,
        "last_content_at": str(sub.last_content_at) if sub.last_content_at else None,
        "created_at": str(sub.created_at) if sub.created_at else None,
    })


@router.put("/{sub_id}")
async def update_subscription(
    sub_id: int,
    body: SubscriptionUpdateRequest,
    session: AsyncSession = Depends(get_db),
):
    """更新订阅"""
    sub = await subscription_service.update(
        session, sub_id, body.model_dump(exclude_unset=True)
    )
    if not sub:
        raise HTTPException(404, "订阅不存在")
    return ok(message="更新成功")


@router.delete("/{sub_id}")
async def delete_subscription(sub_id: int, session: AsyncSession = Depends(get_db)):
    """取消订阅"""
    deleted = await subscription_service.delete(session, sub_id)
    if not deleted:
        raise HTTPException(404, "订阅不存在")
    return ok(message="已取消订阅")


@router.post("/{sub_id}/crawl")
async def trigger_crawl(sub_id: int, session: AsyncSession = Depends(get_db)):
    """
    手动触发单个订阅的采集 — 调用 CrawlerManager 启动爬虫子进程。
    """
    sub = await subscription_service.get_by_id(session, sub_id)
    if not sub:
        raise HTTPException(404, "订阅不存在")

    from api.services.crawler_manager import crawler_manager
    from api.schemas import CrawlerStartRequest

    # 检查是否有正在运行的爬虫
    status = crawler_manager.get_status()
    if status.get("status") == "running":
        return fail(409, "已有爬虫任务正在运行，请等待完成后再试")

    # 根据订阅信息构建采集配置
    crawl_config = sub.crawl_config or {}
    start_request = CrawlerStartRequest(
        platform=sub.platform,
        login_type=crawl_config.get("login_type", "cookie"),
        crawler_type="creator",
        creator_ids=sub.creator_id,
        save_option=crawl_config.get("save_option", "json"),
        enable_comments=crawl_config.get("enable_comments", False),
        enable_sub_comments=crawl_config.get("enable_sub_comments", False),
        headless=crawl_config.get("headless", True),
    )

    started = await crawler_manager.start(start_request)
    if not started:
        return fail(500, "启动采集失败，请查看日志")

    # 更新最后采集时间
    from datetime import datetime
    sub.last_crawled_at = datetime.now()
    await session.flush()

    return ok(message=f"已触发 {sub.creator_name} 的采集任务")
