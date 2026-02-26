# -*- coding: utf-8 -*-
# @Desc : 微信公众号 API 客户端
#
# 通过 HTTP 调用 wechat-article-exporter 的公开 API 接口。
# 所有需要认证的接口通过 X-Auth-Key 请求头传递 auth-key。

import asyncio
from typing import Any, Dict, List, Optional

import httpx

import config
from tools import utils
from media_platform.wechat.exception import (
    ArticleFetchError,
    AuthKeyExpiredError,
    ServiceUnavailableError,
    WeChatApiError,
)
from media_platform.wechat.field import DownloadFormat

# Auth-Key 过期的特定错误码
_AUTH_KEY_EXPIRED_RET_CODES = {200003, 200004, -1}


class WeChatClient:
    """
    wechat-article-exporter 公开 API 客户端

    Usage:
        client = WeChatClient(base_url="http://localhost:3000", auth_key="your-key")
        is_valid = await client.validate_auth_key()
        accounts = await client.search_account(keyword="铁路12306")
        articles = await client.get_article_list(fakeid="MzA3NzAyMzMyMA==")
        content = await client.download_article(url="https://mp.weixin.qq.com/s/xxx", format="markdown")
    """

    def __init__(
        self,
        base_url: str,
        auth_key: str = "",
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.auth_key = auth_key
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """懒初始化 httpx 异步客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self._build_headers(),
            )
        return self._client

    def _build_headers(self) -> Dict[str, str]:
        """构建请求头"""
        headers = {
            "User-Agent": "MediaCrawler/1.0 (WeChat Module)",
        }
        if self.auth_key:
            headers["X-Auth-Key"] = self.auth_key
        return headers

    async def close(self) -> None:
        """关闭 HTTP 客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    # ======================== 基础请求方法 ========================

    async def _request_json(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        发送 GET 请求并解析 JSON 响应，支持自动重试

        Raises:
            ServiceUnavailableError: 服务不可达
            AuthKeyExpiredError: 认证失败
            WeChatApiError: API 返回错误
        """
        max_retries = getattr(config, 'WECHAT_MAX_RETRY_COUNT', 3)
        base_delay = getattr(config, 'WECHAT_RETRY_BASE_DELAY_SEC', 2.0)
        last_error: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            try:
                client = await self._get_client()
                resp = await client.get(path, params=params)
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
                last_error = ServiceUnavailableError(self.base_url)
                if attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))
                    utils.logger.warning(
                        f"[WeChatClient] 请求失败 ({attempt}/{max_retries}): {e}, {delay}s 后重试"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise last_error from e

            if resp.status_code != 200:
                last_error = WeChatApiError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                if resp.status_code >= 500 and attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))
                    utils.logger.warning(
                        f"[WeChatClient] 服务器错误 {resp.status_code} ({attempt}/{max_retries}), {delay}s 后重试"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise last_error

            data = resp.json()

            # 检查通用错误响应: { "base_resp": { "ret": -1, "err_msg": "..." } }
            base_resp = data.get("base_resp", {})
            ret_code = base_resp.get("ret", 0)
            if ret_code != 0:
                err_msg = base_resp.get("err_msg", "未知错误")
                # Auth-Key 过期精确检测
                if ret_code in _AUTH_KEY_EXPIRED_RET_CODES or "认证" in err_msg or "auth" in err_msg.lower():
                    raise AuthKeyExpiredError(f"Auth-Key 已过期 (ret={ret_code}): {err_msg}")
                raise WeChatApiError(err_msg, ret_code=ret_code)

            return data

        # 不应走到这里，但保安全
        raise last_error or WeChatApiError("请求失败：未知错误")

    async def _request_text(self, path: str, params: Optional[Dict] = None) -> str:
        """
        发送 GET 请求并返回文本响应（用于文章内容下载），支持自动重试
        """
        max_retries = getattr(config, 'WECHAT_MAX_RETRY_COUNT', 3)
        base_delay = getattr(config, 'WECHAT_RETRY_BASE_DELAY_SEC', 2.0)
        last_error: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            try:
                client = await self._get_client()
                resp = await client.get(path, params=params)
            except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as e:
                last_error = ServiceUnavailableError(self.base_url)
                if attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))
                    utils.logger.warning(
                        f"[WeChatClient] 文本请求失败 ({attempt}/{max_retries}): {e}, {delay}s 后重试"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise last_error from e

            if resp.status_code != 200:
                # download 接口可能返回 JSON 错误
                try:
                    data = resp.json()
                    err_msg = data.get("base_resp", {}).get("err_msg", resp.text[:200])
                    last_error = WeChatApiError(err_msg)
                except Exception:
                    last_error = WeChatApiError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                if resp.status_code >= 500 and attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))
                    utils.logger.warning(
                        f"[WeChatClient] 服务器错误 {resp.status_code} ({attempt}/{max_retries}), {delay}s 后重试"
                    )
                    await asyncio.sleep(delay)
                    continue
                raise last_error

            return resp.text

        raise last_error or WeChatApiError("请求失败：未知错误")

    # ======================== 公开 API ========================

    async def validate_auth_key(self) -> bool:
        """
        验证 auth-key 是否有效

        Returns:
            True 有效, False 无效
        """
        try:
            client = await self._get_client()
            resp = await client.get("/api/public/v1/authkey")
            data = resp.json()
            # authkey 接口返回格式: { "code": 0, "data": "key" } 或 { "code": -1, "msg": "..." }
            return data.get("code", -1) == 0
        except Exception as e:
            utils.logger.warning(f"[WeChatClient] Auth-Key 验证失败: {e}")
            return False

    async def search_account(
        self,
        keyword: str,
        begin: int = 0,
        size: int = 5,
    ) -> Dict[str, Any]:
        """
        根据关键字搜索公众号

        Args:
            keyword: 搜索关键词
            begin: 起始索引 (从 0 开始)
            size: 返回条数 (最大 20)

        Returns:
            {
                "base_resp": {"ret": 0, "err_msg": "ok"},
                "total": 2,
                "list": [{"fakeid": "...", "nickname": "...", ...}, ...]
            }
        """
        params = {"keyword": keyword, "begin": begin, "size": min(size, 20)}
        return await self._request_json("/api/public/v1/account", params=params)

    async def get_article_list(
        self,
        fakeid: str,
        begin: int = 0,
        size: int = 5,
        keyword: str = "",
    ) -> Dict[str, Any]:
        """
        获取公众号历史文章列表

        Args:
            fakeid: 公众号唯一标识
            begin: 起始索引
            size: 返回条数 (最大 20)
            keyword: 文章搜索关键词（可选）

        Returns:
            {
                "base_resp": {"ret": 0, "err_msg": "ok"},
                "articles": [{"aid": "...", "title": "...", "link": "...", ...}, ...]
            }
        """
        params: Dict[str, Any] = {"fakeid": fakeid, "begin": begin, "size": min(size, 20)}
        if keyword:
            params["keyword"] = keyword
        return await self._request_json("/api/public/v1/article", params=params)

    async def download_article(
        self,
        url: str,
        format: str = "html",
    ) -> str:
        """
        下载文章内容（此接口不需要 auth-key）

        Args:
            url: 文章链接
            format: 输出格式 (html/markdown/text/json)

        Returns:
            文章内容文本
        """
        params = {"url": url, "format": format}
        return await self._request_text("/api/public/v1/download", params=params)

    async def fetch_article_raw_html(self, article_url: str) -> str:
        """
        直接请求微信文章原始 HTML 页面（不经过 wechat-article-exporter 解析）

        用于降级提取 JS 动态渲染的内容（图片分享 / 文本分享等），
        原始 HTML 中包含 window.picture_page_info_list、__QMTPL_SSR_DATA__ 等变量。

        Args:
            article_url: 微信文章链接

        Returns:
            原始 HTML 文本（失败返回空字符串）
        """
        import httpx

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
            "Referer": "https://mp.weixin.qq.com/",
            "Origin": "https://mp.weixin.qq.com",
        }
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as http:
                resp = await http.get(article_url, headers=headers)
                resp.raise_for_status()
                return resp.text
        except Exception as e:
            from tools import utils
            utils.logger.warning(f"[WeChatClient] 获取原始 HTML 失败: {e}")
            return ""

    async def get_author_info(self, fakeid: str) -> Dict[str, Any]:
        """
        获取公众号主体信息（beta，不需要 auth-key）

        Args:
            fakeid: 公众号唯一标识

        Returns:
            {
                "base_resp": {"ret": 0},
                "identity_name": "xxx",
                "is_verify": 2,
                "original_article_count": 262
            }
        """
        return await self._request_json("/api/public/beta/authorinfo", params={"fakeid": fakeid})

    async def get_about_biz(self, fakeid: str, key: str = "") -> Dict[str, Any]:
        """
        获取公众号详细信息（beta，不需要 auth-key）

        Args:
            fakeid: 公众号唯一标识
            key: 可选的 x-wechat-key 参数

        Returns:
            {
                "base_resp": {"ret": 0},
                "data": {"intro": "...", "wechat": "...", "type": "...", "org": "..."}
            }
        """
        params: Dict[str, str] = {"fakeid": fakeid}
        if key:
            params["key"] = key
        return await self._request_json("/api/public/beta/aboutbiz", params=params)

    async def search_account_by_url(self, article_url: str) -> Dict[str, Any]:
        """
        根据文章链接反查公众号信息

        Args:
            article_url: 微信公众号文章链接

        Returns:
            同 search_account 的返回格式
        """
        return await self._request_json("/api/public/v1/accountbyurl", params={"url": article_url})

    # ======================== 图片下载 ========================

    async def download_image(self, image_url: str) -> Optional[bytes]:
        """
        下载单张图片（直接请求微信图床，不经过 wechat-article-exporter）
        支持失败自动重试

        Args:
            image_url: 微信图片 URL (mmbiz.qpic.cn)

        Returns:
            图片字节内容，失败返回 None
        """
        max_retries = getattr(config, 'WECHAT_MAX_RETRY_COUNT', 3)
        base_delay = getattr(config, 'WECHAT_RETRY_BASE_DELAY_SEC', 2.0)

        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=30.0,
                    headers={
                        "Referer": "https://mp.weixin.qq.com/",
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    },
                    follow_redirects=True,
                ) as img_client:
                    resp = await img_client.get(image_url)
                    if resp.status_code == 200:
                        return resp.content
                    else:
                        if attempt < max_retries:
                            delay = base_delay * (2 ** (attempt - 1))
                            utils.logger.warning(
                                f"[WeChatClient] 图片下载 HTTP {resp.status_code} ({attempt}/{max_retries}), {delay}s 后重试: {image_url[:60]}"
                            )
                            await asyncio.sleep(delay)
                            continue
                        utils.logger.warning(
                            f"[WeChatClient] 图片下载失败 HTTP {resp.status_code}: {image_url[:80]}"
                        )
                        return None
            except Exception as e:
                if attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))
                    utils.logger.warning(
                        f"[WeChatClient] 图片下载异常 ({attempt}/{max_retries}): {e}, {delay}s 后重试"
                    )
                    await asyncio.sleep(delay)
                    continue
                utils.logger.warning(f"[WeChatClient] 图片下载失败: {e}, URL: {image_url[:80]}")
                return None

        return None

    # ======================== 便捷聚合方法 ========================

    async def get_all_articles(
        self,
        fakeid: str,
        max_count: int = 0,
        interval_sec: float = 2.0,
        date_start_ts: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        获取公众号全部文章（自动翻页）

        Args:
            fakeid: 公众号唯一标识
            max_count: 最大文章数，0 表示不限制
            interval_sec: 请求间隔（秒）
            date_start_ts: 日期起始时间戳，文章早于此时间则终止翻页（利用倒序排列特性）

        Returns:
            文章信息列表
        """
        all_articles: List[Dict[str, Any]] = []
        begin = 0
        page_size = 20  # API 最大值

        while True:
            try:
                data = await self.get_article_list(fakeid=fakeid, begin=begin, size=page_size)
            except AuthKeyExpiredError:
                raise
            except WeChatApiError as e:
                utils.logger.error(f"[WeChatClient] 获取文章列表失败: {e}")
                break

            articles = data.get("articles", [])
            if not articles:
                utils.logger.info(f"[WeChatClient] fakeid={fakeid} 文章列表已到末尾, 共获取 {len(all_articles)} 篇")
                break

            # 过滤已删除文章
            valid_articles = [a for a in articles if not a.get("is_deleted", False)]

            # 日期早停：如果本页最旧的文章已早于 date_start_ts，只保留范围内的
            hit_date_boundary = False
            if date_start_ts > 0 and valid_articles:
                filtered_batch = []
                for a in valid_articles:
                    ct = a.get("create_time", 0)
                    if ct and ct < date_start_ts:
                        hit_date_boundary = True
                        continue
                    filtered_batch.append(a)
                valid_articles = filtered_batch

            all_articles.extend(valid_articles)

            utils.logger.info(
                f"[WeChatClient] fakeid={fakeid} 已获取 {len(all_articles)} 篇文章 (begin={begin})"
            )

            # 达到数量限制
            if max_count > 0 and len(all_articles) >= max_count:
                all_articles = all_articles[:max_count]
                break

            # 日期早停：已遇到早于起始日期的文章
            if hit_date_boundary:
                utils.logger.info(
                    f"[WeChatClient] fakeid={fakeid} 已到达日期起始边界, 停止翻页, 共获取 {len(all_articles)} 篇"
                )
                break

            # 本页不满表示已到末尾
            if len(articles) < page_size:
                break

            begin += page_size
            await asyncio.sleep(interval_sec)

        return all_articles

    async def ping(self) -> bool:
        """
        检测 wechat-article-exporter 服务是否可用
        """
        try:
            client = await self._get_client()
            resp = await client.get("/", follow_redirects=True)
            return resp.status_code == 200
        except Exception:
            return False
