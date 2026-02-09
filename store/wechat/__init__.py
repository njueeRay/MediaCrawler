# -*- coding: utf-8 -*-
# @Desc : 微信公众号数据存储层
#
# 遵循 MediaCrawler store 模式:
#   - WechatStoreFactory 根据 config.SAVE_DATA_OPTION 选择存储实现
#   - update_wechat_article() 规范化文章数据后调用 store
#   - save_creator() 保存公众号创作者信息

from typing import Dict

import config
from tools import utils
from var import crawler_type_var

from ._store_impl import *


class WechatStoreFactory:
    STORES = {
        "csv": WechatCsvStoreImplement,
        "db": WechatDbStoreImplement,
        "postgres": WechatDbStoreImplement,
        "json": WechatJsonStoreImplement,
        "sqlite": WechatSqliteStoreImplement,
        "mongodb": WechatMongoStoreImplement,
        "excel": WechatExcelStoreImplement,
    }

    @staticmethod
    def create_store() -> "AbstractStore":
        store_class = WechatStoreFactory.STORES.get(config.SAVE_DATA_OPTION)
        if not store_class:
            raise ValueError(
                f"[WechatStoreFactory] 不支持的存储类型: {config.SAVE_DATA_OPTION}"
                f"\n微信模块当前支持: {', '.join(WechatStoreFactory.STORES.keys())}"
            )
        return store_class()


async def update_wechat_article(article_item: Dict) -> None:
    """
    保存/更新微信公众号文章数据

    Args:
        article_item: 已规范化的文章数据字典，包含以下关键字段:
            - article_id: 文章唯一标识
            - title: 文章标题
            - link: 文章链接
            - author_name: 作者名
            - account_nickname: 公众号昵称
            - create_time: 创建时间戳
            - update_time: 更新时间戳
            - content_format: 内容格式 (html/markdown/text/json)
            - content_length: 内容长度
            - last_modify_ts: 最后修改时间戳 (MediaCrawler 生成)
    """
    utils.logger.info(f"[store.wechat.update_wechat_article] article: {article_item.get('title', '')}")
    await WechatStoreFactory.create_store().store_content(article_item)


async def save_creator(fakeid: str, creator: Dict) -> None:
    """
    保存公众号创作者信息

    Args:
        fakeid: 公众号 fakeid
        creator: 创作者信息字典
    """
    local_db_item = {
        "fakeid": fakeid,
        "nickname": creator.get("nickname", ""),
        "alias": creator.get("alias", ""),
        "round_head_img": creator.get("round_head_img", ""),
        "signature": creator.get("signature", ""),
        "service_type": creator.get("service_type", 0),
        "verify_status": creator.get("verify_status", 0),
        "identity_name": creator.get("identity_name", ""),
        "original_article_count": creator.get("original_article_count", 0),
        "intro": creator.get("intro", ""),
        "org": creator.get("org", ""),
        "account_type": creator.get("account_type", ""),
        "ip_location": creator.get("ip_location", ""),
        "last_modify_ts": utils.get_current_timestamp(),
    }
    utils.logger.info(f"[store.wechat.save_creator] creator: {local_db_item.get('nickname', fakeid)}")
    await WechatStoreFactory.create_store().store_creator(local_db_item)
