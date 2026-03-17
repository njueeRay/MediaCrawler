# 全体会议纪要 — WebUI 验收第二轮 Bug + 部署规划

| 字段 | 内容 |
|------|------|
| **会议日期** | 2026-02-27 |
| **类型** | 验收复盘 + 热修复 + 部署规划 |
| **主持** | Brain |
| **参与者** | Brain（战略）、Dev（实现）、PM（排期）、Code-Reviewer（审计） |
| **议题** | ① 文档归档治理 ② 2个P0 Bug修复 ③ 全面功能复查 ④ Linux部署准备 |

---

## 一、用户验收反馈（3点）

### 反馈 1：文档归档混乱
上一轮将会议纪要错误创建到 `docs/dev/WebUI/meetings/`，违反统一归档原则。
- **处置**: 已移动到 `docs/meetings/`，删除空目录
- **铁律确立**: 所有会议纪要只存放 `docs/meetings/`，命名 `YYYY-MM-DD-<topic>.md`

### 反馈 2：两个 P0 功能 Bug

#### Bug A：任务调度「新建」状态残留
- **现象**: 编辑任务后取消 → 再点新建 → 弹窗标题变"编辑"，表单残留旧数据
- **根因**: `@click="showCreate = true"` 不重置 `editingTaskId` / `newTask` / `pipelineCfg`
- **修复**: 新建按钮改为 `openCreate()` 函数（重置全部表单状态），取消按钮改为 `cancelCreate()`（清空 editingTaskId）
- **文件**: `webui-src/src/views/TaskScheduler.vue`

#### Bug B：微信搜索 auth key 读取源不一致
- **现象**: 测试连接成功 → 搜索创作者报"认证无效"
- **根因 1**: 测试连接直接读 `.env` 文件，搜索读 Python config 模块（可能未热重载）
- **根因 2**: 测试连接 `except Exception: pass` 吞掉 auth 验证异常，产生假阳性
- **修复**:
  - 搜索改为优先从 `.env` 文件读取 auth_key（fallback config 模块）
  - `except Exception: pass` 改为记录 warning + 返回"auth 验证未完成"提示
  - 搜索时增加调试日志（auth_key 前6位 + base_url）
- **文件**: `api/services/subscription_service.py`, `api/routers/config.py`

### 反馈 3：自动化任务编排 + 远程部署准备
- **短期**: 本地端到端跑通多任务组合编排（cron → 采集 → 飞书同步 → JSON 解析）
- **中期**: Linux 服务器部署（Docker/systemd + 反向代理）
- **处置**: Docker 骨架已输出，待本地验证通过后正式部署

---

## 二、全面复查结果

对所有 WebUI 页面进行交互走查：

| 页面 | 状态残留问题 | 认证一致性 | 结论 |
|------|-------------|-----------|------|
| TaskScheduler | **Bug A**（已修复） | — | ✅ |
| Subscription | 新建弹窗无编辑模式，无风险 | — | ✅ |
| FieldMapping | 新建弹窗无编辑模式，无风险 | — | ✅ |
| ConfigManager | — | 微信测试连接假阳性（**Bug B 已修复**） | ✅ |
| DataBrowser | — | — | ✅ |
| FeishuSync | — | — | ✅ |
| Dashboard | — | — | ✅ |

**结论**: Bug A 的状态残留模式仅存在于 TaskScheduler（唯一使用 create/edit 共享弹窗的页面）。Bug B 的读取源不一致仅影响微信模块。无其他同类问题。

---

## 三、决策记录

| # | 决策 | 理由 |
|---|------|------|
| D-011 | 会议纪要统一归档到 `docs/meetings/` | 用户明确要求，避免散落 |
| D-012 | 搜索功能配置读取优先从 `.env` 文件，fallback config 模块 | 与测试连接保持一致，避免热重载失败导致不一致 |
| D-013 | Docker 骨架先输出，Sprint #003 正式验证 | 不阻塞当前本地验证流程，但提前准备 |

---

## 四、本次修复清单

| # | 类型 | 改动 | 文件 | 状态 |
|---|------|------|------|------|
| 1 | P0-BugA | 新建按钮 → `openCreate()` 重置全部表单状态 | TaskScheduler.vue L21 | ✅ |
| 2 | P0-BugA | 取消按钮 → `cancelCreate()` 清空 editingTaskId | TaskScheduler.vue L146 | ✅ |
| 3 | P0-BugA | 新增 `resetFormState()` / `openCreate()` / `cancelCreate()` 函数 | TaskScheduler.vue | ✅ |
| 4 | P0-BugB | 搜索优先从 .env 读取 auth_key 和 base_url | subscription_service.py L190-215 | ✅ |
| 5 | P0-BugB | 搜索增加调试日志（auth_key前6位+base_url） | subscription_service.py L213 | ✅ |
| 6 | P0-BugB | 测试连接 auth 异常不再静默吞掉 | config.py L170 | ✅ |
| 7 | 归档 | 会议纪要移动到 ops/meetings/ | 文件系统 | ✅ |
| 8 | 部署 | Dockerfile + docker-compose.yml 骨架 | deploy/ | ✅ |
| 9 | 治理 | copilot-instructions.md 迭代状态更新 | .github/prompts/ | ✅ |
| 10 | 构建 | 前端重新构建，产物更新到 api/webui/ | api/webui/ | ✅ |

---

## 五、后续工作

| 优先级 | 项目 | 触发条件 |
|--------|------|---------|
| P0 | 用户本地验证：新建任务 + 微信搜索 | 立即 |
| P1 | 本地多任务编排端到端测试 | 用户确认 Bug 修复后 |
| P1 | Linux 服务器部署 | 本地编排跑通后 |
| P2 | Docker 部署正式验证 | Sprint #003 |
| P2 | CI 套件建立 | Sprint #003 |

---

*会议纪要由 GitHub Copilot 记录 | Brain 主持 | 2026-02-27*
*归档位置: docs/meetings/（铁律）*
