# 微信公众号爬虫集成规划（基于 wechat_crawler API）

> **核心思路转变**：wechat_crawler 已经解决了微信公众平台的登录认证、Cookie 管理、请求代理等所有复杂问题，并对外暴露了标准化的 HTTP API。  
> 因此我们**不再需要**用 Python 重写 `proxyMpRequest`、`CookieStore`、登录流程等模块，只需作为 API 消费者，用 httpx 调用 wechat_crawler 的公开接口即可。

---

## 一、可用的 wechat_crawler API 端点

### 需要 Auth Key 的端点（核心业务 API）

| 端点 | 方法 | 参数 | 说明 |
|------|------|------|------|
| `/api/public/v1/account` | GET | `keyword`(必填), `begin`, `size` | 按关键字搜索公众号，返回 `{list[{fakeid, nickname, alias, signature, ...}], total}` |
| `/api/public/v1/accountbyurl` | GET | `url`(必填) | 通过文章链接反查公众号信息 |
| `/api/public/v1/article` | GET | `fakeid`(必填), `begin`, `size`, `keyword` | 获取公众号历史文章列表，返回 `{articles[{aid, title, cover, link, author_name, create_time, ...}]}` |
| `/api/public/v1/authkey` | GET | 无 | 验证当前 auth-key 是否有效 |

### 无需 Auth Key 的端点

| 端点 | 方法 | 参数 | 说明 |
|------|------|------|------|
| `/api/public/v1/download` | GET | `url`(必填,需URL编码), `format`(html/markdown/text/json) | 下载文章内容，支持四种格式输出 |
| `/api/public/beta/authorinfo` | GET | `fakeid`(必填) | 查询公众号主体信息（认证主体、原创文章数等） |
| `/api/public/beta/aboutbiz` | GET | `fakeid`(必填), `key`(可选) | 查询公众号详细信息（简介、微信号、IP属地、授权第三方等） |

### Auth Key 传输方式

二选一：
- 自定义请求头：`X-Auth-Key: <your-key>`
- Cookie：`auth-key=<your-key>`

### 关键响应格式

**文章列表** (`/api/public/v1/article`) 单条文章字段：
```json
{
  "aid": "2247503214_1",
  "title": "文章标题",
  "cover": "https://mmbiz.qpic.cn/...",
  "link": "https://mp.weixin.qq.com/s/xxx",
  "digest": "摘要",
  "author_name": "作者名",
  "create_time": 1753666493,
  "update_time": 1753666492,
  "is_deleted": false,
  "copyright_type": 1,
  "album_id": "3457885223537541125"
}
```

**文章下载** (`/api/public/v1/download`) 按 format 参数返回：
- `html` → 归一化后的 HTML（已处理懒加载图片、移除脚本等）
- `text` → 纯文本
- `markdown` → Markdown 格式
- `json` → 页面内嵌的 CGI 结构化数据

---

## 二、工作量重新评估

对比原方案，以下模块**可完全跳过**：

| 原方案模块 | 状态 | 原因 |
|-----------|------|------|
| ② WeChatMpClient 核心请求层 | ~~跳过~~ | wechat_crawler API 已封装 |
| ③ 凭证管理 (credential.py) | ~~跳过~~ | auth-key 机制替代 |
| ④ 公众平台登录流程 | ~~跳过~~ | 在 wechat_crawler 端完成 |
| ⑥ HTML 解析与归一化 | ~~跳过~~ | `/download?format=...` 已处理 |

**实际需要开发的模块**：

| 模块 | 工作量 | 说明 |
|------|--------|------|
| A. `WeChatClient` API 客户端 | **小** | 纯 httpx 调用 wechat_crawler API，无签名/Cookie 逻辑 |
| B. `WeChatCrawler` 主爬虫类 | **中** | 实现 `start()` / `search()` / creator 模式 |
| C. 配置文件 | **小** | `wechat_config.py` |
| D. 数据模型 | **小** | `model/m_wechat.py` |
| E. 存储层 | **中** | `store/wechat/`，对齐多后端（CSV/JSON/DB/Excel） |
| F. 图片下载 | **中** | 从 HTML 提取图片 URL 并下载到本地 |
| G. 注册集成 | **小** | `main.py` + `config/__init__.py` |

**修订后总工作量：约 10-12 个文件，1500-2500 行 Python 代码，预计 5-8 小时。**

---

## 三、目标文件结构

```
media_platform/wechat/
├── __init__.py              # 导出 WeChatCrawler
├── core.py                  # 主爬虫类 WeChatCrawler(AbstractCrawler)
├── client.py                # wechat_crawler API 客户端（httpx 封装）
├── field.py                 # 枚举常量（下载格式、排序等）
├── help.py                  # 辅助函数（URL 校验、图片提取等）
└── exception.py             # 自定义异常

config/
└── wechat_config.py         # 微信平台配置

model/
└── m_wechat.py              # 数据模型（Pydantic）

store/wechat/
├── __init__.py              # WechatStoreFactory + update_wechat_article 等
├── _store_impl.py           # CSV/JSON/DB/Excel 存储实现
└── wechat_store_media.py    # 图片/资源文件下载存储

database/models.py           # 新增 WechatArticle, WechatArticleComment, WechatCreator 表
```

---

## 四、详细设计

### 4.1 `client.py` — API 客户端

与其他平台的 `client.py` 不同，微信模块**不需要浏览器**，不继承 `AbstractApiClient`，而是一个纯 HTTP 客户端：

```python
class WeChatClient:
    """wechat_crawler 公开 API 客户端"""

    def __init__(self, base_url: str, auth_key: str, proxy: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.auth_key = auth_key
        self._client = httpx.AsyncClient(
            headers={"X-Auth-Key": auth_key},
            timeout=30.0,
            proxies=proxy,
        )

    # --- 需要 auth-key 的接口 ---

    async def search_accounts(self, keyword: str, begin: int = 0, size: int = 5) -> dict:
        """搜索公众号 → /api/public/v1/account"""

    async def get_article_list(self, fakeid: str, begin: int = 0, size: int = 5) -> dict:
        """获取文章列表 → /api/public/v1/article"""

    async def check_auth_key(self) -> bool:
        """验证 auth-key 有效性 → /api/public/v1/authkey"""

    # --- 无需 auth-key 的接口 ---

    async def download_article(self, url: str, format: str = "html") -> str:
        """下载文章内容 → /api/public/v1/download"""

    async def download_article_json(self, url: str) -> dict:
        """下载文章结构化数据 → /api/public/v1/download?format=json"""

    async def get_author_info(self, fakeid: str) -> dict:
        """获取公众号主体信息 → /api/public/beta/authorinfo"""

    async def get_about_biz(self, fakeid: str) -> dict:
        """获取公众号详细信息 → /api/public/beta/aboutbiz"""

    # --- 图片下载 ---

    async def download_image(self, image_url: str) -> bytes:
        """下载单张图片二进制"""

    async def close(self):
        await self._client.aclose()
```

### 4.2 `core.py` — 主爬虫类

```python
class WeChatCrawler(AbstractCrawler):
    """微信公众号爬虫 — 通过调用 wechat_crawler API 实现"""

    def __init__(self):
        self.client: Optional[WeChatClient] = None

    async def start(self):
        # 1. 初始化客户端（用配置中的 base_url + auth_key）
        # 2. 验证 auth-key 有效性
        # 3. 分发：search / detail / creator
        # 4. 清理

    async def search(self):
        """关键词搜索公众号 → 遍历结果 → 爬取文章"""
        # 遍历 config.KEYWORDS
        # 调用 client.search_accounts(keyword)
        # 对每个公众号调用 _crawl_creator_articles(fakeid)

    async def get_specified_articles(self):
        """detail 模式：爬取指定文章 URL 列表"""
        # 遍历 WECHAT_SPECIFIED_ARTICLE_URL_LIST
        # 调用 client.download_article(url, format)
        # 提取图片并下载
        # 存储

    async def get_creators_and_articles(self):
        """creator 模式（核心）：爬取给定创作者列表的全部文章"""
        # 遍历 WECHAT_CREATOR_ID_LIST（fakeid 列表）
        # 对每个 fakeid:
        #   1. 获取创作者信息 → store_creator
        #   2. 分页获取全部文章列表 → _fetch_all_articles(fakeid)
        #   3. 对每篇文章:
        #      a. 下载文章内容（HTML + text）
        #      b. 从 HTML 提取图片列表
        #      c. 下载图片到本地
        #      d. store_content
        #   4. 请求间隔控制

    async def _fetch_all_articles(self, fakeid: str) -> List[Dict]:
        """分页获取全部文章"""
        # 循环调用 client.get_article_list(fakeid, begin)
        # 直到无更多数据或达到 CRAWLER_MAX_NOTES_COUNT
        # 每页间隔 WECHAT_REQUEST_INTERVAL 秒

    async def launch_browser(self, ...):
        """微信模块不需要浏览器，空实现"""
        pass
```

### 4.3 `help.py` — 辅助函数

```python
def extract_images_from_html(html: str) -> List[str]:
    """从归一化后的 HTML 中提取所有图片 URL"""
    # BeautifulSoup 解析
    # 提取 <img> 的 src 和 data-src
    # 标准化 URL（补全 https://）
    # 去重

def build_image_filename(url: str, index: int) -> str:
    """根据 URL 生成图片文件名"""
    # 优先从 URL 路径提取原始文件名
    # 回退 {index}.{ext}

def validate_article_url(url: str) -> bool:
    """校验是否为合法的微信公众号文章 URL"""

def sanitize_filename(name: str, max_length: int = 100) -> str:
    """清理文件名中的非法字符"""
```

### 4.4 `config/wechat_config.py` — 配置

```python
# ==================== 微信公众号爬虫配置 ====================

# wechat_crawler 服务地址（本地部署或远程部署）
WECHAT_API_BASE_URL = "http://localhost:3000"

# API 密钥（从 wechat_crawler 网站登录后获取）
WECHAT_AUTH_KEY = ""

# 请求间隔（秒），防止触发反爬
WECHAT_REQUEST_INTERVAL = 3

# 文章下载格式: html / markdown / text / json
WECHAT_DOWNLOAD_FORMAT = "html"

# 是否同时保存 Markdown 格式（额外存一份）
WECHAT_SAVE_MARKDOWN = True

# 是否下载文章中的图片到本地
WECHAT_DOWNLOAD_IMAGES = True

# 图片下载并发数
WECHAT_IMAGE_CONCURRENCY = 3

# --------------- detail 模式 ---------------
# 指定文章 URL 列表
WECHAT_SPECIFIED_ARTICLE_URL_LIST: list[str] = [
    # "https://mp.weixin.qq.com/s/xxx",
]

# --------------- creator 模式 ---------------
# 指定公众号 fakeid 列表（从搜索结果中获取）
WECHAT_CREATOR_ID_LIST: list[str] = [
    # "MzA3NzAyMzMyMA==",  # 示例：铁路12306
]
```

### 4.5 `model/m_wechat.py` — 数据模型

```python
from pydantic import BaseModel, Field

class WeChatCreatorInfo(BaseModel):
    """公众号创作者信息（用于 creator 列表配置）"""
    fakeid: str = Field(title="公众号唯一标识")

class WeChatAccountInfo(BaseModel):
    """公众号搜索结果"""
    fakeid: str = ""
    nickname: str = ""
    alias: str = ""
    round_head_img: str = ""
    service_type: int = 0
    signature: str = ""
    verify_status: int = 0
```

### 4.6 `store/wechat/__init__.py` — 存储层

遵循 XHS 模式，提供以下函数：

```python
class WechatStoreFactory:
    STORES = {
        "csv": WechatCsvStoreImplement,
        "db": WechatDbStoreImplement,
        "json": WechatJsonStoreImplement,
        "sqlite": WechatSqliteStoreImplement,
        "mongodb": WechatMongoStoreImplement,
        "excel": WechatExcelStoreImplement,
    }

async def update_wechat_article(article_item: Dict):
    """规范化文章数据并存储"""
    local_db_item = {
        "article_id": article_item.get("aid"),
        "title": article_item.get("title"),
        "cover": article_item.get("cover"),
        "link": article_item.get("link"),
        "digest": article_item.get("digest"),
        "author_name": article_item.get("author_name"),
        "fakeid": article_item.get("fakeid"),
        "create_time": article_item.get("create_time"),
        "update_time": article_item.get("update_time"),
        "content_html": article_item.get("content_html", ""),
        "content_text": article_item.get("content_text", ""),
        "content_markdown": article_item.get("content_markdown", ""),
        "image_list": article_item.get("image_list", ""),
        "is_deleted": article_item.get("is_deleted", False),
        "source_keyword": source_keyword_var.get(),
        "last_modify_ts": utils.get_current_timestamp(),
    }
    await WechatStoreFactory.create_store().store_content(local_db_item)

async def save_creator(fakeid: str, creator_info: Dict):
    """存储公众号创作者信息"""
    local_db_item = {
        "fakeid": fakeid,
        "nickname": creator_info.get("nickname", ""),
        "alias": creator_info.get("alias", ""),
        "signature": creator_info.get("signature", ""),
        "round_head_img": creator_info.get("round_head_img", ""),
        "identity_name": creator_info.get("identity_name", ""),
        "is_verify": creator_info.get("is_verify", 0),
        "original_article_count": creator_info.get("original_article_count", 0),
        "service_type": creator_info.get("service_type", 0),
        "last_modify_ts": utils.get_current_timestamp(),
    }
    await WechatStoreFactory.create_store().store_creator(local_db_item)

async def update_wechat_article_image(article_id: str, pic_content: bytes, filename: str):
    """保存文章图片到磁盘"""
```

### 4.7 数据库表结构（追加到 `database/models.py`）

```python
class WechatArticle(Base):
    __tablename__ = "wechat_article"
    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(String(64), index=True, unique=True)
    title = Column(String(512))
    cover = Column(String(1024))
    link = Column(String(1024))
    digest = Column(Text)
    author_name = Column(String(128))
    fakeid = Column(String(64), index=True)
    create_time = Column(BigInteger)
    update_time = Column(BigInteger)
    content_html = Column(Text)
    content_text = Column(Text)
    content_markdown = Column(Text)
    image_list = Column(Text)              # 逗号分隔的图片 URL
    is_deleted = Column(Boolean, default=False)
    source_keyword = Column(String(128))
    last_modify_ts = Column(BigInteger)

class WechatCreator(Base):
    __tablename__ = "wechat_creator"
    id = Column(Integer, primary_key=True, autoincrement=True)
    fakeid = Column(String(64), index=True, unique=True)
    nickname = Column(String(128))
    alias = Column(String(128))
    signature = Column(Text)
    round_head_img = Column(String(1024))
    identity_name = Column(String(256))
    is_verify = Column(Integer, default=0)
    original_article_count = Column(Integer, default=0)
    service_type = Column(Integer, default=0)
    last_modify_ts = Column(BigInteger)
```

---

## 五、核心流程 — Creator 模式端到端

这是你的核心需求：给定一组公众号 fakeid 列表，爬取所有文章的文本内容和图片资源。

```
用户配置 WECHAT_CREATOR_ID_LIST = ["MzA3NzAyMzMyMA==", "MjM5NTM0Mzg0MA=="]

WeChatCrawler.start()
  │
  ├── 1. 初始化 WeChatClient(base_url, auth_key)
  │
  ├── 2. client.check_auth_key() → 验证密钥有效性
  │       └── 失败则抛出异常，提示用户重新获取
  │
  ├── 3. get_creators_and_articles()
  │       │
  │       └── for fakeid in WECHAT_CREATOR_ID_LIST:
  │             │
  │             ├── 3a. 获取创作者信息
  │             │     ├── client.search_accounts(keyword=fakeid)  → 获取基础信息
  │             │     ├── client.get_author_info(fakeid)          → 获取主体信息
  │             │     └── save_creator(fakeid, merged_info)
  │             │
  │             ├── 3b. 分页获取全部文章列表
  │             │     └── _fetch_all_articles(fakeid)
  │             │           ├── begin=0, size=5
  │             │           ├── 循环调用 client.get_article_list(fakeid, begin)
  │             │           ├── 累加 articles，受 CRAWLER_MAX_NOTES_COUNT 限制
  │             │           └── 每页间隔 WECHAT_REQUEST_INTERVAL 秒
  │             │
  │             └── 3c. 逐篇处理文章（可并发，受 MAX_CONCURRENCY_NUM 限制）
  │                   │
  │                   ├── i.  下载文章 HTML
  │                   │     └── client.download_article(link, "html")
  │                   │
  │                   ├── ii. 下载文章纯文本
  │                   │     └── client.download_article(link, "text")
  │                   │
  │                   ├── iii. 下载 Markdown（可选）
  │                   │     └── client.download_article(link, "markdown")
  │                   │
  │                   ├── iv. 从 HTML 提取图片列表
  │                   │     └── extract_images_from_html(html_content)
  │                   │
  │                   ├── v.  下载图片到本地（并发控制）
  │                   │     └── for img_url in image_list:
  │                   │           client.download_image(img_url)
  │                   │           → save to data/wechat/images/{article_id}/
  │                   │
  │                   ├── vi. 组装数据并存储
  │                   │     └── update_wechat_article({
  │                   │           aid, title, link, content_html, content_text,
  │                   │           content_markdown, image_list, ...
  │                   │         })
  │                   │
  │                   └── vii. 间隔控制
  │                         └── sleep(WECHAT_REQUEST_INTERVAL)
  │
  └── 4. 清理
        └── client.close()
```

### 输出目录结构

```
data/wechat/
├── csv/                    # CSV 模式输出
│   └── articles.csv
├── json/                   # JSON 模式输出
│   └── articles.json
├── images/                 # 图片资源
│   ├── 2247503214_1/       # article_id 作为子目录
│   │   ├── 001.jpg
│   │   ├── 002.png
│   │   └── ...
│   └── 2247503179_1/
│       └── ...
└── markdown/               # Markdown 格式文章（可选）
    ├── 文章标题1.md
    └── 文章标题2.md
```

---

## 六、开发阶段规划

### Phase 1：最小可用版本（MVP）— 预计 2-3 小时

**目标**：跑通「给定 fakeid → 获取文章列表 → 下载文章内容 → 保存到 JSON」的链路。

| 步骤 | 文件 | 内容 |
|------|------|------|
| 1.1 | `config/wechat_config.py` | 基础配置（base_url, auth_key, creator_id_list） |
| 1.2 | `config/__init__.py` | 导入 wechat_config |
| 1.3 | `config/base_config.py` | PLATFORM 枚举中补充 "wechat" |
| 1.4 | `model/m_wechat.py` | WeChatCreatorInfo 模型 |
| 1.5 | `media_platform/wechat/__init__.py` | 导出 WeChatCrawler |
| 1.6 | `media_platform/wechat/client.py` | WeChatClient 完整实现 |
| 1.7 | `media_platform/wechat/core.py` | WeChatCrawler MVP（仅 creator 模式 + JSON 输出） |
| 1.8 | `media_platform/wechat/help.py` | extract_images_from_html, validate_article_url |
| 1.9 | `media_platform/wechat/exception.py` | AuthKeyExpiredError, ArticleFetchError |
| 1.10 | `store/wechat/__init__.py` | 最小 store（JSON 输出 + 图片下载） |
| 1.11 | `main.py` | 注册 "wechat": WeChatCrawler |

**验收标准**：
```bash
python main.py --platform wechat --type creator
# 成功获取指定公众号的文章列表
# 文章内容（HTML + TEXT）保存到 data/wechat/json/
# 文章图片下载到 data/wechat/images/
```

### Phase 2：完善存储层 — 预计 1-2 小时

| 步骤 | 内容 |
|------|------|
| 2.1 | `store/wechat/_store_impl.py` — CSV/DB/SQLite/Excel/MongoDB 存储实现 |
| 2.2 | `database/models.py` — 新增 WechatArticle, WechatCreator 表 |
| 2.3 | `store/wechat/wechat_store_media.py` — 图片存储优化（去重、断点续传） |

### Phase 3：补充 search 和 detail 模式 — 预计 1-2 小时

| 步骤 | 内容 |
|------|------|
| 3.1 | `core.py` 补充 `search()` 实现 |
| 3.2 | `core.py` 补充 `get_specified_articles()` 实现 |
| 3.3 | `media_platform/wechat/field.py` — 下载格式枚举等 |

### Phase 4：健壮性与优化 — 预计 1-2 小时

| 步骤 | 内容 |
|------|------|
| 4.1 | Auth-key 过期自动检测与提示 |
| 4.2 | 请求重试机制（指数退避） |
| 4.3 | 增量爬取（基于 last_modify_ts 跳过已有文章） |
| 4.4 | 图片下载并发控制 + 失败重试 |
| 4.5 | 日志完善（复用 `tools.utils.logger`） |
| 4.6 | Markdown 文件单独保存（含图片相对路径替换） |

---

## 七、与现有架构的适配说明

### 7.1 AbstractCrawler 接口适配

微信模块**不需要浏览器**，与其他平台有本质区别：

| 抽象方法 | 微信实现 |
|---------|---------|
| `start()` | 初始化 httpx 客户端 → 验证 auth-key → 分发任务 |
| `search()` | 调用 `/api/public/v1/account` 搜索 → 遍历结果爬取文章 |
| `launch_browser()` | **空实现**（不需要浏览器） |

### 7.2 不需要的模块

| 模块 | 原因 |
|------|------|
| `login.py` | 登录在 wechat_crawler 端完成，这边只需 auth-key |
| `AbstractLogin` | 同上 |
| `AbstractApiClient` | 不走浏览器，不需要 Cookie 同步 |
| Playwright 相关 | 完全不需要 |

### 7.3 复用的模块

| MediaCrawler 现有模块 | 如何复用 |
|----------------------|---------|
| `config.CRAWLER_TYPE` | "creator" 模式直接对应 |
| `config.KEYWORDS` | search 模式使用 |
| `config.CRAWLER_MAX_NOTES_COUNT` | 文章数量上限 |
| `config.MAX_CONCURRENCY_NUM` | 文章下载并发数 |
| `config.ENABLE_GET_MEIDAS` | 控制是否下载图片 |
| `config.SAVE_DATA_OPTION` | 存储后端选择 |
| `tools.utils.logger` | 日志 |
| `tools.utils.get_current_timestamp` | 时间戳 |
| `var.source_keyword_var` | 关键词上下文 |
| `var.crawler_type_var` | 爬取类型上下文 |

---

## 八、风险与注意事项

1. **Auth-Key 有效期**：与 wechat_crawler 的登录状态绑定（约 4 天），过期需要重新登录 wechat_crawler 网站获取新密钥。需在程序启动时校验，过期时给出明确提示。

2. **wechat_crawler 服务依赖**：本方案依赖 wechat_crawler 服务持续运行。如果使用官方部署的公共服务，需注意：
   - 可能有请求频率限制
   - 官方已提示后续可能收费
   - 建议私有部署 wechat_crawler 以保证稳定性

3. **图片下载**：通过 `/api/public/v1/download?format=html` 获取的 HTML 中图片 URL 已被归一化，可直接下载。但需注意：
   - 微信图片 CDN 可能有防盗链（需带 Referer）
   - 部分图片为 webp 格式
   - 大文章可能包含数十张图片，需控制并发

4. **session 过期标志**：文章列表接口返回 `base_resp.ret == 200003` 表示 session 过期，需要捕获并提示用户。

5. **文章去重**：使用 `article_id`（aid）作为唯一标识，DB 存储模式下通过 UNIQUE 约束自动去重。
