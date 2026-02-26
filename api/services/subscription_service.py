# -*- coding: utf-8 -*-
"""
订阅管理服务 — CRUD + 平台创作者搜索
"""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.webui_models import Subscription


class CreatorSearchError(RuntimeError):
    """用于将“搜索失败原因”上抛到 router，避免被吞掉导致前端误以为无结果。"""


class WechatSourceUnavailable(CreatorSearchError):
    pass


class WechatSourceAuthInvalid(CreatorSearchError):
    pass


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

    # ------ 平台创作者搜索 ------

    async def search_creators(
        self, session: AsyncSession, platform: str, keyword: str
    ) -> List[dict]:
        """
        搜索创作者 — 通过轻量 HTTP API 实现，不依赖 Playwright 浏览器会话。
        支持两种模式:
          1. 关键词搜索 (bilibili, wechat, weibo)
          2. URL/ID 精确查找 (xhs, dy, ks)
        """
        if platform == "bili":
            return await self._search_bilibili(keyword)
        if platform == "wechat":
            return await self._search_wechat(keyword)
        if platform == "wb":
            return await self._search_weibo(keyword)
        if platform == "xhs":
            return await self._search_xhs(keyword)
        if platform == "dy":
            return await self._search_douyin(keyword)
        # 其他平台暂不支持
        return []

    async def _search_bilibili(self, keyword: str) -> List[dict]:
        """B站用户搜索 — 通过 Web Search API (无需登录)"""
        import httpx

        url = "https://api.bilibili.com/x/web-interface/search/type"
        params = {
            "search_type": "bili_user",
            "keyword": keyword,
            "page": 1,
            "order": "fans",
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://search.bilibili.com/",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=headers, timeout=15)
            data = resp.json()

        results = []
        for item in (data.get("data", {}).get("result", []) or []):
            # B站搜索结果 uname 中有 <em> 高亮标签，需要清理
            uname = (item.get("uname", "") or "").replace("<em class=\"keyword\">", "").replace("</em>", "")
            results.append({
                "creator_id": str(item.get("mid", "")),
                "creator_name": uname,
                "creator_avatar": (item.get("upic", "") or "").replace("//", "https://"),
                "creator_url": f"https://space.bilibili.com/{item.get('mid', '')}",
                "meta": {
                    "fans": item.get("fans", 0),
                    "videos": item.get("videos", 0),
                    "usign": item.get("usign", ""),
                    "level": item.get("level", 0),
                },
            })
        return results[:10]

    async def _search_wechat(self, keyword: str) -> List[dict]:
        """微信公众号搜索 — 通过 wechat-article-exporter 的 public API"""
        import httpx

        from config import wechat_config

        configured_base_url = (getattr(wechat_config, "WECHAT_API_BASE_URL", "") or "").strip().rstrip("/")
        base_urls: List[str] = []
        if configured_base_url:
            base_urls.append(configured_base_url)
        # 常见本地端口（便于开箱即用）
        base_urls.extend([
            "http://localhost:3000",
            "http://localhost:8088",
        ])

        auth_key = (getattr(wechat_config, "WECHAT_AUTH_KEY", "") or "").strip()
        headers = {"X-Auth-Key": auth_key} if auth_key else {}

        last_network_error: Optional[str] = None
        last_auth_error: Optional[str] = None

        for base_url in base_urls:
            try:
                url = f"{base_url.rstrip('/')}/api/public/v1/account"
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        url,
                        params={"keyword": keyword, "size": 10, "begin": 0},
                        headers=headers,
                        timeout=10,
                    )

                try:
                    data = resp.json()
                except Exception:
                    last_network_error = f"微信源返回非 JSON: {base_url}"
                    continue

                # wechat-article-exporter: { base_resp: { ret, err_msg }, list: [...] }
                if isinstance(data, dict) and isinstance(data.get("base_resp"), dict):
                    ret = data["base_resp"].get("ret")
                    if ret not in (0, "0", None):
                        last_auth_error = data["base_resp"].get("err_msg") or "认证信息无效"
                        continue

                # 其他服务兜底: { code, msg, data }
                if isinstance(data, dict) and "code" in data and data.get("code") not in (0, "0", None):
                    last_auth_error = data.get("msg") or "认证信息无效"
                    continue

                results = []
                for item in ((data.get("list", []) if isinstance(data, dict) else None) or []):
                    avatar = (item.get("round_head_img", "") or "")
                    if avatar.startswith("//"):
                        avatar = "https:" + avatar
                    elif avatar.startswith("http://"):
                        avatar = "https://" + avatar[len("http://"):]
                    results.append({
                        "creator_id": item.get("fakeid", ""),
                        "creator_name": item.get("nickname", ""),
                        "creator_avatar": avatar,
                        "creator_url": "",
                        "meta": {
                            "service_type": item.get("service_type", ""),
                            "signature": item.get("signature", ""),
                        },
                    })
                return results
            except httpx.HTTPError as e:
                last_network_error = f"微信源不可达: {base_url} ({e.__class__.__name__})"
                continue
            except Exception as e:
                last_network_error = f"微信源请求失败: {base_url} ({e.__class__.__name__})"
                continue

        if last_auth_error:
            raise WechatSourceAuthInvalid(
                f"微信源认证无效：{last_auth_error}。请先在 wechat-article-exporter 登录并配置 WECHAT_AUTH_KEY（或在 WebUI 配置管理中填入）。"
            )
        raise WechatSourceUnavailable(
            last_network_error
            or "微信源不可达：请确认 wechat-article-exporter 已启动，并检查 WECHAT_API_BASE_URL 配置。"
        )

    async def _search_weibo(self, keyword: str) -> List[dict]:
        """微博用户搜索 — 通过 Web API"""
        import httpx

        url = "https://m.weibo.cn/api/container/getIndex"
        params = {
            "containerid": f"100103type=3&q={keyword}",
            "page_type": "searchall",
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 13_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148",
            "Referer": "https://m.weibo.cn/",
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, headers=headers, timeout=15)
            data = resp.json()

        results = []
        cards = data.get("data", {}).get("cards", []) or []
        for card in cards:
            card_group = card.get("card_group", []) or []
            for item in card_group:
                user = item.get("user")
                if user:
                    results.append({
                        "creator_id": str(user.get("id", "")),
                        "creator_name": user.get("screen_name", ""),
                        "creator_avatar": user.get("profile_image_url", ""),
                        "creator_url": f"https://weibo.com/u/{user.get('id', '')}",
                        "meta": {
                            "description": user.get("description", ""),
                            "followers_count": user.get("followers_count", 0),
                            "verified_reason": user.get("verified_reason", ""),
                        },
                    })
        return results[:10]

    async def _search_xhs(self, keyword: str) -> List[dict]:
        """小红书创作者查找 — 支持 URL / 用户 ID / 关键词搜索

        由于 XHS API 需要 Playwright 签名，WebUI 中采用以下策略:
          1. 输入为创作者主页 URL → 解析 user_id → 抓取主页提取信息
          2. 输入为纯用户 ID (24位十六进制) → 同上
          3. 输入为关键词 → 尝试通过搜索页 SSR 提取去重的作者信息
        """
        import re

        keyword = keyword.strip()

        # 尝试从 URL 中提取 user_id
        url_match = re.search(r"xiaohongshu\.com/user/profile/([a-f0-9]+)", keyword)
        if url_match:
            user_id = url_match.group(1)
            return await self._xhs_fetch_profile(user_id)

        # 纯用户 ID（24 位十六进制）
        if re.fullmatch(r"[a-f0-9]{24}", keyword):
            return await self._xhs_fetch_profile(keyword)

        # 关键词搜索：通过搜索页面 SSR 提取笔记作者
        return await self._xhs_search_by_keyword(keyword)

    async def _xhs_fetch_profile(self, user_id: str) -> List[dict]:
        """通过主页 HTML 获取 XHS 用户信息"""
        import json
        import re
        import httpx

        profile_url = f"https://www.xiaohongshu.com/user/profile/{user_id}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.xiaohongshu.com/",
        }
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(profile_url, headers=headers, timeout=15)
                html = resp.text

            match = re.search(
                r"<script>window\.__INITIAL_STATE__=(.+?)</script>", html, re.M
            )
            if match:
                state = json.loads(
                    match.group(1).replace(":undefined", ":null"), strict=False
                )
                user_data = (state.get("user") or {}).get("userPageData") or {}
                basic = user_data.get("basicInfo") or {}
                interactions = user_data.get("interactions") or []

                # 提取粉丝数
                fans = 0
                for item in interactions:
                    if item.get("type") == "fans":
                        fans_str = item.get("count", "0")
                        try:
                            fans = int(fans_str) if isinstance(fans_str, int) else int(
                                str(fans_str).replace("万", "0000").replace("+", "")
                            )
                        except (ValueError, TypeError):
                            fans = 0

                avatar = basic.get("imageb", "") or basic.get("image", "")
                return [{
                    "creator_id": user_id,
                    "creator_name": basic.get("nickname", user_id),
                    "creator_avatar": avatar,
                    "creator_url": profile_url,
                    "meta": {
                        "desc": basic.get("desc", ""),
                        "gender": basic.get("gender", ""),
                        "fans": fans,
                        "ip_location": basic.get("ipLocation", ""),
                    },
                }]
        except Exception:
            pass

        # 兜底：即使抓取失败也返回可订阅的基本信息
        return [{
            "creator_id": user_id,
            "creator_name": user_id,
            "creator_avatar": "",
            "creator_url": f"https://www.xiaohongshu.com/user/profile/{user_id}",
            "meta": {"note": "无法自动获取用户信息，请确认 ID 正确后订阅"},
        }]

    async def _xhs_search_by_keyword(self, keyword: str) -> List[dict]:
        """通过小红书搜索页面 SSR 提取笔记作者（不需要 API 签名）"""
        import json
        import re
        import httpx

        search_url = f"https://www.xiaohongshu.com/search_result?keyword={keyword}&source=web_search_result_notes"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://www.xiaohongshu.com/",
        }
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(search_url, headers=headers, timeout=15)
                html = resp.text

            match = re.search(
                r"<script>window\.__INITIAL_STATE__=(.+?)</script>", html, re.M
            )
            if match:
                state = json.loads(
                    match.group(1).replace(":undefined", ":null"), strict=False
                )
                feed_items = (state.get("search") or {}).get("feeds") or []
                seen_ids: set = set()
                results: List[dict] = []
                for item in feed_items:
                    note = item.get("note") or item.get("noteCard") or item
                    user = note.get("user") or {}
                    uid = user.get("userId") or user.get("user_id") or ""
                    if not uid or uid in seen_ids:
                        continue
                    seen_ids.add(uid)
                    avatar = user.get("avatar") or user.get("image") or ""
                    if avatar.startswith("//"):
                        avatar = "https:" + avatar
                    results.append({
                        "creator_id": uid,
                        "creator_name": user.get("nickname") or user.get("nick_name") or uid,
                        "creator_avatar": avatar,
                        "creator_url": f"https://www.xiaohongshu.com/user/profile/{uid}",
                        "meta": {},
                    })
                    if len(results) >= 10:
                        break
                return results
        except Exception:
            pass
        # 搜索失败时返回空列表（前端提示用户使用 URL 或手动添加）
        return []

    async def _search_douyin(self, keyword: str) -> List[dict]:
        """抖音创作者查找 — 支持主页 URL 或 sec_uid"""
        import re
        import httpx

        keyword = keyword.strip()

        # 从 URL 提取 sec_uid
        sec_uid = ""
        url_match = re.search(r"douyin\.com/user/([A-Za-z0-9_-]+)", keyword)
        if url_match:
            sec_uid = url_match.group(1)
        elif re.fullmatch(r"MS4wLj[A-Za-z0-9_-]{20,}", keyword):
            sec_uid = keyword

        if sec_uid:
            return [{
                "creator_id": sec_uid,
                "creator_name": sec_uid,
                "creator_avatar": "",
                "creator_url": f"https://www.douyin.com/user/{sec_uid}",
                "meta": {"note": "抖音用户信息需通过爬虫采集获取"},
            }]

        return []


subscription_service = SubscriptionService()
