# Sprint #002 规划 + 全体复盘会议纪要

**日期：** 2026-02-26（第二次团队会议，追加全体复盘）  
**参会成员：** Brain (主持) / PM / Researcher / Code-Reviewer  
**会议类型：** Sprint 规划 + 技术审查 + 部署复盘  
**关联文档：** [design-decisions.md](../design-decisions.md) | [CHANGELOG.md](../../CHANGELOG.md)

---

## 一、会议议程

1. **战略问题确认：** WebUI 调度 vs 容器化部署的优先级
2. **技术债务审查：** Code-Reviewer 深度代码扫描结果
3. **部署方案确定：** 今晚如何将服务跑在 Linux 服务器上
4. **Sprint #002 范围划定**

---

## 二、战略问题结论

> 用户问：「WebUI 的调度放在容器化部署的前面还是后面？」

**结论：WebUI APScheduler 调度功能已完整实现，无需再次开发。**  
今晚目标直接推进到**生产部署（systemd）**，Docker 容器化归入 Sprint #003。

顺序为：
```
[当前] WebUI 调度已建成 → [今晚] systemd 部署 → [Sprint #003] Docker 容器化
```

**PM 推荐方案：** systemd over Docker for Sprint #002
- systemd：约 1.5 小时完成，无需学习曲线，日志由 journald 统一管理
- Docker：约 4 小时，需处理 Playwright + shm_size + 卷挂载，留给 Sprint #003

---

## 三、Code-Reviewer 审查报告摘要

### P0 阻断项（上线前必须修复）

| ID | 位置 | 问题描述 | 修复状态 |
|----|------|---------|---------|
| P0-1 | `api/main.py` `webui_startup()` | APScheduler 重启后不恢复任务：DB 中的 ScheduledTask 记录存在，但未向 APScheduler 重注册，服务重启后所有定时任务静默失效 | ✅ 已修复 |
| P0-2 | `config/base_config.py` | `SAVE_DATA_OPTION` 默认值 `csv` 导致 `get_session()` 返回 `None`，WebUI 订阅/调度/飞书同步功能全部静默失败 | ⚙️ 配置修复（设置 env） |
| P0-3 | `api/main.py` CORSMiddleware | `allow_origins` 硬编码 localhost，生产环境 WebUI 完全无法访问 | ✅ 已修复 |

### P1 高优先级（本 Sprint 内处理）

| ID | 位置 | 问题描述 | 修复状态 |
|----|------|---------|---------|
| P1-1 | `scheduler_service.py` ~line 354 | `subscription_combo` 循环中检测到爬虫正在运行时执行 `raise RuntimeError`，导致整批订阅任务失败（应为 `continue` 跳过） | ✅ 已修复 |
| P1-2 | `api/main.py` | `@app.on_event("startup")` 已在 FastAPI 0.110+ 废弃，应迁移到 `lifespan` | ⏳ Sprint #002 后期 |
| P1-3 | `api/main.py` `/api/config/platforms` | 微信平台缺失于平台列表，WebUI 订阅页无法选择微信 | ✅ 已修复 |

### 其他发现
- `auto_scheduler.py` 行 19 导入 `feishu_sync_simple` 不存在文件，进程启动即崩溃 → **已废弃**
- `_wait_crawler_done`：`asyncio.sleep(1)` 在状态检查前执行（细节问题，不影响正确性）

---

## 四、Researcher 调查结论

1. **微信模块不需要 Playwright**（纯 HTTP 消费 wechat-article-exporter），今晚部署无需安装浏览器依赖
2. **Linux 服务器必须设置的 env：**
   - `HEADLESS=true`（无显示器）
   - `ENABLE_CDP_MODE=false`（无 GUI 环境）
   - `SAVE_DATA_OPTION=sqlite`（WebUI 功能前提）
3. **Docker 镜像方案（Sprint #003 备用）：** `mcr.microsoft.com/playwright/python:v1.45.0-jammy` + `shm_size: '1gb'`

---

## 五、Sprint #002 计划（PM 制定）

### 目标
> 今晚：服务跑在 Linux 服务器，根据订阅列表定时爬取，按规范同步飞书。

### 任务清单

#### 阻断修复（今日完成）
- [x] P0-1：`webui_startup()` 添加 APScheduler 任务恢复循环
- [x] P0-3：CORS `allow_origins` 改为读取 `ALLOWED_ORIGINS` env var
- [x] P1-1：`subscription_combo` 循环 `raise` → `continue`
- [x] P1-3：`/api/config/platforms` 添加微信平台
- [x] 废弃 `auto_scheduler.py`（加 RuntimeError 保护 + 说明注释）
- [x] 更新 `.env.example`：补充 `ALLOWED_ORIGINS`、服务器部署警告
- [x] 创建 `deploy/mediacrawler.service`（systemd 模板）

#### P0-2 操作项（服务器上执行）
- [ ] 服务器 `.env` 设置 `SAVE_DATA_OPTION=sqlite`（无代码修改）

#### Sprint #002 后期
- [ ] 迁移 `@app.on_event` → `lifespan`（P1-2，FastAPI 废弃警告）
- [ ] 依赖管理统一：`requirements.txt` 从 `pyproject.toml` 生成冻结（D-006）
- [ ] 安全：WECHAT_AUTH_KEY 轮换流程文档化

### 不在本 Sprint 范围
- Docker 容器化（→ Sprint #003）
- CI/CD 流水线（→ Sprint #003）
- 前端 WebUI 功能开发

---

## 六、今晚部署检查清单

```bash
# 1. 代码同步到服务器
git pull origin main

# 2. 安装依赖
uv sync

# 3. 创建并编辑 .env
cp .env.example .env
# 必须修改的值:
#   SAVE_DATA_OPTION=sqlite
#   FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_BITABLE_APP_TOKEN
#   WECHAT_API_BASE_URL / WECHAT_AUTH_KEY
#   HEADLESS=true
#   ENABLE_CDP_MODE=false
#   ALLOWED_ORIGINS=http://<your-server-ip>:8080

# 4. 安装 systemd 服务（修改service文件中的路径）
sudo cp deploy/mediacrawler.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mediacrawler
sudo systemctl start mediacrawler
sudo systemctl status mediacrawler

# 5. 验证
curl http://localhost:8080/api/health
# 预期: {"status": "ok"}
```

---

## 七、业务工作流（用户确认的标准流程）

```
订阅列表
   ↓ (APScheduler 定时触发)
subscription_combo 任务
   ↓ (串行遍历订阅，逐个启动爬虫)
数据写入 SQLite/DB
   ↓ (同步步骤)
飞书「表 1」（原始数据，FeishuSyncManager）
   ↓ (人工在飞书进行数据清洗/编辑 + AI 结构化)
飞书「表 1」JSON 列（AI 输出结果）
   ↓ (json_column_sync.py 定时拉取)
飞书「表 2」（结构化输出，供下游消费）
```

CLI 一键执行（绕过调度器）：
```bash
bash scripts/wechat_feishu_workflow.sh
```

---

## 八、已决定事项（新增设计决策）

- **D-009：** Sprint #002 使用 systemd 部署，Sprint #003 引入 Docker（详见 design-decisions.md）
- **D-010：** `auto_scheduler.py` 正式废弃，以 WebUI APScheduler 为唯一调度入口（详见 design-decisions.md）

---

## 九、会议结论

| 决议 | 结果 |
|------|------|
| 调度优先级 | WebUI APScheduler 已建成，直接进入部署阶段 |
| 今晚部署方案 | systemd（uv run uvicorn），单 worker |
| 容器化时间 | Sprint #003，与本次无关 |
| 代码审查结论 | 3 P0 + 2 P1 发现，Sprint #002 内全部修复 |

**下次会议触发条件：** 服务器部署完成 + 第一条订阅任务成功执行。

---

## 十、全体复盘（第二轮 PM + Researcher 评估）

> 本节为追加复盘，在 Sprint #002 代码修复完成后召开。

### 系统状态地图

| 层级 | 状态 | 细节 |
|------|------|------|
| **代码层** | ✅ 就绪 | P0-1/P0-3/P1-1/P1-3 已修复，systemd 模板已建 |
| **依赖层** | ✅ 已修复 | `apscheduler` + `lark-oapi` 已加入 pyproject.toml（本轮复盘新发现） |
| **配置层** | ⚙️ 待用户操作 | `.env.example` 模板就绪，服务器 `.env` 需手动填写关键变量 |
| **服务器层** | ⏳ 未启动 | 代码未同步，systemd 未安装，WebUI 未验证 |
| **业务流程层** | ⏳ 未验证 | 端到端从未在生产环境完整执行过 |

### Researcher 新发现（复盘轮次新增）

#### 🔴 P0-4（新发现，已修复）：`apscheduler` + `lark-oapi` 不在 pyproject.toml

`uv sync` 仅读取 `pyproject.toml`，而 `apscheduler` 只在 `requirements.txt`（第53行），`lark-oapi` 在两个文件中都缺失。

**后果：**
- `uv sync` 后部署，APScheduler 导入失败，调度器静默禁用（代码做了 `try/except ImportError`，不报错）
- 所有飞书同步功能启动时报 `ModuleNotFoundError`

**修复：** 已将两个依赖加入 `pyproject.toml`：
```toml
"apscheduler>=3.10.0",  # 实际安装版本 3.11.2
"lark-oapi>=1.5.0",     # 实际安装版本 1.5.2
```

#### 🟡 P1-4（设计缺口）：WebUI 调度路径缺少「表2同步」配置入口

`subscription_combo` 任务执行飞书同步时，调用 `feishu_service.start_sync()`，该路径使用 `FEISHU_TABLE_ID`（表1），**没有 `TABLE2_ID` 和 `JSON_COLUMNS` 的配置入口**。

**当前结论：**
- 表1同步（原始数据写入）：✅ WebUI 路径完整
- 表2同步（JSON列解析）：⚠️ 目前只能用 CLI 脚本路径（`scripts/wechat_feishu_workflow.sh`）

**今晚部署策略：**
```
WebUI APScheduler → subscription_crawl（仅爬取 + 表1同步）
CLI 脚本（cron 或手动）→ 表2 JSON 列解析同步
```

#### 🟡 P1-5：飞书 env 双命名割裂

| 使用路径 | 变量名 | 含义 |
|---------|--------|------|
| WebUI 调度 | `FEISHU_TABLE_ID` | 表1 ID |
| CLI 脚本 | `TABLE1_ID` | 表1 ID（相同值，不同名） |
| CLI 脚本 | `TABLE2_ID` | 表2 ID |

**服务器 `.env` 必须同时配置两个名称（值相同）：**
```env
FEISHU_TABLE_ID=<表1的table_id>
TABLE1_ID=<表1的table_id>           # 与上同值
TABLE2_ID=<表2的table_id>
JSON_COLUMNS=<需解析的JSON列名>
```

#### 🟡 P1-6：DB 中无 Subscription 记录 → subscription_combo 空转

首次部署时 SQLite DB 为空，`subscription_combo` 任务触发后 `subscription_total=0` 静默完成。

**首次部署最快路径：** 直接 SQL 批量插入：
```sql
INSERT INTO webui_subscription
  (platform, creator_id, creator_name, is_active, auto_crawl, created_at, updated_at)
VALUES
  ('wechat', '<fakeid>', '<公众号名称>', 1, 1, datetime('now'), datetime('now'));
```
或通过 WebUI `/api/subscriptions` API 逐条创建。

#### ⚠️ 注意：WECHAT_AUTH_KEY 4 天有效期

- 默认值来自 `config/wechat_config.py` 硬编码（公网实例），约 4 天过期
- **服务器 `.env` 必须显式设置 `WECHAT_AUTH_KEY`**，不能依赖默认值
- 后续需要建立定期轮换机制（cron + 企业微信告警）

---

### 最终行动路径（按优先级）

#### 【用户操作项 — 今晚部署】

```
步骤 1  git pull + uv sync
         ↓ 确认输出中有 "apscheduler" 和 "lark-oapi"

步骤 2  cp .env.example .env，填写以下变量（最小集）：
         SAVE_DATA_OPTION=sqlite          ← 遗漏 = 全部功能静默失败
         HEADLESS=true
         ENABLE_CDP_MODE=false
         ALLOWED_ORIGINS=http://<服务器IP>:8080
         FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_BITABLE_APP_TOKEN
         FEISHU_TABLE_ID=<表1 table_id>
         TABLE1_ID=<表1 table_id>         ← 与上同值
         TABLE2_ID=<表2 table_id>
         JSON_COLUMNS=<列名>
         WECHAT_API_BASE_URL / WECHAT_AUTH_KEY

步骤 3  修改 deploy/mediacrawler.service：
         User=<实际用户名>
         WorkingDirectory=<项目路径>
         EnvironmentFile=<.env 绝对路径>

步骤 4  sudo cp deploy/mediacrawler.service /etc/systemd/system/
         sudo systemctl daemon-reload
         sudo systemctl enable --now mediacrawler
         sudo systemctl status mediacrawler

步骤 5  验证启动
         curl http://localhost:8080/api/health
         journalctl -u mediacrawler | grep "APScheduler started"
         journalctl -u mediacrawler | grep "Seeded\|Recovered"

步骤 6  WebUI 创建订阅 + ScheduledTask（或 SQL 批量插入）
         建议任务类型: subscription_combo（爬取+表1同步一键）

步骤 7  手动触发一次任务，验证飞书表1有数据写入
         curl -X POST http://localhost:8080/api/scheduler/tasks/<id>/trigger

步骤 8（可选）配置 cron 定期运行 wechat_feishu_workflow.sh 完成表2同步
         0 3 * * * cd /opt/mediacrawler && bash scripts/wechat_feishu_workflow.sh
```

#### 【团队待办 — Sprint #002 收尾】

| 优先级 | 任务 | 备注 |
|--------|------|------|
| P1 | WebUI scheduler 增加 table2 配置入口（TABLE2_ID + JSON_COLUMNS） | 目前缺口，让 WebUI 路径完整 |
| P1 | `@app.on_event` → `lifespan` 迁移 | FastAPI 废弃警告 |
| P1 | WECHAT_AUTH_KEY 轮换机制文档化 + cron 模板 | 每 3 天 |
| P2 | `/api/subscriptions/batch` 批量创建 API | 减少首次部署手工操作 |

---

### 已知风险清单

| 🔴 最高 | `.env` 漏填 `SAVE_DATA_OPTION=sqlite` → WebUI 全系功能静默失败 |
|--------|---|
| 🔴 最高 | `WECHAT_AUTH_KEY` 过期 → 微信爬取 100% 失败（每 4 天检查一次） |
| 🟡 中 | DB 中无 Subscription 记录 → `subscription_combo` 空转不报错 |
| 🟡 中 | `ALLOWED_ORIGINS` 填写错误（尾部斜杠/协议不匹配）→ 跨域报错 |
| 🟡 中 | systemd 服务文件路径未修改 → 服务启动失败 |
| 🟢 低 | 表2同步依赖 CLI 脚本（非 WebUI 调度），需额外 cron |

**Sprint #002 DoD（完成标准）：** 端到端至少跑通一次，飞书「表1」有可见数据写入。

---

## 十、Sprint #002 全体复盘报告

> 会议时间：2026-02-26 会话尾声  
> 主持：PM  

---

### 系统状态地图

| 层级 | 状态 | 说明 |
|------|------|------|
| **代码层** | ✅ 就绪 | P0-1/P0-3/P1-1/P1-3 已修复，auto_scheduler.py 已废弃，systemd 模板已创建 |
| **配置层** | ⚙️ 待用户操作 | `.env.example` 模板已就绪，服务器 `.env` 需手动填写 4 个关键变量 |
| **服务器层** | ⏳ 未启动 | 代码未同步到服务器，systemd 服务未安装，WebUI 未验证 |
| **业务流程层** | ⏳ 未验证 | 端到端流程（爬取→SQLite→飞书）从未在生产环境完整跑过 |

#### 代码层细项

| 组件 | 状态 | 备注 |
|------|------|------|
| `api/main.py` APScheduler 任务恢复 | ✅ | P0-1 已修复 |
| `api/main.py` CORS 环境变量化 | ✅ | P0-3 已修复 |
| `scheduler_service.py` 订阅循环容错 | ✅ | P1-1 已修复 |
| `/api/config/platforms` 微信支持 | ✅ | P1-3 已修复 |
| `auto_scheduler.py` | ✅ | 已废弃，RuntimeError 封印 |
| `@app.on_event` lifespan 迁移 | ⏳ | P1-2，FastAPI deprecated 警告，不影响运行 |
| `requirements.txt` 与 `pyproject.toml` 统一 | ⏳ | D-006，Sprint #002 后期 |

---

### 行动路径

#### 【用户操作项】—— 今晚，按顺序执行

```
步骤 1：服务器代码同步
  git pull origin main

步骤 2：安装依赖
  uv sync

步骤 3：配置 .env（最关键一步，P0-2）
  cp .env.example .env
  # 必填 4 个变量：
  #   SAVE_DATA_OPTION=sqlite          ← 遗漏此项 = WebUI 完全失效
  #   ALLOWED_ORIGINS=http://<server-ip>:8080
  #   HEADLESS=true
  #   ENABLE_CDP_MODE=false
  # 必填飞书凭据：FEISHU_APP_ID / FEISHU_APP_SECRET / FEISHU_BITABLE_APP_TOKEN
  # 必填微信凭据：WECHAT_API_BASE_URL / WECHAT_AUTH_KEY

步骤 4：确认 wechat-article-exporter 状态
  # 微信爬虫是纯 HTTP 消费，依赖外部服务
  # 确认 wechat-article-exporter 是否已在服务器运行
  # 如未运行 → 先跳过微信订阅，仅验证其他平台

步骤 5：安装 systemd 服务
  # 修改 deploy/mediacrawler.service 中的 User / WorkingDirectory / ExecStart 路径
  sudo cp deploy/mediacrawler.service /etc/systemd/system/
  sudo systemctl daemon-reload
  sudo systemctl enable mediacrawler
  sudo systemctl start mediacrawler
  sudo systemctl status mediacrawler

步骤 6：服务健康验证
  curl http://localhost:8080/api/health
  # 预期：{"status": "ok"}
  # 如失败：journalctl -u mediacrawler -f 查看日志

步骤 7：WebUI 端到端验证
  # 在浏览器打开 http://<server-ip>:8080
  # 7a. 创建一个订阅（选择平台，填入 creator_id）
  # 7b. 创建 ScheduledTask，绑定该订阅，设置触发间隔
  # 7c. 手动触发一次任务，观察 WebSocket 日志
  # 7d. 确认 SQLite 中有数据写入
  # 7e. 确认飞书「表1」有新记录
```

#### 【团队待办】—— 代码层未完成项

| 优先级 | 任务 | 负责角色 | 触发条件 |
|--------|------|----------|----------|
| P1 | 迁移 `@app.on_event` → `lifespan` | dev | 服务器部署稳定后下一会话 |
| P1 | `requirements.txt` 从 `pyproject.toml` 冻结生成 | dev | Sprint #002 收尾前 |
| P2 | `WECHAT_AUTH_KEY` 轮换流程文档化 | brain/pm | Sprint #002 收尾前 |
| P3 | Docker 容器化 | dev | Sprint #003 |

---

### 风险点识别

| 风险 | 可能性 | 影响 | 预防措施 |
|------|--------|------|----------|
| **`.env` 忘记设 `SAVE_DATA_OPTION=sqlite`** | 🔴 高 | WebUI 全部功能静默失败，无报错提示 | 步骤 3 中特别标注；验证时检查 `/api/subscribe` 是否可写 |
| **`wechat-article-exporter` 未在服务器运行** | 🟡 中 | 微信订阅任务 100% 失败 | 步骤 4 先确认；若未跑则临时跳过微信，不影响其余平台验证 |
| **`ALLOWED_ORIGINS` 配置错误** | 🟡 中 | WebUI 跨域报错，浏览器无法访问 | 填写格式 `http://ip:port`，不带尾部斜杠；检查 Network 面板 CORS 响应头 |
| **systemd 服务文件路径未修改** | 🟡 中 | 服务启动失败 | 启动前 `cat /etc/systemd/system/mediacrawler.service` 确认路径正确 |
| **APScheduler 任务恢复后重复注册** | 🟢 低 | 同一任务被触发两次 | P0-1 修复时已加去重检查；查看日志确认无 `duplicate job` 报错 |
| **飞书 API 配额/Token 过期** | 🟢 低 | 同步步骤静默失败 | 首次手动触发后检查飞书表格是否有新数据写入 |

---

### Sprint #002 剩余目标优先级

```
P0（今晚，阻断部署）
  └─ 服务器 .env 正确填写（SAVE_DATA_OPTION=sqlite + 飞书/微信凭据）
  └─ systemd 服务安装并启动
  └─ 端到端流程验证（至少一条订阅成功执行 + 数据写入飞书）

P1（本 Sprint 收尾前）
  └─ 确认 wechat-article-exporter 状态（是否在服务器运行）
  └─ @app.on_event → lifespan 迁移
  └─ requirements.txt 与 pyproject.toml 统一

P2（Sprint #002 → #003 交界）
  └─ WECHAT_AUTH_KEY 轮换流程文档化
  └─ CHANGELOG [Unreleased] → 版本号（触发条件：端到端验证通过）
```

---

### DoD Checklist（Sprint #002 完成标准）

#### 代码质量
- [x] P0-1/P0-3/P1-1/P1-3 已修复且可运行
- [ ] P1-2 lifespan 迁移完成（不影响运行，但需在 Sprint 内完成）
- [ ] 无已知 broken lint/import 错误

#### 文档同步
- [x] CHANGELOG.md Sprint #002 区块已更新
- [x] docs/design-decisions.md D-009/D-010 已记录
- [x] copilot-instructions.md「当前迭代状态」已同步
- [x] 会议纪要已存档

#### 版本管理
- [ ] **端到端验证通过后**：CHANGELOG `[Unreleased]` → `[0.3.0]`（minor，含完整部署能力）
- [ ] Tag `v0.3.0` 打出，Release Notes 发布

#### 质量门禁
- [x] code-reviewer 已完成 P0/P1 审查
- [ ] 服务器部署验证通过（至少一次成功的 subscription_combo 执行）

**⚠️ Sprint #002 当前状态：代码层 ✅ 就绪 | 服务器层 ⏳ 待执行 | DoD 未完成**

---

### 下一次会议触发条件（更新）

> 服务器步骤 1-7 全部完成 + 至少一条订阅任务在飞书写入可见数据。  
> 届时召开 Sprint #002 收尾 + Sprint #003（Docker 容器化）规划会。
