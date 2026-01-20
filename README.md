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
| 功能模块 | 飞书同步 | AI数据清洗 | 自动化调度 | 监控告警 | 容器部署 | Web界面 | API服务 |
| -------- | -------- | ---------- | ---------- | -------- | -------- | ------- | ------- |
| 当前版本 | ✅        | ⏳         | ⏳         | ⏳       | ⏳       | 📋      | 📋      |
| 计划版本 | ✅        | ✅          | ✅          | ✅        | ✅        | ✅       | ✅       |

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

### 3. 飞书数据同步（新增功能）
```bash
# 激活虚拟环境
source venv/bin/activate

# 同步单个文件到飞书
python feishu_sync_simple.py --file data/xhs/json/search_contents_2025-09-05.json

# 批量同步整个目录
python feishu_sync_simple.py --dir data/xhs/json/ --batch-size 50
```

### 4. 自动化调度（智能增强）
```bash
# 启动自动化调度器（7x24小时运行）
./start_scheduler.sh

# 单次执行特定任务
python auto_scheduler.py --mode once --task daily
```

## 📁 项目结构

```
MediaCrawler/
├── 📂 原版爬虫模块/
│   ├── main.py                   # 主爬虫程序
│   ├── media_platform/           # 各平台爬虫实现
│   ├── config/                   # 爬虫配置
│   └── README_original.md        # 📖 原版完整文档
│
├── 🚀 飞书同步模块/
│   ├── feishu_sync_simple.py     # 核心同步脚本
│   ├── feishu_sync/              # 支持模块
│   │   ├── config.py            # 配置管理
│   │   └── data_formatter.py    # 数据格式化
│   └── docs/feishu/             # 📚 飞书文档
│
├── 🤖 自动化模块/
│   ├── auto_scheduler.py         # 自动化调度器
│   ├── ai_processor/             # AI数据处理
│   └── monitoring/               # 监控模块
│
├── 🛠️ 部署工具/
│   ├── setup.sh                  # 一键安装脚本
│   ├── docker-compose.yml        # 容器编排
│   └── requirements.txt          # 依赖管理
│
└── 📊 数据存储/
    ├── data/                     # 爬虫数据
    ├── logs/                     # 运行日志
    └── config/                   # 用户配置
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

### 📅 近期计划 (v1.1 - v1.2)
- [x] 飞书数据同步功能
- [ ] AI数据清洗和质量评分
- [ ] 自动化调度和监控
- [ ] 容器化部署方案

### 🚀 中期规划 (v2.0)
- [ ] Web管理界面
- [ ] RESTful API服务
- [ ] 多平台数据融合
- [ ] 实时数据可视化

### 🌟 长期愿景 (v3.0+)
- [ ] 企业级数据中台
- [ ] AI驱动的智能分析
- [ ] 多租户SaaS服务
- [ ] 开放API生态

详细规划请查看：[📋 完整发展规划](docs/feishu/todo.md)

## 📚 文档索引

### 🔗 核心文档
- **[原版功能文档](README_original.md)** - 完整的爬虫功能说明
- **[飞书同步指南](docs/feishu/feishu_README.md)** - 飞书集成实现说明
- **[开发者文档](docs/feishu/飞书开发说明.md)** - 技术实现详解
- **[发展规划](docs/feishu/todo.md)** - 完整的项目路线图

### 🎯 快速导航
- **新用户** → [快速开始](#-快速开始) → [飞书配置](docs/feishu/快速接入多维表格.md)
- **开发者** → [项目结构](#-项目结构) → [开发文档](docs/feishu/飞书开发说明.md)
- **企业用户** → [部署指南](#-高级配置) → [商业化规划](docs/feishu/todo.md#-商业化路径)

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