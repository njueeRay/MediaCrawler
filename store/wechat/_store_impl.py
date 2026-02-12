# -*- coding: utf-8 -*-
# @Desc : 微信公众号存储实现 (CSV / JSON / DB / SQLite / MongoDB / Excel)

import json
from typing import Dict

import config
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from base.base_crawler import AbstractStore
from tools.async_file_writer import AsyncFileWriter
from tools.time_util import get_current_timestamp
from var import crawler_type_var


# ==================== CSV ====================

class WechatCsvStoreImplement(AbstractStore):
    """CSV 文件存储实现"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.writer = AsyncFileWriter(platform="wechat", crawler_type=crawler_type_var.get())

    async def store_content(self, content_item: Dict):
        await self.writer.write_to_csv_with_dedup(
            item=content_item,
            item_type="contents",
            dedup_key="article_id",
            replace_on_dup=getattr(config, "WECHAT_CSV_DEDUP_ON_WRITE", True),
        )

    async def store_comment(self, comment_item: Dict):
        await self.writer.write_to_csv(item_type="comments", item=comment_item)

    async def store_creator(self, creator_item: Dict):
        await self.writer.write_to_csv(item_type="creators", item=creator_item)


# ==================== JSON ====================

class WechatJsonStoreImplement(AbstractStore):
    """JSON 文件存储实现"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.writer = AsyncFileWriter(platform="wechat", crawler_type=crawler_type_var.get())

    async def store_content(self, content_item: Dict):
        await self.writer.write_single_item_to_json(item_type="contents", item=content_item)

    async def store_comment(self, comment_item: Dict):
        await self.writer.write_single_item_to_json(item_type="comments", item=comment_item)

    async def store_creator(self, creator_item: Dict):
        await self.writer.write_single_item_to_json(item_type="creators", item=creator_item)


# ==================== DB (MySQL / PostgreSQL) ====================

class WechatDbStoreImplement(AbstractStore):
    """关系型数据库存储实现 (MySQL / PostgreSQL / SQLite)"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    # ---------- content (article) ----------

    async def store_content(self, content_item: Dict):
        from database.db_session import get_session
        article_id = content_item.get("article_id")
        if not article_id:
            return
        async with get_session() as session:
            if await self._content_exists(session, article_id):
                await self._update_content(session, content_item)
            else:
                await self._add_content(session, content_item)

    async def _add_content(self, session: AsyncSession, item: Dict):
        from database.models import WechatArticle
        article = WechatArticle(
            article_id=item.get("article_id"),
            fakeid=item.get("fakeid", ""),
            title=item.get("title"),
            link=item.get("link"),
            digest=item.get("digest"),
            content=item.get("content", ""),
            author_name=item.get("author_name"),
            account_nickname=item.get("account_nickname"),
            item_show_type=item.get("item_show_type", "普通图文"),
            create_time_str=item.get("create_time_str"),
            update_time_str=item.get("update_time_str"),
            cover=item.get("cover", ""),
            image_list=item.get("image_list", ""),
            source_keyword=item.get("source_keyword", ""),
            add_ts=item.get("add_ts", ""),
        )
        session.add(article)

    async def _update_content(self, session: AsyncSession, item: Dict):
        from database.models import WechatArticle
        update_vals = {
            "cover": item.get("cover", ""),
            "image_list": item.get("image_list", ""),
            "source_keyword": item.get("source_keyword", ""),
        }
        # 仅在有内容时更新 content 字段（避免空值覆盖已有内容）
        if item.get("content"):
            update_vals["content"] = item["content"]
        stmt = (
            update(WechatArticle)
            .where(WechatArticle.article_id == item.get("article_id"))
            .values(**update_vals)
        )
        await session.execute(stmt)

    async def _content_exists(self, session: AsyncSession, article_id: str) -> bool:
        from database.models import WechatArticle
        stmt = select(WechatArticle).where(WechatArticle.article_id == article_id)
        result = await session.execute(stmt)
        return result.first() is not None

    # ---------- comment ----------

    async def store_comment(self, comment_item: Dict):
        """评论存储 — 预留接口，待后续实现"""
        pass

    # ---------- creator ----------

    async def store_creator(self, creator_item: Dict):
        from database.db_session import get_session
        fakeid = creator_item.get("fakeid")
        if not fakeid:
            return
        async with get_session() as session:
            if await self._creator_exists(session, fakeid):
                await self._update_creator(session, creator_item)
            else:
                await self._add_creator(session, creator_item)

    async def _add_creator(self, session: AsyncSession, item: Dict):
        from database.models import WechatCreator
        now = int(get_current_timestamp())
        creator = WechatCreator(
            fakeid=item.get("fakeid"),
            nickname=item.get("nickname"),
            alias=item.get("alias"),
            round_head_img=item.get("round_head_img"),
            signature=item.get("signature"),
            service_type=item.get("service_type", 0),
            verify_status=item.get("verify_status", 0),
            identity_name=item.get("identity_name"),
            original_article_count=item.get("original_article_count", 0),
            intro=item.get("intro"),
            org=item.get("org"),
            account_type=item.get("account_type"),
            ip_location=item.get("ip_location"),
            add_ts=now,
            last_modify_ts=now,
        )
        session.add(creator)

    async def _update_creator(self, session: AsyncSession, item: Dict):
        from database.models import WechatCreator
        now = int(get_current_timestamp())
        stmt = (
            update(WechatCreator)
            .where(WechatCreator.fakeid == item.get("fakeid"))
            .values(
                last_modify_ts=now,
                nickname=item.get("nickname"),
                alias=item.get("alias"),
                round_head_img=item.get("round_head_img"),
                signature=item.get("signature"),
                identity_name=item.get("identity_name"),
                original_article_count=item.get("original_article_count", 0),
                intro=item.get("intro"),
                org=item.get("org"),
                account_type=item.get("account_type"),
                ip_location=item.get("ip_location"),
            )
        )
        await session.execute(stmt)

    async def _creator_exists(self, session: AsyncSession, fakeid: str) -> bool:
        from database.models import WechatCreator
        stmt = select(WechatCreator).where(WechatCreator.fakeid == fakeid)
        result = await session.execute(stmt)
        return result.first() is not None


# ==================== SQLite ====================

class WechatSqliteStoreImplement(WechatDbStoreImplement):
    """SQLite 存储实现 — 复用 DB 实现（engine 由 db_session 根据 SAVE_DATA_OPTION 自动切换）"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)


# ==================== MongoDB ====================

class WechatMongoStoreImplement(AbstractStore):
    """MongoDB 存储实现"""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        from database.mongodb_store_base import MongoDBStoreBase
        self.mongo_store = MongoDBStoreBase(collection_prefix="wechat")

    async def store_content(self, content_item: Dict):
        article_id = content_item.get("article_id")
        if not article_id:
            return
        await self.mongo_store.save_or_update(
            collection_suffix="contents",
            query={"article_id": article_id},
            data=content_item,
        )

    async def store_comment(self, comment_item: Dict):
        comment_id = comment_item.get("comment_id")
        if not comment_id:
            return
        await self.mongo_store.save_or_update(
            collection_suffix="comments",
            query={"comment_id": comment_id},
            data=comment_item,
        )

    async def store_creator(self, creator_item: Dict):
        fakeid = creator_item.get("fakeid")
        if not fakeid:
            return
        await self.mongo_store.save_or_update(
            collection_suffix="creators",
            query={"fakeid": fakeid},
            data=creator_item,
        )


# ==================== Excel ====================

class WechatExcelStoreImplement:
    """Excel 存储实现 — 通过 ExcelStoreBase 单例管理"""

    def __new__(cls, *args, **kwargs):
        from store.excel_store_base import ExcelStoreBase
        return ExcelStoreBase.get_instance(
            platform="wechat",
            crawler_type=crawler_type_var.get(),
        )
