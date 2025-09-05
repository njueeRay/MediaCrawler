# 飞书多维表格数据同步

## 📋 项目简介

本项目为 MediaCrawler 提供小红书数据自动同步到飞书多维表格的功能。基于飞书官方 Python SDK (lark-oapi) 开发，支持批量同步、实时监控和自动化处理。

## 🏗️ 项目结构

```
MediaCrawler/
├── feishu_sync/                    # 飞书同步核心包
│   ├── __init__.py                # 包初始化文件
│   ├── config.py                  # 配置管理模块
│   ├── data_formatter.py          # 数据格式化器
│   ├── feishu_client.py          # 飞书API客户端
│   └── sync_manager.py           # 同步管理器
├── sync_to_feishu.py             # 主执行脚本
├── validate_feishu_setup.py      # 功能验证脚本
├── .env.example                  # 环境变量配置模板
└── docs/feishu/                  # 文档目录
    ├── README.md                 # 本文档
    ├── 飞书开发说明.md            # 详细开发文档
    └── todo.md                   # 待办清单
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 安装依赖包
pip install lark-oapi pandas python-dotenv schedule

# 创建配置文件
python sync_to_feishu.py --create-env
cp .env.example .env
```

### 2. 飞书应用配置

1. **创建飞书应用**
   - 访问 [飞书开放平台](https://open.feishu.cn/app)
   - 创建企业自建应用
   - 获取 `App ID` 和 `App Secret`

2. **配置权限**
   ```
   bitable:app - 多维表格应用权限
   bitable:app:readonly - 读取权限  
   bitable:app:readwrite - 写入权限
   ```

3. **创建多维表格**
   - 在飞书中创建新的多维表格
   - 获取 `App Token`

### 3. 配置环境变量

编辑 `.env` 文件，填入必要配置：

```bash
# 必需配置
FEISHU_APP_ID=your_app_id_here
FEISHU_APP_SECRET=your_app_secret_here
FEISHU_APP_TOKEN=your_app_token_here

# 可选配置
FEISHU_TABLE_ID=                    # 留空会自动创建
DATA_DIR=data/xhs/                  # 数据文件目录
FEISHU_BATCH_SIZE=500              # 批量上传数量
```

### 4. 验证设置

```bash
# 运行验证脚本
python validate_feishu_setup.py

# 创建数据表
python sync_to_feishu.py --setup
```

## 📖 使用指南

### 基础使用

```bash
# 同步单个文件
python sync_to_feishu.py --file data/xhs/notes.csv
python sync_to_feishu.py --file data/xhs/data.json

# 同步整个目录
python sync_to_feishu.py --dir data/xhs/

# 指定文件格式
python sync_to_feishu.py --dir data/xhs/ --pattern "*.csv"
```

### 自动监控模式

```bash
# 每5分钟检查一次新数据
python sync_to_feishu.py --dir data/xhs/ --auto --interval 300

# 使用配置文件中的默认设置
python sync_to_feishu.py
```

### 管理功能

```bash
# 显示配置信息
python sync_to_feishu.py --config

# 检查同步状态
python sync_to_feishu.py --status

# 显示使用示例
python sync_to_feishu.py --examples
```

## 🔧 核心模块说明

### FeishuConfig (配置管理)
```python
from feishu_sync import FeishuConfig

config = FeishuConfig()
config.validate()  # 验证配置
config.print_config_summary()  # 显示配置摘要
```

**主要配置项：**
- `APP_ID`: 飞书应用ID
- `APP_SECRET`: 飞书应用密钥  
- `APP_TOKEN`: 多维表格Token
- `BATCH_SIZE`: 批量上传大小（默认500）
- `AUTO_SYNC`: 自动同步开关

### XHSDataFormatter (数据格式化)
```python
from feishu_sync import XHSDataFormatter

formatter = XHSDataFormatter()

# 加载数据
data = formatter.load_from_csv("data.csv")
data = formatter.load_from_json("data.json")

# 格式化数据
records = formatter.format_batch_records(data)
```

**功能特性：**
- 智能类型转换（时间戳、数字）
- 文本清理和长度限制
- 标签解析（支持多种分隔符）
- 热度评分计算
- 数据去重处理

### FeishuSyncManager (同步管理)
```python
from feishu_sync import FeishuSyncManager, FeishuConfig

config = FeishuConfig()
manager = FeishuSyncManager(config)

# 同步数据
result = manager.sync_from_csv("data.csv")
result = manager.sync_directory("data/xhs/")

# 获取状态
status = manager.get_sync_status()
```

**核心功能：**
- 基于飞书官方SDK
- 批量数据上传
- 自动表格创建
- 错误处理和重试
- 实时状态监控

## 📊 数据表结构

| 字段名称 | 类型 | 说明 | 数据源 |
|---------|------|------|--------|
| 笔记ID | 单行文本 | 唯一标识 | note_id |
| 标题 | 单行文本 | 笔记标题 | title |
| 内容摘要 | 多行文本 | 描述内容 | desc |
| 类型 | 单选 | 图文/视频 | type |
| 发布时间 | 日期时间 | 原发布时间 | time |
| 用户昵称 | 单行文本 | 发布者昵称 | nickname |
| 点赞数 | 数字 | 互动数据 | liked_count |
| 收藏数 | 数字 | 互动数据 | collected_count |
| 评论数 | 数字 | 互动数据 | comment_count |
| 分享数 | 数字 | 互动数据 | share_count |
| 地理位置 | 单行文本 | IP定位 | ip_location |
| 标签 | 多选 | 内容标签 | tag_list |
| 搜索关键词 | 单行文本 | 爬取关键词 | source_keyword |
| 笔记链接 | 超链接 | 原文链接 | note_url |
| 热度评分 | 数字 | 综合热度 | 公式计算 |
| 爬取时间 | 日期时间 | 采集时间 | last_modify_ts |

### 热度评分算法
```
热度评分 = (点赞数×1.0 + 收藏数×2.0 + 评论数×3.0 + 分享数×4.0) / 10
```

## 🔄 数据流程

```
小红书数据 (CSV/JSON)
    ↓
数据加载与验证
    ↓
格式化转换 (XHSDataFormatter)
    ↓
去重处理
    ↓
批量上传 (FeishuSyncManager)
    ↓
飞书多维表格
```

## ⚙️ 高级配置

### 自定义数据处理
```python
from feishu_sync import XHSDataFormatter

class CustomFormatter(XHSDataFormatter):
    def _calculate_heat_score(self, data):
        # 自定义热度算法
        return super()._calculate_heat_score(data) * 1.5
```

### 批量处理优化
```bash
# 环境变量配置
FEISHU_BATCH_SIZE=200              # 减小批量大小
FEISHU_RATE_LIMIT_DELAY=0.2        # 增加请求间隔
FEISHU_RETRY_COUNT=5               # 增加重试次数
```

### 监控和日志
```bash
# 日志配置
LOG_LEVEL=DEBUG                    # 详细日志
LOG_FILE=custom_sync.log          # 自定义日志文件

# 查看日志
tail -f feishu_sync.log
grep ERROR feishu_sync.log
```

## 🚨 注意事项

### API限制
- 飞书API单次最多上传500条记录
- 建议设置合理的请求间隔避免限流
- 访问令牌有效期2小时，会自动刷新

### 数据质量
- CSV文件需使用UTF-8编码
- 时间戳支持秒级和毫秒级
- 文本字段有长度限制（标题100字符，描述500字符）

### 安全建议
- 敏感配置信息存放在 `.env` 文件中
- 不要将 `.env` 文件提交到代码仓库
- 定期轮换应用密钥

## 🔍 故障排查

### 常见问题

1. **导入模块失败**
   ```bash
   # 安装缺失依赖
   pip install lark-oapi pandas python-dotenv schedule
   ```

2. **认证失败**
   ```bash
   # 检查配置
   python sync_to_feishu.py --config
   
   # 验证设置
   python validate_feishu_setup.py
   ```

3. **上传失败**
   ```bash
   # 查看详细日志
   grep ERROR feishu_sync.log
   
   # 检查数据格式
   python sync_to_feishu.py --file sample.csv --config
   ```

### 日志分析
```bash
# 查看成功率
grep "同步完成" feishu_sync.log | tail -10

# 查看错误详情
grep -A 5 "ERROR" feishu_sync.log

# 查看API调用情况
grep "批次" feishu_sync.log
```

## 📚 扩展开发

### 自定义数据源
```python
from feishu_sync import FeishuSyncManager

# 自定义数据加载
def load_custom_data():
    # 你的数据加载逻辑
    return data_list

manager = FeishuSyncManager()
result = manager.sync_data(load_custom_data())
```

### 集成到爬虫流程
```python
# 在爬虫完成后自动同步
if config.ENABLE_FEISHU_AUTO_SYNC:
    from feishu_sync import FeishuSyncManager
    
    sync_manager = FeishuSyncManager()
    sync_manager.sync_from_csv("latest_data.csv")
```

## 🔗 相关资源

- [飞书开放平台](https://open.feishu.cn/app)
- [飞书多维表格API文档](https://open.feishu.cn/document/server-docs/docs/bitable-v1/app-table-record/create)
- [飞书Python SDK文档](https://open.feishu.cn/document/uAjLw4CM/ukTMukTMukTM/server-side-sdk/python--sdk/preparations-before-development)
- [详细开发说明](./飞书开发说明.md)
- [项目待办清单](./todo.md)

## 📄 许可证

本项目遵循 MediaCrawler 项目的许可证条款。

---

*最后更新：2025年9月5日*  
*版本：v1.0.0*