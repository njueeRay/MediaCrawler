# 全体会议纪要 — 文档重整复盘 & 启动验收前置审查

| 字段 | 内容 |
|------|------|
| **会议日期** | 2026-02-27 |
| **类型** | 复盘（里程碑后质量审查） |
| **主持** | Brain（战略） |
| **参与者** | Brain、PM、Dev |
| **议题** | 1) 文档重整成果复盘；2) 启动指引完整性核查；3) WebUI + 后端验收启动授权 |
| **背景** | 上一次全体会议（`2026-02-27-docs-restructure-workshop.md`）完成了文档库全体重整，本次为里程碑后质量闸门，确保文档知识完整留存并授权启动验收测试 |

---

## 一、文档重整成果审计

### 1.1 已完成项核查（Brain 主持，Dev 确认）

| 验收项 | 状态 | 备注 |
|--------|------|------|
| `docs/guide/` 8个用户指南文件 | ✅ 就绪 | login/proxy/storage/export/cdp/faq/automation/quickstart |
| `docs/reference/` 知识库迁移 | ✅ 就绪 | 01~07 + README + upstream-readme |
| `docs/dev/webui/` 设计文档 | ✅ 就绪 | 01~05 + DEVLOG + design-decisions |
| `docs/ops/` 团队运营文档 | ✅ 就绪 | team-playbook/agent-workflow/copilot_command/feishu-backlog/donations |
| `docs/feishu/` 飞书集成文档 | ✅ 就绪 | README + dev-notes + Python_SDK（保留） |
| `README.md` 功能状态更新 | ✅ 就绪 | WebUI/调度/飞书全部 ✅；含 uvicorn 启动命令 |
| `docs/index.md` 导航链接 | ✅ 就绪 | 指向 guide/reference/feishu 新路径 |

### 1.2 遗留 P1 项（下次 Sprint 处理）

| 文件 | 内容 | 原因 |
|------|------|------|
| `.vitepress/` 侧栏配置 | 同步 guide/reference/ops/feishu 新路径 | 当前无 `.vitepress/` 目录，文档站未启用 |
| `docs/guide/automation.md` | 内容完整性验证 | 从 `dev/自动化运行任务.md` 迁移，内容待人工核查 |
| `docs/feishu/README.md` | 整理为功能入口，去冗余 | 当前内容仍较混杂 |

---

## 二、启动指引完整性核查

### 2.1 技术配置确认（Dev 核查结论）

```
webui-src/vite.config.ts 确认：
  - 开发服务器端口：3000
  - /api 代理目标：http://localhost:8080（changeOrigin: true, ws: true）
  - 生产构建输出：../api/webui（FastAPI 静态托管目录）

api/main.py 确认：
  - 健康检查端点：GET /api/health → {"status": "ok"}
  - 静态文件服务：已挂载 api/webui/ 目录
```

### 2.2 完整启动命令（单一权威来源）

> 详细说明见 [docs/guide/quickstart.md](../guide/quickstart.md#启动-webui后端-api--前端界面)

**生产模式（推荐）：**
```shell
# Step 1：构建前端
cd webui-src
npm install
npm run build
cd ..

# Step 2：启动后端（托管前端静态文件）
uv run uvicorn api.main:app --host 0.0.0.0 --port 8080

# 验证：http://localhost:8080
```

**开发模式（前后端分离，热重载）：**
```shell
# 终端 1
uv run uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload

# 终端 2
cd webui-src && npm run dev

# 验证：http://localhost:3000
```

---

## 三、规范化协作制度（Brain 提案，全体确认）

### 3.1 会议纪要规范

| 规则 | 说明 |
|------|------|
| **即时归档** | 每次会议结束后会议纪要在同一次提交中落地 |
| **命名规范** | `YYYY-MM-DD-{主题关键词}.md`，存放于 `docs/ops/meetings/` |
| **必填字段** | 日期、类型、主持、参与者、议题、背景（见本文件头部表格） |
| **决议格式** | 每项决议需明确：是/否/待定 + 负责人 + 截止时间 |

### 3.2 文档更新规范

| 规则 | 说明 |
|------|------|
| **P0 变更必须更新文档** | 新功能上线、架构调整、启动命令变更，当次提交必须同步更新对应文档 |
| **单一权威来源** | 每个知识域只有一份文档，跨引用用链接，禁止复制粘贴 |
| **DEVLOG 只追加** | `docs/dev/webui/DEVLOG.md` 记录每次里程碑，不删改历史条目 |

### 3.3 提交规范

| 类型前缀 | 适用场景 |
|---------|---------|
| `feat(module):` | 新功能实现 |
| `fix(module):` | Bug 修复 |
| `docs:` | 纯文档变更 |
| `refactor(module):` | 代码重构（不改变行为） |
| `chore:` | 工具/配置/依赖变更 |

> 完整规范见 [docs/ops/team-playbook.md](../ops/team-playbook.md)

---

## 四、会议决议

| # | 决议 | 状态 | 负责人 |
|---|------|------|--------|
| 1 | 文档重整成果验收通过 | ✅ 通过 | Brain |
| 2 | 启动指引文档（quickstart.md / README.md）内容完整，可作为用户验收依据 | ✅ 通过 | Dev |
| 3 | **授权进入验收阶段**：启动 WebUI + 后端，由用户测试验收 | ✅ 授权 | PM |
| 4 | VitePress 侧栏配置更新推迟至下次 Sprint（当前无 .vitepress/ 目录，影响有限） | ✅ 延期 | Dev |
| 5 | 规范化协作制度（3.1~3.3节）纳入 team-playbook | ⏳ 待写入 | Dev |

---

## 五、下一步行动清单

| 优先级 | 行动 | 状态 |
|--------|------|------|
| **P0** | 启动后端：`uv run uvicorn api.main:app --host 0.0.0.0 --port 8080` | 本次执行 |
| **P0** | 构建并启动前端：`cd webui-src && npm install && npm run build && cd ..` | 本次执行 |
| **P0** | 验证 `http://localhost:8080` 可访问 WebUI | 用户验收 |
| **P1** | 将规范化协作制度（§3）写入 `docs/ops/team-playbook.md` | 下次 Sprint |
| **P1** | 验证 `docs/guide/automation.md` 内容完整性 | 下次 Sprint |

---

*会议纪要由 GitHub Copilot 记录 | Brain 主持 | 2026-02-27*
