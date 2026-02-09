# 微信爬虫模块集成到 MediaCrawler 的方案思考

## 一、两个项目的架构差异

| 维度 | wechat_crawler (wechat-article-exporter) | MediaCrawler |
|------|----------------------------------------|--------------|
| 语言 | TypeScript (Nuxt 3 + Nitro) | Python (asyncio) |
| 运行模式 | Web 服务 (浏览器端 + 服务端) | CLI 脚本 / API 服务 |
| 登录方式 | 微信公众平台扫码登录 (Cookie 代理) | Playwright 浏览器自动化 |
| 数据存储 | IndexedDB (前端) + KV (Nitro) | MySQL/CSV/JSON + Redis 缓存 |
| 代理架构 | 前端代理池 (`utils/pool.ts`) | 服务端代理池 (`proxy/proxy_ip_pool.py`) |

重点：wechat_crawler 的核心逻辑是 TypeScript 写的，不能直接 import，需要**用 Python 重写核心请求逻辑**。

## 二、集成方案设计

### 2.1 整体架构

按照 MediaCrawler 的平台模块模式（参考 `media_platform/` 下的 `xhs/`、`douyin/` 等），新增一个 `media_platform/wechat/` 模块：

```
media_platform/wechat/
├── __init__.py
├── core.py              # 主爬虫类 WeChatCrawler(AbstractCrawler)
├── client.py            # 微信 MP API 客户端（Python 重写 proxyMpRequest 逻辑）
├── login.py             # 登录处理（两种模式）
├── field.py             # 搜索/帖子排序等枚举
├── help.py              # 辅助函数
├── exception.py         # 自定义异常
└── credential.py        # mitmproxy 凭证管理（从 wechat_crawler 迁移）
```

同时新增：
- `model/m_wechat.py` — 数据模型
- `config/wechat_config.py` — 微信平台配置
- `store/wechat/` — 存储适配

### 2.2 核心模块映射

#### ① 登录与认证

wechat_crawler 提供两种认证路径，需要都支持：

**路径 A：公众平台登录（对应内部 API）**

参考 `server/api/web/login/bizlogin.post.ts` 的 `proxyMpRequest` 登录流程，用 Python `httpx`/`aiohttp` 重写：

```python
# filepath: media_platform/wechat/client.py
import httpx
from typing import Optional, Dict, Any

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36 WAE/1.0"
)

class WeChatMpClient:
    """微信公众平台 API 客户端，对应 wechat_crawler 的 proxyMpRequest"""
    
    BASE_URL = "https://mp.weixin.qq.com"
    
    def __init__(self):
        self.cookies: Dict[str, str] = {}
        self.token: Optional[str] = None
        self._client = httpx.AsyncClient(
            headers={
                "Referer": "https://mp.weixin.qq.com/",
                "Origin": "https://mp.weixin.qq.com",
                "User-Agent": USER_AGENT,
            },
            follow_redirects=True,
            timeout=30.0,
        )
    
    async def proxy_mp_request(
        self,
        method: str,
        endpoint: str,
        query: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        cookie: Optional[str] = None,
    ) -> httpx.Response:
        """
        核心代理请求方法
        对应 wechat_crawler server/utils/proxy-request.ts 的 proxyMpRequest
        """
        headers = dict(self._client.headers)
        if cookie:
            headers["Cookie"] = cookie
        elif self.cookies:
            headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in self.cookies.items())
        
        if method.upper() == "GET":
            response = await self._client.get(endpoint, params=query, headers=headers)
        else:
            response = await self._client.post(
                endpoint, params=query, data=body, headers=headers
            )
        
        # 提取并保存 set-cookie
        for cookie_header in response.headers.get_list("set-cookie"):
            self._parse_and_store_cookie(cookie_header)
        
        return response

    async def login(self, username: str, password: str) -> bool:
        """
        公众平台登录流程
        对应 wechat_crawler server/api/web/login/bizlogin.post.ts
        """
        # Step 1: 启动登录，获取二维码
        resp = await self.proxy_mp_request(
            method="GET",
            endpoint=f"{self.BASE_URL}/cgi-bin/bizlogin",
            query={"action": "startlogin"},
        )
        # Step 2: 轮询扫码状态 ...
        # Step 3: 提交登录，获取 token
        # ...
        return True
    
    async def get_article_list(
        self, fakeid: str, begin: int = 0, size: int = 5
    ) -> Dict[str, Any]:
        """
        获取公众号文章列表
        对应 wechat_crawler apis/index.ts 的 getArticleList
        """
        resp = await self.proxy_mp_request(
            method="GET",
            endpoint=f"{self.BASE_URL}/cgi-bin/appmsgpublish",
            query={
                "sub": "list",
                "search_field": None,
                "begin": str(begin),
                "count": str(size),
                "query": "",
                "fakeid": fakeid,
                "type": "101_1",
                "free_publish_type": "1",
                "sub_action": "list_ex",
                "token": self.token,
                "lang": "zh_CN",
                "f": "json",
                "ajax": "1",
            },
        )
        return resp.json()
    
    async def download_article(self, url: str, fmt: str = "html") -> str:
        """
        下载文章内容
        对应 wechat_crawler server/api/public/v1/download.get.ts
        """
        resp = await self._client.get(
            url,
            headers={
                "Referer": "https://mp.weixin.qq.com/",
                "Origin": "https://mp.weixin.qq.com",
                "User-Agent": USER_AGENT,
            },
        )
        raw_html = resp.text
        # TODO: HTML 解析/归一化，对应 shared/utils/html.ts 的 normalizeHtml
        if fmt == "html":
            return self._normalize_html(raw_html)
        elif fmt == "text":
            return self._extract_text(raw_html)
        elif fmt == "markdown":
            return self._to_markdown(raw_html)
        return raw_html
    
    async def get_comment(
        self, biz: str, comment_id: str, uin: str, key: str, pass_ticket: str
    ) -> Dict[str, Any]:
        """
        获取文章评论
        对应 wechat_crawler apis/index.ts 的 getComment
        """
        resp = await self._client.get(
            f"{self.BASE_URL}/mp/appmsg_comment",
            params={
                "action": "getcomment",
                "__biz": biz,
                "comment_id": comment_id,
                "uin": uin,
                "key": key,
                "pass_ticket": pass_ticket,
                "offset": "1",
                "limit": "100",
                "f": "json",
            },
        )
        return resp.json()
    
    def _parse_and_store_cookie(self, set_cookie: str) -> None:
        parts = set_cookie.split(";")[0].strip()
        if "=" in parts:
            name, value = parts.split("=", 1)
            self.cookies[name.strip()] = value.strip()
    
    def _normalize_html(self, html: str) -> str:
        """对应 shared/utils/html.ts 的 normalizeHtml"""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find(id="js_content")
        return str(content) if content else html
    
    def _extract_text(self, html: str) -> str:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, "html.parser")
        content = soup.find(id="js_content")
        return content.get_text(strip=True) if content else ""
    
    def _to_markdown(self, html: str) -> str:
        import markdownify
        normalized = self._normalize_html(html)
        return markdownify.markdownify(normalized)

    async def close(self) -> None:
        await self._client.aclose()
```

**路径 B：mitmproxy 凭证模式（对应 credential 模式）**

直接迁移 `public/plugins/credential.py`，稍作改造，使其凭证能注入到 `WeChatMpClient`：

```python
# filepath: media_platform/wechat/credential.py
import json
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from pathlib import Path

# 凭证有效期 25 分钟，对应 wechat_crawler config/index.ts CREDENTIAL_LIVE_MINUTES
CREDENTIAL_LIVE_MINUTES = 25


@dataclass
class WeChatCredential:
    """微信凭证，对应 wechat_crawler 中 credentials 格式"""
    biz: str  # __biz
    uin: str
    key: str
    pass_ticket: str
    wap_sid2: str = ""
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    
    @property
    def valid(self) -> bool:
        elapsed_minutes = (time.time() * 1000 - self.timestamp) / 1000 / 60
        return elapsed_minutes < CREDENTIAL_LIVE_MINUTES


class CredentialManager:
    """凭证管理器，对应 wechat_crawler 的 CookieStore + credential.py"""
    
    def __init__(self, credential_file: str = "credentials.json"):
        self.credential_file = Path(credential_file)
        self._credentials: Dict[str, WeChatCredential] = {}
    
    def load_from_file(self) -> None:
        """从 mitmproxy 插件生成的 credentials.json 加载"""
        if not self.credential_file.exists():
            return
        with open(self.credential_file, "r") as f:
            data = json.load(f)
        for item in data:
            # 解析 mitmproxy 捕获的数据
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(item.get("url", ""))
            params = parse_qs(parsed.query)
            biz = params.get("__biz", [None])[0]
            if biz:
                # 从 set_cookie 中提取凭证字段
                cred = self._parse_credential(biz, item)
                if cred:
                    self._credentials[biz] = cred
    
    def get_credential(self, biz: str) -> Optional[WeChatCredential]:
        cred = self._credentials.get(biz)
        if cred and cred.valid:
            return cred
        return None
    
    def set_credential(self, credential: WeChatCredential) -> None:
        self._credentials[credential.biz] = credential
    
    def _parse_credential(self, biz: str, raw: dict) -> Optional[WeChatCredential]:
        """解析 mitmproxy 抓取的 cookie 数据"""
        set_cookie = raw.get("set_cookie", "")
        # 从 Set-Cookie 中提取 uin, key, pass_ticket 等
        cookie_dict = {}
        for part in set_cookie.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                cookie_dict[k.strip()] = v.strip()
        
        return WeChatCredential(
            biz=biz,
            uin=cookie_dict.get("wxuin", ""),
            key=cookie_dict.get("wap_sid2", ""),
            pass_ticket=cookie_dict.get("pass_ticket", ""),
            wap_sid2=cookie_dict.get("wap_sid2", ""),
            timestamp=raw.get("timestamp", int(time.time() * 1000)),
        )
```

#### ② 主爬虫类

遵循 MediaCrawler 的 `base/base_crawler.py` 接口模式：

```python
# filepath: media_platform/wechat/core.py
import asyncio
from typing import Optional, List, Dict, Any

from base.base_crawler import AbstractCrawler
from model.m_wechat import WeChatArticle, WeChatAccount
from media_platform.wechat.client import WeChatMpClient
from media_platform.wechat.credential import CredentialManager
from proxy.proxy_ip_pool import IpInfoModel, create_ip_pool
from store.wechat import wechat_store
from tools import utils
from var import crawler_type_var, source_keyword_var

from config.wechat_config import (
    WECHAT_LOGIN_TYPE,
    WECHAT_SPECIFIED_ACCOUNTS,
    WECHAT_ARTICLE_DETAIL_ENABLED,
    WECHAT_COMMENT_ENABLED,
    WECHAT_CREDENTIAL_FILE,
)


class WeChatCrawler(AbstractCrawler):
    platform: str = "wechat"
    
    def __init__(self) -> None:
        self.client: Optional[WeChatMpClient] = None
        self.credential_manager = CredentialManager(WECHAT_CREDENTIAL_FILE)
    
    async def start(self) -> None:
        """启动爬虫"""
        # 初始化代理池（复用 MediaCrawler 现有代理体系）
        ip_proxy_pool, ip_proxy_info = await self._setup_proxy()
        
        # 初始化客户端
        self.client = WeChatMpClient()
        if ip_proxy_info:
            # 设置代理
            pass
        
        # 登录
        await self._login()
        
        # 根据爬虫类型执行
        crawler_type = crawler_type_var.get()
        if crawler_type == "search":
            await self.search()
        elif crawler_type == "detail":
            await self.get_specified_articles()
        elif crawler_type == "creator":
            await self.get_creators_and_bindaccounts()
        
        # 清理
        await self.client.close()
    
    async def _login(self) -> None:
        """登录处理"""
        if WECHAT_LOGIN_TYPE == "credential":
            # 凭证模式：从 mitmproxy 生成的文件加载
            self.credential_manager.load_from_file()
        elif WECHAT_LOGIN_TYPE == "platform":
            # 公众平台登录模式
            await self.client.login("", "")
    
    async def search(self) -> None:
        """搜索公众号并爬取文章"""
        keywords = source_keyword_var.get()
        for keyword in keywords:
            accounts = await self._search_accounts(keyword)
            for account in accounts:
                await self._crawl_account_articles(account)
    
    async def get_specified_articles(self) -> None:
        """爬取指定公众号的文章"""
        for account_id in WECHAT_SPECIFIED_ACCOUNTS:
            articles = await self._fetch_all_articles(account_id)
            for article in articles:
                if WECHAT_ARTICLE_DETAIL_ENABLED:
                    content = await self.client.download_article(article["link"])
                    article["content"] = content
                
                if WECHAT_COMMENT_ENABLED:
                    cred = self.credential_manager.get_credential(account_id)
                    if cred:
                        comments = await self.client.get_comment(
                            biz=cred.biz,
                            comment_id=article.get("comment_id", ""),
                            uin=cred.uin,
                            key=cred.key,
                            pass_ticket=cred.pass_ticket,
                        )
                        article["comments"] = comments
                
                await wechat_store.update_wechat_article(article)
    
    async def get_creators_and_bindaccounts(self) -> None:
        """获取公众号主体信息"""
        for account_id in WECHAT_SPECIFIED_ACCOUNTS:
            info = await self._get_author_info(account_id)
            await wechat_store.update_wechat_account(info)
    
    async def _search_accounts(self, keyword: str) -> List[Dict[str, Any]]:
        """搜索公众号，对应 /api/public/v1/account"""
        resp = await self.client.proxy_mp_request(
            method="GET",
            endpoint=f"{WeChatMpClient.BASE_URL}/cgi-bin/searchbiz",
            query={
                "action": "search_biz",
                "begin": "0",
                "count": "5",
                "query": keyword,
                "token": self.client.token,
                "lang": "zh_CN",
                "f": "json",
                "ajax": "1",
            },
        )
        data = resp.json()
        return data.get("list", [])
    
    async def _fetch_all_articles(
        self, fakeid: str, max_count: int = 100
    ) -> List[Dict[str, Any]]:
        """
        分页获取全部文章
        对应 wechat_crawler apis/index.ts 的 getArticleList
        """
        all_articles = []
        begin = 0
        while len(all_articles) < max_count:
            data = await self.client.get_article_list(fakeid, begin=begin)
            
            if data.get("base_resp", {}).get("ret") == 200003:
                raise Exception("session expired")
            
            publish_page = data.get("publish_page", {})
            if isinstance(publish_page, str):
                import json
                publish_page = json.loads(publish_page)
            
            publish_list = publish_page.get("publish_list", [])
            if not publish_list:
                break
            
            for item in publish_list:
                publish_info = item.get("publish_info", "")
                if isinstance(publish_info, str):
                    import json
                    publish_info = json.loads(publish_info)
                all_articles.extend(publish_info.get("appmsgex", []))
            
            begin += len(publish_list)
            # 反爬：请求间隔
            await asyncio.sleep(3)
        
        return all_articles
    
    async def _get_author_info(self, fakeid: str) -> Dict[str, Any]:
        """
        获取公众号主体信息
        对应 wechat_crawler server/api/public/beta/authorinfo.get.ts
        """
        resp = await self.client.proxy_mp_request(
            method="GET",
            endpoint=f"{WeChatMpClient.BASE_URL}/mp/authorinfo",
            query={
                "wxtoken": "777",
                "biz": fakeid,
                "__biz": fakeid,
                "x5": "0",
                "f": "json",
            },
        )
        return resp.json()
    
    async def _setup_proxy(self):
        """复用 MediaCrawler 的代理池"""
        from config.base_config import ENABLE_IP_PROXY
        if ENABLE_IP_PROXY:
            return await create_ip_pool(
                ip_pool_count=5, enable_validate_ip=True
            )
        return None, None
```

#### ③ 配置文件

```python
# filepath: config/wechat_config.py
"""微信公众号爬虫配置"""

# 登录方式: "credential" (mitmproxy 凭证) 或 "platform" (公众平台登录)
WECHAT_LOGIN_TYPE = "credential"

# mitmproxy 凭证文件路径
WECHAT_CREDENTIAL_FILE = "credentials.json"

# 指定要爬取的公众号 fakeid 列表
WECHAT_SPECIFIED_ACCOUNTS: list[str] = [
    # "MzA3NzAyMzMyMA==",  # 示例 fakeid
]

# 是否下载文章正文内容
WECHAT_ARTICLE_DETAIL_ENABLED = True

# 是否抓取评论（需要有效的 credential）
WECHAT_COMMENT_ENABLED = False

# 文章列表每页大小（对应 wechat_crawler 的 ARTICLE_LIST_PAGE_SIZE）
WECHAT_ARTICLE_PAGE_SIZE = 5

# 请求间隔（秒），防止触发反爬
WECHAT_REQUEST_INTERVAL = 3
```

#### ④ 数据模型

```python
# filepath: model/m_wechat.py
"""微信公众号数据模型"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class WeChatAccount:
    """公众号信息"""
    fakeid: str = ""
    nickname: str = ""
    alias: str = ""
    round_head_img: str = ""
    service_type: int = 0
    signature: str = ""
    verify_status: int = 0
    identity_name: str = ""
    original_article_count: int = 0


@dataclass
class WeChatArticle:
    """公众号文章"""
    aid: str = ""
    title: str = ""
    cover: str = ""
    link: str = ""
    digest: str = ""
    update_time: int = 0
    create_time: int = 0
    author_name: str = ""
    fakeid: str = ""
    content: str = ""  # 文章正文 HTML
    content_text: str = ""  # 纯文本
    is_deleted: bool = False


@dataclass
class WeChatComment:
    """文章评论"""
    content_id: str = ""
    nick_name: str = ""
    logo_url: str = ""
    content: str = ""
    create_time: int = 0
    like_num: int = 0
    reply_list: List[dict] = field(default_factory=list)
```

#### ⑤ 存储适配

```python
# filepath: store/wechat/__init__.py
"""微信公众号数据存储"""


async def update_wechat_article(article: dict) -> None:
    """存储文章数据，适配 MediaCrawler 的多存储后端"""
    from store import wechat as wechat_store_module
    from config.base_config import SAVE_DATA_OPTION
    
    if SAVE_DATA_OPTION == "db":
        from store.wechat.wechat_store_db import update_article_to_db
        await update_article_to_db(article)
    elif SAVE_DATA_OPTION == "csv":
        from store.wechat.wechat_store_csv import update_article_to_csv
        await update_article_to_csv(article)
    else:
        from store.wechat.wechat_store_json import update_article_to_json
        await update_article_to_json(article)


async def update_wechat_account(account: dict) -> None:
    """存储公众号信息"""
    pass  # 类似实现
```

#### ⑥ 注册入口

在 `main.py` 中注册微信平台：

```python
# filepath: main.py
# ...existing code...
from media_platform.wechat.core import WeChatCrawler

# ...existing code...
# 在平台映射中添加
platform_crawlers = {
    # ...existing code...
    "wechat": WeChatCrawler,
}
# ...existing code...
```

## 三、模块对应关系总结

| wechat_crawler 源文件 | 迁移后 MediaCrawler 位置 | 说明 |
|---|---|---|
| `server/utils/proxy-request.ts` | `media_platform/wechat/client.py` → `proxy_mp_request()` | 核心代理请求，Python 重写 |
| `apis/index.ts` → `getArticleList` | `client.py` → `get_article_list()` | 文章列表获取 |
| `apis/index.ts` → `getComment` | `client.py` → `get_comment()` | 评论获取 |
| `apis/index.ts` → `getArticleListWithCredential` | `client.py` → 带凭证的请求模式 | 凭证模式获取 |
| `server/api/public/v1/download.get.ts` | `client.py` → `download_article()` | 文章下载 |
| `server/api/public/beta/authorinfo.get.ts` | `core.py` → `_get_author_info()` | 公众号信息 |
| `public/plugins/credential.py` | `credential.py` | mitmproxy 插件直接复用 |
| `config/index.ts` | `config/wechat_config.py` | 配置项 |
| `utils/download/Downloader.ts` | `core.py` 中的下载逻辑 | 简化为直接下载 |
| `utils/pool.ts` | 复用 `proxy/proxy_ip_pool.py` | 代理池直接复用 MediaCrawler 已有的 |
| KV 存储 (Nitro) | 复用 `cache/` | 缓存层复用 Redis/本地缓存 |

## 四、关键注意事项

1. **凭证有效期**：wechat_crawler 中凭证只有 **25 分钟**有效期（见 `config/index.ts` 的 `CREDENTIAL_LIVE_MINUTES`），需要在 `CredentialManager` 中做过期检测和自动刷新提示。

2. **反爬策略**：微信有严格的风控，需要：
   - 请求间隔不低于 3 秒
   - 复用 MediaCrawler 的代理池（`proxy/proxy_ip_pool.py`）轮换 IP
   - 参考 `Downloader.ts` 中对 `Exception`（风控）状态的处理

3. **HTML 解析**：wechat_crawler 使用 cheerio（JS），迁移后用 `BeautifulSoup` 替代。核心解析逻辑在 `shared/utils/html.ts` 中的 `normalizeHtml`。

4. **两种登录模式并存**：
   - `credential` 模式更轻量，适合有手机的场景（通过 mitmproxy 抓包）
   - `platform` 模式需要扫码登录公众平台后台，功能更完整（可搜索公众号）

5. **增量依赖**：需在 `requirements.txt` 中添加：
   - `markdownify`（HTML 转 Markdown）
   - `mitmproxy`（可选，仅凭证模式需要）
