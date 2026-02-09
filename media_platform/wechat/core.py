# -*- coding: utf-8 -*-
# @Desc : 微信公众号爬虫核心逻辑
#
# 实现 AbstractCrawler 接口，通过 WeChatClient 调用 wechat-article-exporter 公开 API
# 支持三种爬取模式：
#   - search:  按关键词搜索公众号，爬取搜索结果中公众号的文章
#   - detail:  爬取指定文章 URL 列表的内容
#   - creator: 爬取指定公众号 fakeid 列表的全部文章

import asyncio
import os
from typing import Dict, List, Optional

from playwright.async_api import BrowserContext, BrowserType, Playwright

import config
from base.base_crawler import AbstractCrawler
from media_platform.wechat.client import WeChatClient
from media_platform.wechat.exception import AuthKeyExpiredError, ServiceUnavailableError
from media_platform.wechat.field import DownloadFormat
from media_platform.wechat.help import (
    build_article_filename,
    build_image_filename,
    ensure_dir,
    extract_image_urls_from_html,
    format_timestamp,
    sanitize_filename,
)
from store.wechat import WechatStoreFactory, update_wechat_article, save_creator
from store.wechat.wechat_store_media import WechatMediaStore
from tools import utils
from var import crawler_type_var


class WeChatCrawler(AbstractCrawler):
    """
    微信公众号爬虫

    不需要浏览器，通过 HTTP 调用 wechat-article-exporter 的公开 API。
    使用前需要：
      1. 启动 wechat-article-exporter 服务
      2. 配置 WECHAT_API_BASE_URL 和 WECHAT_AUTH_KEY
    """

    def __init__(self) -> None:
        self.client: Optional[WeChatClient] = None
        self.media_store: Optional[WechatMediaStore] = None

    async def start(self) -> None:
        """爬虫入口"""
        # 初始化客户端
        self.client = WeChatClient(
            base_url=config.WECHAT_API_BASE_URL,
            auth_key=config.WECHAT_AUTH_KEY,
        )

        # 初始化图片存储管理器
        self.media_store = WechatMediaStore()

        try:
            # 检查服务可用性
            utils.logger.info(
                f"[WeChatCrawler] 正在连接 wechat-article-exporter: {config.WECHAT_API_BASE_URL}"
            )
            if not await self.client.ping():
                raise ServiceUnavailableError(config.WECHAT_API_BASE_URL)
            utils.logger.info("[WeChatCrawler] 服务连接成功")

            # 验证 auth-key（需要认证的模式）
            if config.CRAWLER_TYPE in ("search", "creator"):
                if not config.WECHAT_AUTH_KEY:
                    utils.logger.error(
                        "[WeChatCrawler] WECHAT_AUTH_KEY 未配置！请在 config/wechat_config.py 中设置。"
                        "\n获取方式：登录 wechat-article-exporter 后从浏览器 Cookie 获取 auth-key"
                    )
                    return

                is_valid = await self.client.validate_auth_key()
                if not is_valid:
                    utils.logger.error(
                        "[WeChatCrawler] Auth-Key 已过期或无效，请重新登录 wechat-article-exporter 获取新的 auth-key"
                    )
                    return
                utils.logger.info("[WeChatCrawler] Auth-Key 验证通过")

            # 设置爬取类型上下文
            crawler_type_var.set(config.CRAWLER_TYPE)

            # 根据模式分发
            if config.CRAWLER_TYPE == "search":
                await self.search()
            elif config.CRAWLER_TYPE == "detail":
                await self._get_specified_articles()
            elif config.CRAWLER_TYPE == "creator":
                await self._get_creators_and_articles()
            else:
                utils.logger.error(
                    f"[WeChatCrawler] 不支持的爬取类型: {config.CRAWLER_TYPE}"
                    "\n支持: search / detail / creator"
                )

        except ServiceUnavailableError as e:
            utils.logger.error(
                f"[WeChatCrawler] ❌ {e}"
                f"\n请确认 wechat-article-exporter 是否已启动: {config.WECHAT_API_BASE_URL}"
            )
        except AuthKeyExpiredError as e:
            utils.logger.error(f"[WeChatCrawler] ❌ {e}")
        except Exception as e:
            utils.logger.error(f"[WeChatCrawler] 爬取异常: {e}", exc_info=True)
        finally:
            if self.client:
                await self.client.close()
            utils.logger.info("[WeChatCrawler] 爬取结束")

    async def search(self) -> None:
        """
        search 模式：按关键词搜索公众号，然后爬取搜索到的公众号的文章
        """
        keywords = [kw.strip() for kw in config.KEYWORDS.split(",") if kw.strip()]
        if not keywords:
            utils.logger.warning("[WeChatCrawler] KEYWORDS 为空，无法执行搜索")
            return

        for keyword in keywords:
            utils.logger.info(f"[WeChatCrawler] 搜索公众号: {keyword}")
            try:
                result = await self.client.search_account(keyword=keyword, size=10)
            except Exception as e:
                utils.logger.error(f"[WeChatCrawler] 搜索失败: {e}")
                continue

            account_list = result.get("list", [])
            if not account_list:
                utils.logger.info(f"[WeChatCrawler] 未找到匹配的公众号: {keyword}")
                continue

            utils.logger.info(
                f"[WeChatCrawler] 找到 {len(account_list)} 个公众号，开始爬取文章"
            )

            for account in account_list:
                fakeid = account.get("fakeid", "")
                nickname = account.get("nickname", "")
                utils.logger.info(f"[WeChatCrawler] 爬取公众号: {nickname} (fakeid={fakeid})")

                await self._crawl_account_articles(fakeid, nickname)
                await asyncio.sleep(config.WECHAT_REQUEST_INTERVAL_SEC)

    async def _get_specified_articles(self) -> None:
        """
        detail 模式：爬取指定文章 URL 列表
        """
        article_urls = config.WECHAT_SPECIFIED_ARTICLE_URL_LIST
        if not article_urls:
            utils.logger.warning(
                "[WeChatCrawler] WECHAT_SPECIFIED_ARTICLE_URL_LIST 为空，无法执行"
            )
            return

        utils.logger.info(f"[WeChatCrawler] detail 模式，共 {len(article_urls)} 篇文章待处理")

        for i, url in enumerate(article_urls, 1):
            utils.logger.info(f"[WeChatCrawler] [{i}/{len(article_urls)}] 处理文章: {url[:80]}")
            try:
                await self._download_and_store_article(
                    article_info={"link": url, "title": "", "aid": f"detail_{i}"},
                    account_nickname="",
                )
            except Exception as e:
                utils.logger.error(f"[WeChatCrawler] 文章处理失败: {e}")
            await asyncio.sleep(config.WECHAT_REQUEST_INTERVAL_SEC)

    async def _get_creators_and_articles(self) -> None:
        """
        creator 模式：爬取指定公众号 fakeid 列表的全部文章
        """
        creator_ids = config.WECHAT_CREATOR_ID_LIST
        if not creator_ids:
            utils.logger.warning(
                "[WeChatCrawler] WECHAT_CREATOR_ID_LIST 为空，无法执行"
                "\n请在 config/wechat_config.py 中配置目标公众号 fakeid"
            )
            return

        utils.logger.info(
            f"[WeChatCrawler] creator 模式，共 {len(creator_ids)} 个公众号待处理"
        )

        for i, fakeid in enumerate(creator_ids, 1):
            utils.logger.info(f"[WeChatCrawler] [{i}/{len(creator_ids)}] 开始处理 fakeid={fakeid}")

            # 获取公众号基础信息
            nickname = await self._fetch_and_save_creator_info(fakeid)
            display_name = nickname or fakeid

            # 爬取文章
            await self._crawl_account_articles(fakeid, display_name)

            if i < len(creator_ids):
                utils.logger.info(f"[WeChatCrawler] 等待 {config.WECHAT_REQUEST_INTERVAL_SEC}s 后处理下一个公众号")
                await asyncio.sleep(config.WECHAT_REQUEST_INTERVAL_SEC)

    # ======================== 内部方法 ========================

    async def _fetch_and_save_creator_info(self, fakeid: str) -> str:
        """
        获取公众号信息并保存到 store，返回 nickname

        尝试聚合 authorinfo 和 aboutbiz 接口的数据
        """
        creator_data: Dict = {"fakeid": fakeid}
        nickname = ""

        # 1. 获取 authorinfo（不需要 auth-key）
        try:
            author_info = await self.client.get_author_info(fakeid)
            creator_data["identity_name"] = author_info.get("identity_name", "")
            creator_data["is_verify"] = author_info.get("is_verify", 0)
            creator_data["original_article_count"] = author_info.get("original_article_count", 0)
        except Exception as e:
            utils.logger.debug(f"[WeChatCrawler] 获取 authorinfo 失败: {e}")

        # 2. 获取 aboutbiz（不需要 auth-key）
        try:
            about_biz = await self.client.get_about_biz(fakeid)
            biz_data = about_biz.get("data", {})
            creator_data["intro"] = biz_data.get("intro", "")
            creator_data["wechat"] = biz_data.get("wechat", "")
            creator_data["account_type"] = biz_data.get("type", "")
            creator_data["org"] = biz_data.get("org", "")
            ip_wording = biz_data.get("ip_wording", {})
            if ip_wording:
                creator_data["ip_location"] = (
                    f"{ip_wording.get('countryName', '')}"
                    f"{ip_wording.get('provinceName', '')}"
                    f"{ip_wording.get('cityName', '')}"
                ).strip()
            # 如果 aboutbiz 没有 nickname，alias 可替代
            nickname = creator_data.get("wechat", "")
        except Exception as e:
            utils.logger.debug(f"[WeChatCrawler] 获取 aboutbiz 失败: {e}")

        # 3. 尝试通过 search_account 获取 nickname 和头像
        try:
            # 用 fakeid 搜索可能拿不到结果，但如果有 alias 可以用
            if creator_data.get("wechat"):
                search_result = await self.client.search_account(keyword=creator_data["wechat"], size=1)
                account_list = search_result.get("list", [])
                if account_list:
                    account = account_list[0]
                    nickname = account.get("nickname", nickname)
                    creator_data["nickname"] = nickname
                    creator_data["alias"] = account.get("alias", "")
                    creator_data["round_head_img"] = account.get("round_head_img", "")
                    creator_data["signature"] = account.get("signature", "")
                    creator_data["service_type"] = account.get("service_type", 0)
                    creator_data["verify_status"] = account.get("verify_status", 0)
        except Exception as e:
            utils.logger.debug(f"[WeChatCrawler] 搜索公众号补充信息失败: {e}")

        if not creator_data.get("nickname"):
            creator_data["nickname"] = nickname or fakeid

        # 保存创作者信息
        try:
            await save_creator(fakeid, creator_data)
        except Exception as e:
            utils.logger.warning(f"[WeChatCrawler] 保存创作者信息失败: {e}")

        return creator_data.get("nickname", fakeid)

    async def _crawl_account_articles(self, fakeid: str, nickname: str) -> None:
        """
        爬取指定公众号的文章列表，然后逐篇下载内容

        Args:
            fakeid: 公众号 fakeid
            nickname: 公众号昵称（用于日志和存储）
        """
        max_articles = config.WECHAT_MAX_ARTICLES_PER_CREATOR
        interval = config.WECHAT_REQUEST_INTERVAL_SEC

        utils.logger.info(
            f"[WeChatCrawler] 获取 [{nickname}] 的文章列表 (最多 {max_articles} 篇)"
        )

        try:
            articles = await self.client.get_all_articles(
                fakeid=fakeid,
                max_count=max_articles,
                interval_sec=interval,
            )
        except AuthKeyExpiredError:
            raise
        except Exception as e:
            utils.logger.error(f"[WeChatCrawler] 获取文章列表失败: {e}")
            return

        if not articles:
            utils.logger.info(f"[WeChatCrawler] [{nickname}] 没有找到文章")
            return

        utils.logger.info(
            f"[WeChatCrawler] [{nickname}] 共 {len(articles)} 篇文章，开始逐篇处理"
        )

        # 用信号量控制并发
        semaphore = asyncio.Semaphore(config.MAX_CONCURRENCY_NUM)
        skipped = 0

        async def _process_one(idx: int, article: Dict) -> None:
            nonlocal skipped
            async with semaphore:
                title = article.get("title", "无标题")
                aid = article.get("aid", "")

                # 增量爬取：检查文章内容文件是否已存在
                if self._article_file_exists(title, aid, nickname):
                    utils.logger.info(
                        f"[WeChatCrawler] [{nickname}] [{idx}/{len(articles)}] 跳过已存在: {title}"
                    )
                    skipped += 1
                    return

                utils.logger.info(
                    f"[WeChatCrawler] [{nickname}] [{idx}/{len(articles)}] {title}"
                )
                try:
                    await self._download_and_store_article(article, nickname)
                except Exception as e:
                    utils.logger.error(
                        f"[WeChatCrawler] 文章处理失败: {title}, 错误: {e}"
                    )
                await asyncio.sleep(interval)

        tasks = [_process_one(i, a) for i, a in enumerate(articles, 1)]
        await asyncio.gather(*tasks)
        if skipped > 0:
            utils.logger.info(
                f"[WeChatCrawler] [{nickname}] 完成，处理 {len(articles) - skipped} 篇，跳过 {skipped} 篇已存在文章"
            )

    def _article_file_exists(self, title: str, aid: str, nickname: str) -> bool:
        """检查文章内容文件是否已存在（用于增量爬取）"""
        download_format = config.WECHAT_DOWNLOAD_FORMAT
        ext_map = {"html": ".html", "markdown": ".md", "text": ".txt", "json": ".json"}
        ext = ext_map.get(download_format, ".txt")
        safe_nickname = sanitize_filename(nickname) if nickname else "unknown"
        save_dir = os.path.join("data", config.WECHAT_CONTENT_SAVE_DIR, safe_nickname)
        filename = build_article_filename(title or aid, aid, ext)
        filepath = os.path.join(save_dir, filename)
        return os.path.exists(filepath)

    async def _download_and_store_article(
        self,
        article_info: Dict,
        account_nickname: str,
    ) -> None:
        """
        下载单篇文章内容并保存

        Args:
            article_info: 文章元信息 (包含 link, title, aid 等)
            account_nickname: 公众号昵称
        """
        article_url = article_info.get("link", "")
        if not article_url:
            return

        title = article_info.get("title", "")
        aid = article_info.get("aid", "")
        download_format = config.WECHAT_DOWNLOAD_FORMAT

        # 1. 下载文章内容
        content = ""
        try:
            content = await self.client.download_article(
                url=article_url,
                format=download_format,
            )
        except Exception as e:
            utils.logger.error(f"[WeChatCrawler] 文章内容下载失败: {e}")

        # 2. 提取数据并存储
        local_db_item = {
            "article_id": aid,
            "title": title or "无标题",
            "link": article_url,
            "digest": article_info.get("digest", ""),
            "cover": article_info.get("cover", ""),
            "author_name": article_info.get("author_name", ""),
            "account_nickname": account_nickname,
            "create_time": article_info.get("create_time", 0),
            "update_time": article_info.get("update_time", 0),
            "create_time_str": format_timestamp(article_info.get("create_time", 0)),
            "update_time_str": format_timestamp(article_info.get("update_time", 0)),
            "content_format": download_format,
            "content_length": len(content),
            "copyright_type": article_info.get("copyright_type", 0),
            "last_modify_ts": utils.get_current_timestamp(),
        }

        await update_wechat_article(local_db_item)

        # 3. 保存文章内容到文件
        if content:
            await self._save_article_content(
                content=content,
                title=title or aid,
                aid=aid,
                nickname=account_nickname,
                format=download_format,
            )

        # 4. 下载文章中的图片（仅 HTML 格式时提取）
        if config.WECHAT_DOWNLOAD_IMAGES and content:
            # 对于非 html 格式，需要单独请求 html 来提取图片
            html_content = content
            if download_format != "html":
                try:
                    html_content = await self.client.download_article(
                        url=article_url, format="html"
                    )
                except Exception:
                    html_content = ""

            if html_content:
                await self._download_article_images(
                    html_content=html_content,
                    aid=aid,
                    nickname=account_nickname,
                )

    async def _save_article_content(
        self,
        content: str,
        title: str,
        aid: str,
        nickname: str,
        format: str,
    ) -> None:
        """保存文章内容到本地文件（已存在则跳过）"""
        ext_map = {"html": ".html", "markdown": ".md", "text": ".txt", "json": ".json"}
        ext = ext_map.get(format, ".txt")

        # 按公众号名称分目录
        safe_nickname = sanitize_filename(nickname) if nickname else "unknown"
        save_dir = ensure_dir(
            os.path.join("data", config.WECHAT_CONTENT_SAVE_DIR, safe_nickname)
        )
        filename = build_article_filename(title, aid, ext)
        filepath = os.path.join(save_dir, filename)

        # 文件去重：已存在则跳过
        if os.path.exists(filepath):
            utils.logger.debug(f"[WeChatCrawler] 文章文件已存在，跳过: {filepath}")
            return

        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            utils.logger.info(f"[WeChatCrawler] 文章内容已保存: {filepath}")
        except Exception as e:
            utils.logger.error(f"[WeChatCrawler] 保存文章失败: {e}")

    async def _download_article_images(
        self,
        html_content: str,
        aid: str,
        nickname: str,
    ) -> None:
        """从文章 HTML 中提取并下载所有图片"""
        image_urls = extract_image_urls_from_html(html_content)
        if not image_urls:
            return

        utils.logger.info(f"[WeChatCrawler] 发现 {len(image_urls)} 张图片，开始下载")

        semaphore = asyncio.Semaphore(config.WECHAT_IMAGE_DOWNLOAD_CONCURRENCY)
        saved_count = 0

        async def _download_one(idx: int, url: str) -> bool:
            async with semaphore:
                img_data = await self.client.download_image(url)
                if img_data and self.media_store:
                    path = self.media_store.save_image(
                        data=img_data,
                        url=url,
                        article_id=aid,
                        index=idx,
                        nickname=nickname,
                    )
                    return path is not None
                return False

        tasks = [_download_one(i, url) for i, url in enumerate(image_urls, 1)]
        results = await asyncio.gather(*tasks)
        saved_count = sum(1 for r in results if r)
        utils.logger.info(f"[WeChatCrawler] 图片下载完成: {saved_count}/{len(tasks)} 张（去重后）")

    # ======================== AbstractCrawler 抽象方法实现 ========================

    async def launch_browser(
        self,
        chromium: BrowserType,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        """
        微信模块不需要浏览器，此方法为空实现（满足 AbstractCrawler 接口要求）
        """
        pass  # type: ignore

    async def launch_browser_with_cdp(
        self,
        playwright: Playwright,
        playwright_proxy: Optional[Dict],
        user_agent: Optional[str],
        headless: bool = True,
    ) -> BrowserContext:
        """
        微信模块不需要 CDP 浏览器，此方法为空实现
        """
        pass  # type: ignore
