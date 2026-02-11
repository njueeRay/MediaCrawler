# MediaCrawler WebUI — API 接口设计

> 版本: v0.2 Draft | 日期: 2026-02-11

---

## 0. 与现有 API 的集成方式

### 0.1 现有路由结构 (api/main.py)

MediaCrawler 已有 3 个路由器，注册于 `api/main.py`：

```python
# 已有 (不修改)
app.include_router(crawler_router, prefix="/api")   # POST /api/crawler/start, /stop, GET /status, /logs
app.include_router(data_router, prefix="/api")      # GET /api/data/files, /files/{path}, /download/{path}, /stats
app.include_router(websocket_router, prefix="/api") # WS /api/ws/logs, /api/ws/status
```

此外 `main.py` 还有 4 个内联端点：`/api/health`, `/api/env/check`, `/api/config/platforms`, `/api/config/options`。

### 0.2 新增路由注册 (api/main.py 追加)

```python
# 🆕 WebUI 新增 5 个路由器 — 追加到 main.py 中已有 include_router 之后
from api.routers import (
    config_router, subscription_router, field_mapping_router,
    feishu_router, scheduler_router
)

app.include_router(config_router, prefix="/api")        # /api/config/*
app.include_router(subscription_router, prefix="/api")  # /api/subscribe/*
app.include_router(field_mapping_router, prefix="/api") # /api/mapping/*
app.include_router(feishu_router, prefix="/api")        # /api/feishu/*
app.include_router(scheduler_router, prefix="/api")     # /api/scheduler/*
```

### 0.3 路由命名空间分配

| 前缀 | 归属 | 来源文件 |
|------|------|----------|
| `/api/crawler/*` | ✅ 已有 | `api/routers/crawler.py` |
| `/api/data/*` | ✅ 已有 | `api/routers/data.py` |
| `/api/ws/*` | ✅ 已有 | `api/routers/websocket.py` |
| `/api/health` | ✅ 已有 (内联) | `api/main.py` |
| `/api/env/*` | ✅ 已有 (内联) | `api/main.py` |
| `/api/config/*` | 🆕 新增 | `api/routers/config.py` |
| `/api/subscribe/*` | 🆕 新增 | `api/routers/subscription.py` |
| `/api/mapping/*` | 🆕 新增 | `api/routers/field_mapping.py` |
| `/api/feishu/*` | 🆕 新增 | `api/routers/feishu.py` |
| `/api/scheduler/*` | 🆕 新增 | `api/routers/scheduler.py` |
| `/api/dashboard/*` | 🆕 新增 (可内联) | `api/main.py` 或独立 Router |

> **无冲突**：已有端点 `/api/config/platforms` 和 `/api/config/options` 是内联定义的，
> 与新增的 `config_router` 路径不重叠 (新 Router 使用 `/api/config/groups`、`/api/config` PUT 等)。

### 0.4 新增服务对已有设施的复用

```python
# SchedulerService 复用已有 CrawlerManager
from api.services.crawler_manager import crawler_manager  # 全局单例

class SchedulerService:
    async def execute_crawl_task(self, task: ScheduledTask):
        request = CrawlerStartRequest(
            platform=task.platform,
            crawler_type=task.task_config["crawler_type"],
            # ...
        )
        crawler_manager.start_crawler(request)  # 复用已有逻辑
```

---

## 1. API 设计规范

### 1.1 统一响应格式

```json
{
  "code": 0,
  "message": "success",
  "data": { ... }
}
```

| code | 含义 |
|------|------|
| 0 | 成功 |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 404 | 资源不存在 |
| 409 | 资源冲突 (重复) |
| 500 | 服务器内部错误 |

### 1.2 分页格式

```json
{
  "code": 0,
  "data": {
    "items": [...],
    "total": 1247,
    "page": 1,
    "size": 20,
    "pages": 63
  }
}
```

### 1.3 请求头

| Header | 说明 |
|--------|------|
| `Content-Type` | `application/json` |
| `Authorization` | `Bearer <token>` (可选，当 `WEBUI_AUTH_ENABLED=true`) |

---

## 2. 配置管理 API

### `GET /api/config/groups`

获取所有配置分组及其配置项。

**Response:**
```json
{
  "code": 0,
  "data": {
    "groups": [
      {
        "key": "feishu",
        "label": "飞书配置",
        "icon": "feishu",
        "fields": [
          {
            "key": "FEISHU_APP_ID",
            "label": "App ID",
            "type": "text",
            "value": "cli_xxxxx",
            "required": true,
            "help": "飞书开放平台应用 ID",
            "sensitive": false
          },
          {
            "key": "FEISHU_APP_SECRET",
            "label": "App Secret",
            "type": "password",
            "value": "****",
            "required": true,
            "help": "飞书开放平台应用密钥",
            "sensitive": true
          }
        ]
      }
    ]
  }
}
```

### `PUT /api/config`

批量更新配置项。

**Request:**
```json
{
  "configs": {
    "FEISHU_APP_ID": "cli_new_value",
    "FEISHU_APP_SECRET": "new_secret",
    "FEISHU_BATCH_SIZE": "500"
  }
}
```

**Response:**
```json
{
  "code": 0,
  "message": "配置已更新，共修改 3 项",
  "data": {
    "updated": ["FEISHU_APP_ID", "FEISHU_APP_SECRET", "FEISHU_BATCH_SIZE"],
    "reload_required": false
  }
}
```

### `POST /api/config/test`

测试连接。

**Request:**
```json
{
  "type": "feishu"
}
```

**Response:**
```json
{
  "code": 0,
  "data": {
    "success": true,
    "message": "飞书连接成功，App: MediaCrawler同步助手",
    "details": {
      "app_name": "MediaCrawler同步助手",
      "permissions": ["bitable:app", "drive:drive"]
    }
  }
}
```

### `GET /api/config/history`

获取配置变更历史。

**Query:** `?page=1&size=20`

---

## 3. 订阅管理 API

### `POST /api/subscribe/search`

搜索各平台创作者。

**Request:**
```json
{
  "platform": "xhs",
  "keyword": "UI设计"
}
```

**Response:**
```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "creator_id": "5a1b2c3d",
        "creator_name": "UI设计日记",
        "creator_avatar": "https://...",
        "creator_url": "https://www.xiaohongshu.com/user/...",
        "meta": {
          "fans_count": 83000,
          "note_count": 128,
          "signature": "分享UI设计灵感与教程"
        },
        "is_subscribed": true
      }
    ]
  }
}
```

### `POST /api/subscribe`

订阅创作者。

**Request:**
```json
{
  "platform": "xhs",
  "creator_id": "5a1b2c3d",
  "creator_name": "UI设计日记",
  "creator_avatar": "https://...",
  "creator_url": "https://...",
  "creator_meta": { "fans_count": 83000 },
  "tags": ["设计", "重要"],
  "notes": "知名UI设计博主"
}
```

### `GET /api/subscribe`

获取订阅列表。

**Query:** `?platform=xhs&is_active=true&tag=设计&page=1&size=20&sort=last_content_at`

**Response:**
```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": 1,
        "platform": "xhs",
        "creator_id": "5a1b2c3d",
        "creator_name": "UI设计日记",
        "creator_avatar": "https://...",
        "creator_meta": { "fans_count": 83000 },
        "is_active": true,
        "auto_crawl": true,
        "last_crawled_at": "2026-02-11T10:32:00",
        "last_content_at": "2026-02-10T15:20:00",
        "content_count": 128,
        "tags": ["设计", "重要"]
      }
    ],
    "total": 86,
    "page": 1,
    "size": 20
  }
}
```

### `GET /api/subscribe/{id}`

获取订阅详情。

### `PUT /api/subscribe/{id}`

更新订阅配置（标签、备注、活跃状态等）。

### `DELETE /api/subscribe/{id}`

取消订阅。

### `POST /api/subscribe/{id}/crawl`

立即采集该订阅创作者的内容。

**Response:**
```json
{
  "code": 0,
  "data": {
    "execution_id": 42,
    "message": "已启动采集任务"
  }
}
```

### `GET /api/subscribe/{id}/content`

获取该订阅创作者的已采集内容列表。

**Query:** `?date_start=2026-01-01&date_end=2026-02-11&type=图文&page=1&size=20`

---

## 4. 数据浏览 API

### `GET /api/data/sources`

获取可用数据源列表。

**Response:**
```json
{
  "code": 0,
  "data": {
    "sources": [
      {
        "key": "xhs_note",
        "label": "小红书笔记",
        "platform": "xhs",
        "data_type": "note",
        "record_count": 3420,
        "fields": ["note_id", "title", "desc", "nickname", "liked_count", ...]
      },
      {
        "key": "wechat_article",
        "label": "微信公众号文章",
        "platform": "wechat",
        "data_type": "article",
        "record_count": 1562,
        "fields": ["article_id", "title", "digest", "account_nickname", ...]
      }
    ]
  }
}
```

### `GET /api/data/query`

查询数据 (统一接口)。

**Query:**
```
source=xhs_note          # 数据源
page=1&size=20            # 分页
sort=liked_count&order=desc  # 排序
date_start=2026-01-01     # 日期过滤
date_end=2026-02-11
keyword=设计              # 关键词搜索
creator_id=5a1b2c3d       # 创作者过滤
mapping_scheme_id=1       # 应用字段映射 (可选)
fields=title,liked_count,time  # 指定返回字段 (可选)
```

**Response:**
```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "note_id": "6a8f1234",
        "title": "2026年UI设计趋势盘点",
        "desc": "今天来聊聊2026年最值得关注的UI设计趋势...",
        "nickname": "UI设计日记",
        "type": "图文",
        "liked_count": 2300,
        "collected_count": 1200,
        "comment_count": 89,
        "time": "2026-02-10",
        "tag_list": "[\"UI设计\", \"设计趋势\", \"2026\"]",
        "note_url": "https://www.xiaohongshu.com/explore/6a8f1234"
      }
    ],
    "total": 1247,
    "page": 1,
    "size": 20,
    "applied_mapping": null
  }
}
```

### `GET /api/data/query` (应用映射)

当指定 `mapping_scheme_id` 时，返回映射后的数据：

```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "笔记ID": "6a8f1234",
        "标题": "2026年UI设计趋势盘点",
        "内容摘要": "今天来聊聊2026年最值得关注的...",
        "用户昵称": "UI设计日记",
        "点赞数": 2300,
        "发布时间": "2026-02-10"
      }
    ],
    "total": 1247,
    "applied_mapping": {
      "scheme_id": 1,
      "scheme_name": "系统默认"
    }
  }
}
```

### `GET /api/data/{source}/{id}`

获取单条记录详情。

### `POST /api/data/export`

导出数据。

**Request:**
```json
{
  "source": "xhs_note",
  "format": "csv",
  "mapping_scheme_id": 1,
  "filters": {
    "date_start": "2026-01-01",
    "date_end": "2026-02-11"
  }
}
```

**Response:** 返回文件下载流。

### `DELETE /api/data/batch`

批量删除数据。

**Request:**
```json
{
  "source": "xhs_note",
  "ids": ["6a8f1234", "7b2c5678"]
}
```

---

## 5. 字段映射 API

### `GET /api/mapping/schemes`

获取映射方案列表。

**Query:** `?platform=xhs&data_type=note`

**Response:**
```json
{
  "code": 0,
  "data": {
    "schemes": [
      {
        "id": 1,
        "name": "系统默认",
        "platform": "xhs",
        "data_type": "note",
        "is_default": true,
        "is_system": true,
        "item_count": 19,
        "enabled_count": 13,
        "created_at": "2026-02-11T00:00:00"
      },
      {
        "id": 5,
        "name": "飞书精简版",
        "platform": "xhs",
        "data_type": "note",
        "is_default": false,
        "is_system": false,
        "item_count": 19,
        "enabled_count": 7,
        "created_at": "2026-02-11T14:30:00"
      }
    ]
  }
}
```

### `GET /api/mapping/schemes/{id}`

获取映射方案详情（含所有字段映射项）。

**Response:**
```json
{
  "code": 0,
  "data": {
    "id": 1,
    "name": "系统默认",
    "platform": "xhs",
    "data_type": "note",
    "items": [
      {
        "id": 1,
        "source_field": "note_id",
        "display_name": "笔记ID",
        "enabled": true,
        "sort_order": 1,
        "feishu_type": "text",
        "feishu_options": {},
        "transform": "none",
        "transform_config": {}
      },
      {
        "id": 7,
        "source_field": "liked_count",
        "display_name": "点赞数",
        "enabled": true,
        "sort_order": 7,
        "feishu_type": "number",
        "feishu_options": {"formatter": "0,0"},
        "transform": "none",
        "transform_config": {}
      }
    ]
  }
}
```

### `POST /api/mapping/schemes`

创建新映射方案。

**Request:**
```json
{
  "name": "飞书精简版",
  "platform": "xhs",
  "data_type": "note",
  "description": "仅包含核心字段的精简方案",
  "copy_from_id": 1,
  "items": [...]
}
```

### `PUT /api/mapping/schemes/{id}`

更新映射方案（包括字段项）。

**Request:**
```json
{
  "name": "系统默认 (修改版)",
  "items": [
    {
      "id": 1,
      "display_name": "笔记编号",
      "enabled": true,
      "sort_order": 1,
      "feishu_type": "text"
    },
    {
      "id": 7,
      "display_name": "获赞数",
      "enabled": true,
      "sort_order": 2,
      "feishu_type": "number"
    }
  ]
}
```

### `DELETE /api/mapping/schemes/{id}`

删除映射方案（系统方案不可删除）。

### `POST /api/mapping/preview`

预览映射效果。

**Request:**
```json
{
  "scheme_id": 1,
  "sample_data": {
    "note_id": "6a8f1234",
    "title": "UI趋势盘点",
    "liked_count": 2300,
    "time": "1707580800"
  }
}
```

**Response:**
```json
{
  "code": 0,
  "data": {
    "original": {
      "note_id": "6a8f1234",
      "title": "UI趋势盘点",
      "liked_count": 2300,
      "time": "1707580800"
    },
    "mapped": {
      "笔记ID": "6a8f1234",
      "标题": "UI趋势盘点",
      "点赞数": 2300,
      "发布时间": "2026-02-10"
    }
  }
}
```

---

## 6. 飞书同步 API

### `GET /api/feishu/status`

获取飞书连接状态。

**Response:**
```json
{
  "code": 0,
  "data": {
    "connected": true,
    "app_name": "MediaCrawler同步助手",
    "app_token": "bascnXXX...",
    "tables": [
      {
        "table_id": "tblXXX",
        "name": "XHS笔记_20260210",
        "record_count": 890
      }
    ]
  }
}
```

### `POST /api/feishu/sync`

创建并执行同步任务。

**Request:**
```json
{
  "source": "xhs_note",
  "mapping_scheme_id": 1,
  "date_range": {
    "start": "2026-01-01",
    "end": "2026-02-11"
  },
  "target": {
    "type": "auto",
    "table_name": "XHS笔记_20260211"
  },
  "batch_size": 500
}
```

**Response:**
```json
{
  "code": 0,
  "data": {
    "sync_id": 15,
    "status": "running",
    "total_records": 1247,
    "message": "同步任务已启动"
  }
}
```

### `GET /api/feishu/sync/{sync_id}`

查询同步任务进度。

**Response:**
```json
{
  "code": 0,
  "data": {
    "sync_id": 15,
    "status": "running",
    "progress": {
      "total": 1247,
      "processed": 500,
      "success": 498,
      "failed": 2,
      "percent": 40.1
    },
    "current_batch": 1,
    "total_batches": 3,
    "elapsed_seconds": 15
  }
}
```

### `GET /api/feishu/history`

获取同步历史列表。

**Query:** `?platform=xhs&page=1&size=20`

### `POST /api/feishu/sync/{sync_id}/cancel`

取消正在执行的同步任务。

---

## 7. 任务调度 API

### `GET /api/scheduler/status`

获取调度器状态。

**Response:**
```json
{
  "code": 0,
  "data": {
    "running": true,
    "active_tasks": 4,
    "paused_tasks": 1,
    "running_executions": 1,
    "next_execution": {
      "task_name": "微信文章采集",
      "run_at": "2026-02-11T16:00:00"
    }
  }
}
```

### `GET /api/scheduler/tasks`

获取任务列表。

### `POST /api/scheduler/tasks`

创建新任务。

**Request:**
```json
{
  "name": "XHS日常采集",
  "task_type": "crawl",
  "platform": "xhs",
  "schedule_type": "cron",
  "schedule_config": {
    "hour": "8",
    "minute": "0"
  },
  "task_config": {
    "crawler_type": "creator",
    "subscription_ids": [1, 2, 3],
    "enable_comments": true,
    "save_option": "db"
  }
}
```

### `PUT /api/scheduler/tasks/{id}`

更新任务配置。

### `DELETE /api/scheduler/tasks/{id}`

删除任务。

### `POST /api/scheduler/tasks/{id}/run`

手动触发任务执行。

### `POST /api/scheduler/tasks/{id}/toggle`

启用/暂停任务。

### `GET /api/scheduler/tasks/{id}/executions`

获取某任务的执行历史。

**Query:** `?page=1&size=20&status=success`

### `GET /api/scheduler/executions`

获取全局执行历史。

---

## 8. 爬虫控制 API (已有，扩展)

### `POST /api/crawler/start` (已有)

启动爬虫任务。

### `POST /api/crawler/stop` (已有)

停止爬虫。

### `GET /api/crawler/status` (已有)

获取运行状态。

### `GET /api/crawler/logs` (已有)

获取最近日志。

---

## 9. WebSocket API (已有，扩展)

### `WS /api/ws/logs` (已有)

实时日志流。

**消息格式:**
```json
{
  "type": "log",
  "level": "INFO",
  "timestamp": "2026-02-11T10:32:15",
  "source": "xhs",
  "message": "获取笔记列表第1页, 共20条"
}
```

### `WS /api/ws/status` (已有)

实时状态推送。

### `WS /api/ws/sync` (新增)

飞书同步进度推送。

**消息格式:**
```json
{
  "type": "sync_progress",
  "sync_id": 15,
  "processed": 500,
  "total": 1247,
  "percent": 40.1,
  "status": "running"
}
```

---

## 10. 仪表盘聚合 API

### `GET /api/dashboard/overview`

获取仪表盘概览数据（聚合多个数据源）。

**Response:**
```json
{
  "code": 0,
  "data": {
    "system": {
      "running_tasks": 2,
      "today_crawled": 347,
      "pending_sync": 1200,
      "uptime_hours": 48.5
    },
    "stats": {
      "total_content": 12400,
      "total_creators": 86,
      "total_comments": 45000,
      "by_platform": {
        "xhs": {"content": 3420, "creators": 25},
        "wechat": {"content": 1562, "creators": 18},
        "dy": {"content": 2890, "creators": 15},
        "bili": {"content": 1800, "creators": 12},
        "wb": {"content": 1200, "creators": 8},
        "tieba": {"content": 980, "creators": 4},
        "zhihu": {"content": 548, "creators": 4}
      }
    },
    "services": {
      "api": {"status": "healthy", "latency_ms": 12},
      "wechat_exporter": {"status": "healthy", "url": "http://localhost:3000"},
      "feishu": {"status": "healthy", "app": "MediaCrawler同步助手"},
      "database": {"status": "healthy", "type": "sqlite"}
    },
    "recent_content": [
      {
        "platform": "xhs",
        "creator_name": "UI设计日记",
        "title": "2026年UI设计趋势盘点",
        "time": "2026-02-10T15:20:00"
      }
    ],
    "recent_tasks": [
      {
        "name": "XHS创作者采集",
        "status": "success",
        "platform": "xhs",
        "duration_seconds": 150,
        "finished_at": "2026-02-11T10:02:30"
      }
    ]
  }
}
```

---

## 11. 接口依赖关系

```
Dashboard ──────▶ /api/dashboard/overview
                      ├── /api/data/stats
                      ├── /api/scheduler/status
                      ├── /api/feishu/status
                      └── /api/health

Config ─────────▶ /api/config/*
                      └── /api/config/test (飞书/DB/微信源)

Subscription ───▶ /api/subscribe/*
                      ├── /api/subscribe/search (调用平台 Client)
                      └── /api/subscribe/{id}/crawl (调用 CrawlerManager)

DataExplorer ───▶ /api/data/*
                      ├── /api/data/sources
                      ├── /api/data/query (+ mapping)
                      └── /api/data/export

FieldMapping ───▶ /api/mapping/*
                      ├── /api/mapping/schemes
                      └── /api/mapping/preview

FeishuSync ─────▶ /api/feishu/*
                      ├── /api/mapping/schemes (选择映射)
                      ├── /api/data/query (预览数据)
                      └── WS /api/ws/sync (进度)

TaskScheduler ──▶ /api/scheduler/*
                      ├── /api/subscribe (关联订阅)
                      └── /api/mapping/schemes (关联映射)

Logs ───────────▶ WS /api/ws/logs
                  WS /api/ws/status
```

---

*上一篇: [04-数据模型设计](./04-数据模型设计.md)*
