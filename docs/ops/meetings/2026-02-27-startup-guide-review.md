# 全体会议纪要 — 文档复盘 & 启动指引补全

| 字段 | 内容 |
|------|------|
| **会议日期** | 2026-02-27 |
| **类型** | 文档复盘 + P0 紧急修复 |
| **主持** | Brain |
| **参与者** | Brain（战略主持）、PM（排期）、Dev（技术确认） |
| **议题** | 上次重组会议后文档缺口盘点；WebUI 启动指引完全缺失修复；docs/index.md 断链修复 |

---

## 一、审计发现

| 问题 | 严重度 | 文件 |
|------|--------|------|
| `docs/index.md` 顶部 3 条导航链接均指向已删除路径 | ❌ P0 | `docs/index.md` |
| WebUI 前端启动方式（`npm run dev`）全库无记录 | ❌ P0 | 全局缺失 |
| `docs/guide/quickstart.md` 只覆盖爬虫，自研模块全无 | ❌ P0 | `docs/guide/quickstart.md` |
| README.md WebUI 章节无前端启动步骤，无联调说明 | ⚠️ P0 | `README.md` |
| `docs/guide/automation.md` 内容未验证 | P1 | 下次 Sprint |

---

## 二、本次执行的变更

### 变更 1：`docs/index.md` — 导航链接修正

| 旧链接 | 新链接 | 原因 |
|--------|--------|------|
| `项目架构文档.md` | `reference/01-项目架构总览.md` | 文件已迁移 |
| `知识库/README.md` | `reference/README.md` | 目录已重命名 |
| （新增）快速开始 | `guide/quickstart.md` | 首位导航指向启动指引 |

### 变更 2：`docs/guide/quickstart.md` — 新增 WebUI 启动章节

末尾追加了三个新章节：
- **启动 WebUI（后端 API + 前端界面）** — 生产模式 + 开发模式双路径
- 端口说明（8080 生产 / 3000 开发模式）
- 后端 API 健康检查验证命令
- **启动定时调度系统** — `uv run auto_scheduler.py`

### 变更 3：`README.md` — WebUI 章节补充前端步骤

在 `### 3. 启动 WebUI 控制台` 节内：
- 新增 `cd webui-src && npm install && npm run build` 前置步骤
- 新增开发模式双终端启动说明
- 新增指向 `docs/guide/quickstart.md` 的详细文档链接

---

## 三、精确启动命令（Dev 确认版）

### 环境初始化（一次性）
```shell
uv sync
uv run playwright install
cd webui-src && npm install && cd ..
```

### 生产启动
```shell
cd webui-src && npm run build && cd ..
uv run uvicorn api.main:app --host 0.0.0.0 --port 8080
# 访问：http://localhost:8080
```

### 开发模式（双终端）
```shell
# 终端 1
uv run uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
# 终端 2
cd webui-src && npm run dev
# 访问：http://localhost:3000
```

### 定时调度系统
```shell
uv run auto_scheduler.py
```

### 爬虫
```shell
uv run main.py --platform xhs --lt qrcode --type search
```

---

## 四、遗留 P1 任务（下次 Sprint 处理）

| 任务 | 文件 | 说明 |
|------|------|------|
| 确认 `automation.md` 内容完整性 | `docs/guide/automation.md` | 检查调度器配置说明是否存在 |
| VitePress `.vitepress/` 侧栏配置同步 | `.vitepress/config.js` | 上次会议已决议延后处理 |
| `docs/feishu/README.md` 整理 | `docs/feishu/README.md` | P1：整理为干净的功能入口 |

---

## 五、DoD Checklist

- [x] `docs/index.md` 断链已修复
- [x] `docs/guide/quickstart.md` 包含 WebUI 完整启动路径
- [x] `README.md` WebUI 章节包含前端启动步骤
- [x] 本次会议纪要已归档
- [ ] `.vitepress/` 侧栏配置（P1，下次 Sprint）

---

*会议纪要由 GitHub Copilot (Brain) 记录 | 2026-02-27*
