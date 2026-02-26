# 🔥 MediaCrawler 增强版 - 多平台数据采集与同步平台

<div align="center">

[![GitHub Stars](https://img.shields.io/github/stars/njueeRay/MediaCrawler?style=social)](https://github.com/njueeRay/MediaCrawler/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/njueeRay/MediaCrawler?style=social)](https://github.com/njueeRay/MediaCrawler/network/members)
[![License](https://img.shields.io/github/license/njueeRay/MediaCrawler)](https://github.com/njueeRay/MediaCrawler/blob/main/LICENSE)
[![Python](https://img.shields.io/badge/Python-3.8+-blue)](https://www.python.org/)
[![Feishu](https://img.shields.io/badge/飞书-集成-green)](https://open.feishu.cn/)

</div>

## 📖 项目简介

基于 [原版MediaCrawler](README_original.md) 的增强版本，在保留原有强大爬虫功能的基础上，**新增了飞书多维表格数据同步和自动化处理能力**，打造一站式数据采集与分析平台。

### 🆕 新增核心功能

- **🚀 飞书数据同步** - 一键将爬取数据同步到飞书多维表格
- **🤖 AI智能处理** - 自动数据清洗、质量评分、内容分类
- **⏰ 自动化调度** - 定时任务、文件监控、智能重试
- **📊 监控告警** - 实时状态监控、异常告警通知
- **🐳 容器化部署** - 一键部署、轻量级运行

## ✨ 功能特性对比

### 🔥 原版功能（完整保留）
| 平台   | 关键词搜索 | 指定帖子ID爬取 | 二级评论 | 指定创作者主页 | 登录态缓存 | IP代理池 | 生成评论词云图 |
| ------ | ---------- | -------------- | -------- | -------------- | ---------- | -------- | -------------- |
| 小红书 | ✅          | ✅              | ✅        | ✅              | ✅          | ✅        | ✅              |
| 抖音   | ✅          | ✅              | ✅        | ✅              | ✅          | ✅        | ✅              |
| 快手   | ✅          | ✅              | ✅        | ✅              | ✅          | ✅        | ✅              |
| B 站   | ✅          | ✅              | ✅        | ✅              | ✅          | ✅        | ✅              |
| 微博   | ✅          | ✅              | ✅        | ✅              | ✅          | ✅        | ✅              |
| 贴吧   | ✅          | ✅              | ✅        | ✅              | ✅          | ✅        | ✅              |

### 🚀 增强功能（新增）
| 功能模块 | 飞书同步 | WebUI控制台 | API服务 | 任务调度 | Pipeline引擎 | AI数据清洗 | 容器部署 |
| -------- | -------- | ----------- | ------- | -------- | ----------- | ---------- | -------- |
| 当前版本 | ✅ | ✅ | ✅ | ✅ | ✅ | ⏳ | ⏳ |
| 说明 | 全链路同步 | Sprint 3 完成 | FastAPI | Cron+手动触发 | 5步骤模块化 | 开发中 | 开发中 |

> ✅ 已完成 | ⏳ 开发中 | 📋 已规划

## 🎯 快速开始

### 1. 环境准备
```bash
# 克隆项目
git clone https://github.com/njueeRay/MediaCrawler.git
cd MediaCrawler

# 一键安装和配置
chmod +x setup.sh
./setup.sh
```

### 2. 基础爬虫（原版功能）
```bash
# 爬取小红书数据
python main.py --platform xhs --type search --keywords "投资理财"

# 详细使用方法参考原版文档
cat README_original.md
```

### 3. 启动 WebUI 控制台（新增功能）
```bash
# 启动 API 服务器（端口 8080）
uv run uvicorn api.main:app --host 0.0.0.0 --port 8080

# 浏览器访问 WebUI 控制台
open http://localhost:8080
```

### 4. 飞书数据同步
```bash
# 同步单个 JSON/CSV 文件
uv run sync_to_feishu.py --file data/xhs/json/search_contents.json

# 批量同步整个目录
uv run sync_to_feishu.py --dir data/xhs/json/ --batch-size 50

# Pipeline 全链路（飞书拉取 → 爬虫 → 飞书推送）
# 通过 WebUI 控制台的「订阅任务」配置并触发
```

### 5. 自动化调度
```bash
# WebUI 控制台创建定时任务并管理调度
# 或通过 API 直接触发
curl -X POST http://localhost:8080/api/scheduler/tasks/{id}/trigger
```

## 📁 项目结构

```
MediaCrawler/
├── 📂 爬虫核心
│   ├── main.py                   # 爬虫入口
│   ├── media_platform/           # 各平台实现（XHS/抖音/B站/微博等）
│   └── config/                   # 爬虫配置
│
├── 🚀 飞书同步模块
│   ├── sync_to_feishu.py         # 统一 CLI（同步/追加/JSON展开）
│   ├── feishu_sync/              # 核心库
│   │   ├── sync_manager.py       # 建表/建字段/批量写入
│   │   ├── data_formatter.py     # 数据格式化
│   │   ├── image_uploader.py     # 图片/附件上传
│   │   ├── json_column_sync.py   # JSON列展开同步
│   │   └── read_from_feishu.py   # 飞书数据拉取
│   └── docs/feishu/              # 飞书相关文档
│
├── 🖥️ WebUI 控制台
│   ├── api/                      # FastAPI 后端
│   │   ├── main.py               # API 入口
│   │   ├── routers/              # 路由（爬虫/调度/订阅/配置）
│   │   ├── services/             # 业务逻辑（含 pipeline_steps.py）
│   │   └── webui/                # 前端静态文件
│   └── webui-src/                # Vue3 前端源码
│
├── ⏰ 任务调度
│   ├── auto_scheduler.py         # 独立调度器
│   └── api/services/scheduler_service.py  # WebUI 集成调度
│
└── 🗄️  数据存储
    ├── database/                 # ORM 模型（SQLite/MySQL）
    ├── store/                    # 存储适配层（CSV/JSON/DB/Excel）
    └── data/                     # 爬取数据输出目录
```

## 🎯 核心优势

### 🔥 技术优势
- **无逆向工程** - 基于Playwright浏览器自动化，避免复杂的JS逆向
- **稳定可靠** - 经过生产环境验证，1794条评论+400条笔记成功同步
- **模块化设计** - 松耦合架构，易于扩展和维护
- **配置驱动** - 通过配置文件灵活控制行为

### 🚀 业务优势
- **一站式解决方案** - 从数据采集到分析展示的完整闭环
- **智能化处理** - AI驱动的数据清洗和质量控制
- **企业级特性** - 监控、告警、备份、恢复等生产级功能
- **商业化就绪** - 支持SaaS模式和私有部署

## 📊 使用案例

### 📈 数据分析场景
```bash
# 1. 爬取竞品分析数据
python main.py --platform xhs --type search --keywords "竞品关键词"

# 2. AI清洗和质量评分
python auto_scheduler.py --mode once --task ai_clean

# 3. 同步到飞书进行分析
python feishu_sync_simple.py --dir data/xhs/json/ --batch-size 50
```

### 🤖 自动化监控场景
```bash
# 1. 启动7x24小时自动化监控
./start_scheduler.sh

# 监控内容：
# - 每日2点自动爬取
# - 实时文件监控
# - AI智能处理
# - 自动同步飞书
# - 异常告警通知
```

## 🛠️ 高级配置

### 飞书应用配置
```bash
# .env 文件配置
FEISHU_APP_ID=your_app_id
FEISHU_APP_SECRET=your_app_secret
FEISHU_APP_TOKEN=your_app_token

# AI处理配置（可选）
OPENAI_API_KEY=your_openai_key
AI_MODEL=gpt-3.5-turbo
QUALITY_THRESHOLD=0.7
```

### 工作流配置
```yaml
# config/workflow.yaml
name: "daily_sync"
schedule: "0 2 * * *"  # 每日2点执行

tasks:
  - name: "crawl_data"
    type: "crawler"
    config: { keywords: ["投资", "创业"], limit: 1000 }
  
  - name: "ai_clean"
    type: "ai_processor"
    depends_on: ["crawl_data"]
    config: { quality_threshold: 0.7 }
  
  - name: "sync_feishu"
    type: "feishu_sync"
    depends_on: ["ai_clean"]
    config: { batch_size: 50 }
```

## 🔮 发展规划

### ✅ 已完成
- [x] 飞书多维表格全链路数据同步
- [x] WebUI 控制台（Vue3 + FastAPI，Sprint 1~3 验收通过）
- [x] RESTful API 服务
- [x] 任务调度系统（Cron + 手动触发）
- [x] Pipeline 模块化引擎（5步骤：爬取 → 飞书拉取 → 飞书推送 → 数据处理）
- [x] SQLite 中间层（feishu_record_snapshot）

### 🔮 规划中
- [ ] AI 数据清洗和质量评分
- [ ] 容器化部署方案
- [ ] 多租户 SaaS 模式
- [ ] 实时数据可视化看板

详细规划参见：[Feishu Backlog](docs/ops/feishu-backlog.md)

## 📚 文档索引

### 🔗 用户指南（`docs/guide/`）
- [快速开始 / 环境搭建](docs/guide/quickstart.md)
- [登录方式说明](docs/guide/login.md)
- [代理IP配置（快代理 / 豌豆HTTP）](docs/guide/proxy.md)
- [数据存储配置](docs/guide/storage.md)
- [数据导出（Excel / 词云图）](docs/guide/export.md)
- [CDP模式使用](docs/guide/cdp.md)
- [自动化运行任务](docs/guide/automation.md)
- [常见问题](docs/guide/faq.md)

### 🔗 飞书集成（`docs/feishu/`）
- [飞书功能概览](docs/feishu/README.md)
- [开发配置说明](docs/feishu/dev-notes.md)

### 🔗 技术参考（`docs/reference/`）
- [项目架构总览](docs/reference/01-项目架构总览.md)
- [平台爬虫模块详解](docs/reference/02-平台爬虫模块详解.md)
- [数据存储系统详解](docs/reference/03-数据存储系统详解.md)
- [WebUI API 与可视化系统](docs/reference/06-WebUI-API与可视化系统.md)
- [全流程调试经验总结](docs/reference/07-全流程调试经验总结.md)
- [上游原版功能文档](docs/reference/upstream-readme.md)

### 🎯 快速导航
- **新用户** → [快速开始](#1-环境准备) → [飞书配置](docs/feishu/dev-notes.md)
- **开发者** → [技术参考](docs/reference/) → [WebUI开发文档](docs/dev/webui/)
- **运营团队** → [Team Playbook](docs/ops/team-playbook.md) → [飞书功能概览](docs/feishu/README.md)

## 🤝 贡献指南

欢迎参与项目开发！请查看：
- [Issues](https://github.com/njueeRay/MediaCrawler/issues) - 报告问题或提出建议
- [Pull Requests](https://github.com/njueeRay/MediaCrawler/pulls) - 提交代码贡献
- [Discussions](https://github.com/njueeRay/MediaCrawler/discussions) - 技术讨论和交流

## ⚖️ 法律声明

> **重要提醒：请遵守相关法律法规**
> 
> 本项目仅供学习和研究使用，禁止用于商业用途。使用者应当遵守目标平台的robots.txt规则和服务条款，不得进行大规模爬取或其他可能对平台造成负担的行为。对于因使用本项目而引起的任何法律问题，项目维护者不承担任何责任。
> 
> 详细声明请查看：[完整免责声明](README_original.md#disclaimer)

## 📞 联系方式

- **项目仓库**: https://github.com/njueeRay/MediaCrawler
- **问题报告**: [GitHub Issues](https://github.com/njueeRay/MediaCrawler/issues)
- **功能建议**: [GitHub Discussions](https://github.com/njueeRay/MediaCrawler/discussions)

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给个Star支持一下！**

Made with ❤️ by MediaCrawler Team

</div>