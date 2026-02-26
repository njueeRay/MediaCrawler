# 数据导出使用指南

本文档涵盖两种数据导出方式：**Excel 格式导出**和**词云图生成**。

---

## 一、Excel 导出

### 功能概述

MediaCrawler 支持将爬取数据导出为格式化的 Excel 文件（`.xlsx`），包含内容、评论、创作者三个独立 Sheet。

**主要特性：**

- **多 Sheet 工作簿**：内容 / 评论 / 创作者分表存储
- **专业格式**：蓝色表头、自动列宽、单元格边框、文本换行
- **智能导出**：空 Sheet 自动移除
- **有序存储**：按时间戳存至 `data/{platform}/` 目录

### 安装依赖

```bash
# 使用 uv（推荐）
uv sync

# 或 pip
pip install openpyxl
```

### 基础使用

**1. 在 `config/base_config.py` 中配置存储格式：**

```python
SAVE_DATA_OPTION = "excel"
```

**2. 运行爬虫：**

```bash
uv run main.py --platform xhs --lt qrcode --type search
uv run main.py --platform dy  --lt qrcode --type search
uv run main.py --platform bili --lt qrcode --type search
```

**3. 文件位置：**`data/{platform}/{platform}_{type}_{timestamp}.xlsx`

### 命令行示例

```bash
# 关键词搜索并导出
uv run main.py --platform xhs --lt qrcode --type search --save_data_option excel

# 指定帖子爬取
uv run main.py --platform xhs --lt qrcode --type detail --save_data_option excel

# 创作者主页爬取
uv run main.py --platform xhs --lt qrcode --type creator --save_data_option excel
```

### Excel 文件结构

#### Contents Sheet（内容）

| 字段 | 说明 |
|------|------|
| `note_id` | 帖子唯一标识 |
| `title` | 标题 |
| `desc` | 描述 |
| `user_id` / `nickname` | 作者信息 |
| `liked_count` / `comment_count` / `share_count` | 互动数据 |
| `ip_location` | IP 地理位置 |
| `image_list` / `tag_list` | 图片/标签（逗号分隔） |
| `note_url` | 原文链接 |

#### Comments Sheet（评论）

| 字段 | 说明 |
|------|------|
| `comment_id` | 评论唯一标识 |
| `note_id` | 关联帖子 ID |
| `content` | 评论内容 |
| `nickname` / `user_id` | 评论者信息 |
| `like_count` | 点赞数 |
| `create_time` | 评论时间 |
| `sub_comment_count` | 回复数 |

#### Creators Sheet（创作者）

| 字段 | 说明 |
|------|------|
| `user_id` | 用户唯一标识 |
| `nickname` | 昵称 |
| `fans` / `follows` | 粉丝/关注数 |
| `interaction` | 总互动量 |
| `desc` | 简介 |

### 与其他格式对比

| 维度 | Excel | CSV | JSON | DB |
|------|-------|-----|------|----|
| 多表存储 | ✅ | ❌ | ❌ | ✅ |
| 人类可读 | ✅ | ✅ | 一般 | ❌ |
| 无编码问题 | ✅ | 一般 | ✅ | ✅ |
| 需额外安装 | openpyxl | ❌ | ❌ | DB驱动 |
| 适合场景 | 分发/分析 | 数据管道 | API/程序 | 大数据量 |

### 高级用法

**合并多个 Excel 文件（Python）：**

```python
import pandas as pd
df1 = pd.read_excel('file1.xlsx', sheet_name='Contents')
df2 = pd.read_excel('file2.xlsx', sheet_name='Contents')
combined = pd.concat([df1, df2])
combined.to_excel('combined.xlsx', index=False)
```

**程序化调用：**

```python
from store.excel_store_base import ExcelStoreBase

store = ExcelStoreBase(platform="xhs", crawler_type="search")
await store.store_content({"note_id": "123", "title": "Test", "liked_count": 100})
store.flush()
```

### 故障排查

| 问题 | 解决方法 |
|------|---------|
| `openpyxl not installed` | `uv add openpyxl` |
| Excel 文件未生成 | 检查 `SAVE_DATA_OPTION = "excel"` 是否设置，确认爬取有数据 |
| 空 Excel 文件 | 检查关键词/ID是否有效，检查登录状态，检查IP/频率限制 |

> 大数据量（>10,000 行）建议改用数据库存储以获得更好性能。

---

## 二、词云图生成

> **前提条件**：词云图目前仅在 `SAVE_DATA_OPTION = "json"` 时生成，且需开启评论爬取。

### 配置项说明

在 `config/base_config.py` 中修改以下配置：

```python
# 1. 存储格式必须为 json
SAVE_DATA_OPTION = "json"

# 2. 开启评论爬取
ENABLE_GET_COMMENTS = True

# 3. 开启词云图功能
ENABLE_GET_WORDCLOUD = True

# 4. 自定义词语分组（可选）
#    格式：xx:yy  → 将 xx 识别为整体词，分入 yy 组
CUSTOM_WORDS = {
    '零几': '年份',
    '高频词': '专业术语',
}

# 5. 停用词文件路径
STOP_WORDS_FILE = "./docs/static/hit_stopwords.txt"

# 6. 中文字体文件路径（默认宋体）
FONT_PATH = "./docs/static/STZHONGS.TTF"
```

**配置说明：**

- `CUSTOM_WORDS`：用于将特定词语强制识别为整体，避免被分词拆散。
- `STOP_WORDS_FILE`：停用词表，每行一个词。如需添加禁用词，直接编辑 `docs/static/hit_stopwords.txt`。
- `FONT_PATH`：词云图使用的中文字体，如需更换字体，替换文件路径即可。

### 生成结果位置

词云图输出在 `data/words/` 目录下：

- `*.json`：词频统计文件
- `*.png`：词云图图片

原始评论内容存于 `data/json/` 目录。

![词云图输出示例](https://rosyrain.oss-cn-hangzhou.aliyuncs.com/img2/202406272049662.png)
