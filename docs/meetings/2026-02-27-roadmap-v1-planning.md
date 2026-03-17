# 全体战略规划会议 — Roadmap v1 + Worktree 并行开发方案

> **日期**：2026-02-27  
> **性质**：全面路线图规划 + 并行分支方案设计  
> **主持**：Brain（架构/产品总负责人）  
> **参会**：Brain、Dev、PM、Researcher、Profile-Designer、Code-Reviewer  
> **触发**：用户提出"大刀阔斧改动 + 并行 worktree 开发"

---

## 一、会议背景与目标

### 当前里程碑

| 状态 | 描述 |
|------|------|
| ✅ 完成 | WebUI 8 模块基本可用，Pipeline 引擎运转，P0/P1 bug 全部修复 |
| ✅ 完成 | 任务调度 Pipeline-first 架构重构，abort 机制，task_config 数据丢失修复 |
| ⚠️ 进行中 | MVP 验收清单 1-4 项已通过，5-6 项（飞书同步 + 日志健康）未完成 |
| ❌ 未开始 | CI、测试覆盖、dev→main 合并、版本号管理 |

### 本次会议目标

1. 对历次会议中所有未落地 Ideas 进行集体取舍
2. 制定 Roadmap v1（v0.1 → v1.0 里程碑）
3. 输出 Worktree 并行开发方案（4-6 个独立分支）
4. 每个 worktree 有足够细的任务描述，可以直接开始 coding

---

## 二、各角色评审发言

### Brain 开场

> 我把历次会议里所有"提出但未落地"的 ideas 整理成 19 条，今天我们要逐一表态：**现在做 / 下一版本 / 放弃**。
>
> 我先说一个大判断：**我们已经过了"让系统跑起来"的阶段，正在进入"让系统可靠运行"的阶段**。用户要部署到服务器，要并行开发多个功能，这意味着我们需要同时推进三件事：
> 1. **稳定性**：消灭已知技术债（config 双轨、except pass、无测试）
> 2. **功能完整性**：剩余 MVP 项（飞书同步任务跑通、多平台 Pipeline 对接）
> 3. **开发体验**：worktree 并行开发需要分支隔离清晰
>
> 开始吧。

---

### Dev（开发工程师）

**对 19 个 Ideas 的评审：**

**Ideas 1 — Config 单一数据源 ConfigProvider**

我认为这是最高价值、最低风险的技术债清偿。我现设计过很多次 bug 的根源都是 `wechat_config.WECHAT_AUTH_KEY` 和 `config_service.get("WECHAT_AUTH_KEY")` 两条读取路径不同步。

具体方案：在 `config/config_service.py` 里增加一个 `get(key, default=None)` 静态方法，从已加载的 env 字典里读取。新代码规定必须走这条路径。旧代码中的 `from config import wechat_config` 模式，在涉及到的文件里逐步替换，但不要求一次性全改——会引入太多冲突。

**判断：✅ 现在做（独立 worktree）**

---

**Ideas 2 — Pipeline dry-run 模式**

这个想法很有价值，但实现成本不低。每个 Pipeline step 需要增加一个 `dry_run` 参数，在 dry-run 模式下只验证配置（如检查飞书 token 是否有效、表格 ID 是否存在）而不真正执行。

后端要加 `POST /scheduler/tasks/{id}/dry-run` 端点，前端要加一个"测试运行"按钮。

**判断：⚠️ 下一版本（v0.2）**，目前 MVP 跑通比 dry-run 更紧迫。

---

**Ideas 3 — 消除 except Exception: pass**

这是纯技术债清偿，没有任何争议。上一轮修复的假阳性连接测试就是这个 pattern 导致的。

现在的分布：`grep -r "except Exception" --include="*.py" .` 大约有 30-40 处，其中约 1/3 是 pass 或者只有 print。

实现方式：专门开一个 worktree，用 `ruff --select E722` 扫出所有裸 except，逐一改为具体异常 + `logger.warning/error`。这个工作不影响其他功能，可以完全并行。

**判断：✅ 现在做（独立 worktree，纯清理工作）**

---

**Ideas 6 — 微信 auth key 自动刷新**

Researcher 之前说了，这在技术上几乎是不可能的——微信风控很严，headless 浏览器自动登录会被识别。wechat-article-exporter 项目本身也没有提供 API 刷新途径。

更务实的做法（已经讨论过）：在 Dashboard 上显示 auth key 的有效期倒计时，让用户知道什么时候需要手动刷新。

**判断：❌ 放弃自动化**，仅做 Dashboard 展示（归入 Ideas 10）

---

**Ideas 7 — 平台分级（轻量/重量）**

这是部署文档侧的事情，不需要改代码。现在 `requirements.txt` 里 playwright 是强依赖，如果用户只用微信（纯 HTTP），可以把 playwright 设为可选依赖。

具体：把 `requirements.txt` 拆成 `requirements-base.txt`（FastAPI + SQLAlchemy + APScheduler 等核心）和 `requirements-playwright.txt`（依赖浏览器的爬虫）。Dockerfile 默认装全量，轻量部署文档里说明可以跳过 playwright。

**判断：✅ 现在做（部署文档 worktree 里顺手处理）**

---

**Ideas 15 — 多平台 Pipeline 对接**

这是当前最大的功能缺口。目前 Pipeline 的 `subscription_crawl` 步骤在 `pipeline_steps.py` 里，对微信以外的平台实际上没有测试过。小红书需要 Playwright 签名，抖音有自己的 API 格式，B站有独立的 `bilibili_service`。

这个工作量最大，但也是最有价值的功能扩展。应该作为独立 worktree，专注 XHS + 抖音 + B站三个平台的 Pipeline 打通。

**判断：✅ 现在做（独立 worktree，并行开发）**

---

**Ideas 18 — 删除 legacy _run_task 分支**

这个和 Ideas 1（Config 重构）一样，是清偿技术债。现在 `scheduler_service.py` 里还有 `_run_legacy_task` 的影子分支，和 pipeline 模式并存。

条件：先确保所有任务类型的 Pipeline 模式都跑通（Ideas 15 完成后），再删 legacy。

**判断：⚠️ 待 Ideas 15 完成后做**

---

**Ideas 19 — 单任务多 cron trigger**

APScheduler 原生支持，但前端 UI 改动不小（需要支持添加多个调度规则）。用户目前最迫切的是跑通单个任务，多 cron 是高级功能。

**判断：❌ 推到 v0.3**

---

### PM（项目经理）

**对 19 个 Ideas 的评审：**

**Ideas 4 — 版本号管理（v0.1.0 tag）**

这不是"可有可无"的东西——用户部署到服务器之后，必须能知道自己运行的是哪个版本。`git describe --tags` 是最简单的方式。

建议：MVP 6 步跑通时打 `v0.1.0` tag，同时在 API 里加一个 `/version` 端点返回版本号，Dashboard 右下角显示。

**判断：✅ 与 MVP 验收同步完成**

---

**Ideas 5 — Changelog 机制**

`CHANGELOG.md` 是标准开源项目实践。但不需要过度工程化——现在我们的 commit 信息已经足够详细，可以从 git log 生成。

工具链：用 `git-cliff` 或者手写。现阶段手写就行，规则是：每次打 tag 前更新 `CHANGELOG.md`。

**判断：✅ 与版本号管理一起做**

---

**Ideas 9 — Onboarding Wizard（首次使用引导）**

Profile-Designer 提的这个想法在商业化角度很有价值。但从 MVP 角度看，我们的目标用户是"懂技术的运营人员"，不是完全的非技术用户。首次引导可以简化为：
- 首次打开 WebUI 检测 config 是否配置完整
- 如果没有配置，header 区域显示一个橙色 banner："请先完成基础配置"，点击跳转配置页
- 不需要完整的 3 步 wizard

**判断：⚠️ 简化版现在做（包含在 Dashboard 健康面板 worktree 里）**

---

**Ideas 16 — Subscription 与 Task 关联**

用户从订阅页面"批量采集"到"创建定时任务"的跳转目前需要手动完成（先批量采集，再去任务页创建任务）。

实现方式：在 Subscription 页面的订阅详情或批量操作区域，增加一个"创建定时采集任务"按钮，点击后预填 TaskScheduler 的新建任务弹窗（platform + task_type = subscription_crawl）。

**判断：✅ 现在做（包含在 Pipeline/Task 优化 worktree 里）**

---

### Researcher（技术调研员）

**对 19 个 Ideas 的评审：**

**Ideas 6 — 微信 auth key 自动刷新**

我之前的评估没有改变——这条路目前是死路。wechat-article-exporter 的 auth key 是通过浏览器扩展捕获的，本质是拦截了微信 Web 端的 cookie session。服务器端没有浏览器环境，无法复现这个过程。

退而求其次，可以做的是：
1. Dashboard 显示 auth key 最后验证时间
2. 每次采集前自动 ping 一下 wechat-article-exporter 服务，如果失败则在执行历史里标注"认证失效"而非简单报错
3. 支持用户通过 WebUI Config 页面更新 auth key（已有，但告知路径不够清晰）

**判断：❌ 自动化放弃。Dashboard 展示 + 失效告警做（归入 Ideas 10）**

---

**Ideas 7 — 平台分级**

Dev 的方案合理。我补充一点：除了 requirements 拆分，`docker-compose.yml` 也应该支持 `ENABLE_PLAYWRIGHT=false` 的环境变量，让容器启动时跳过 playwright 的浏览器安装（`playwright install --with-deps chromium` 这一步很慢，约 2-3 分钟）。

**判断：✅ 现在做（与部署文档一起）**

---

**Ideas 8 — 爬虫健康监控**

这个功能我认为对用户信任感的建立非常重要。当前 Dashboard 显示的是静态统计（总帖子数、订阅数）。改成动态的"平台健康状态"：

| 平台 | HTTP 可达 | Auth 有效 | 最后采集 | 状态 |
|------|-----------|-----------|----------|------|
| 微信 | ✅ | ✅ (2d剩余) | 2h前 | 🟢 |
| 飞书 | ✅ | ✅ | — | 🟢 |
| 小红书 | ✅ | N/A | 未采集 | 🟡 |

后端需要一个 `/health/platforms` 端点，定期 ping 各平台的基础 API（不是完整爬取，只是检查连通性）。

**判断：✅ 现在做（独立 worktree）**

---

### Profile-Designer（UI/交互设计）

**对 19 个 Ideas 的评审：**

**Ideas 10 — Dashboard 健康面板**

这是当前 UI 改进里性价比最高的。当前 Dashboard 只有数字统计卡（总订阅数、总帖子数等），对用户没有行动指导价值。

具体设计方案：
```
┌─────────────────────────────────────────────┐
│  系统健康 (更新于2分钟前) [手动刷新]         │
├──────────┬───────────┬────────────┬─────────┤
│ 平台     │ 连接状态  │ 认证状态   │ 最后采集│
├──────────┼───────────┼────────────┼─────────┤
│ 🔴 微信  │ ✅ 可达   │ ⚠️ 2天后过期│ 1小时前 │
│ 🟢 飞书  │ ✅ 可达   │ ✅ 有效     │ —       │
│ 🟡 小红书│ ✅ 可达   │ N/A        │ 未采集  │
└──────────┴───────────┴────────────┴─────────┘
```
Naive UI 的 `n-data-table` + 颜色徽章实现，后端 `/health/platforms` 返回结构化 JSON。

**判断：✅ 现在做（独立 worktree，与 Researcher 的 Ideas 8 合并）**

---

**Ideas 11 — 配置分组折叠**

ConfigManager 页面目前将所有平台配置平铺展示，视觉上很拥挤。改进方案：
- 按平台分 `n-collapse` 手风琴展开/折叠
- 已配置的平台默认展开，未配置的默认折叠
- 必填项用红色星号标注

这个改动纯前端，3-4 小时可以完成。

**判断：✅ 现在做（包含在 Dashboard/健康面板 worktree 里）**

---

**Ideas 9 — Onboarding Wizard（简化版）**

同意 PM 的简化方案。完整 wizard 对我们目前的用户群没必要。改成：
- 首次访问时，如果 `WECHAT_API_BASE_URL` 为空，Dashboard 顶部显示 `n-alert` 警告条
- Config 页面各分组高亮未填写的必填项

**判断：✅ 简化版做（包含在 Dashboard worktree 里）**

---

**Ideas 17 — Pipeline 可视化编辑器（拖拽）**

这个在上次会议里已经被列为 P2。我来评估一下实现成本：需要引入 `vue-draggable-next` 或者 `@vueuse/gesture`，步骤卡片需要支持拖拽排序，每张卡片需要内嵌独立的配置表单。

实现成本：2-3天工作量，且容易引入 UI 状态管理的复杂性。

**判断：❌ 推到 v0.3**，当前 Pipeline 步骤列表（可增删排序）已经满足需求。

---

### Code-Reviewer（代码质量）

**对 19 个 Ideas 的评审：**

**Ideas 3 — 消除 except Exception: pass**

我来补充具体数据：

```
grep -rn "except Exception" api/ --include="*.py" | wc -l  → 约 38 处
grep -rn "except:" api/ --include="*.py" | wc -l           → 约 5 处
grep -rn "except.*pass" api/ --include="*.py" | wc -l      → 约 12 处
```

其中最危险的是静默 pass 的那 12 处，它们掩盖了真实错误。我建议的规范：

```python
# ❌ 禁止
except Exception:
    pass

# ❌ 禁止  
except Exception as e:
    print(e)

# ✅ 要求
except SpecificError as e:
    logger.warning("描述: %s", e, exc_info=True)
    raise  # 或者 return 一个明确的失败状态
```

**判断：✅ 现在做（独立 worktree）**

---

**Ideas 12 — GitHub Actions CI**

目前没有 CI，每次 push 无法自动验证。我设计的 CI pipeline：

```yaml
# .github/workflows/ci.yml
jobs:
  lint-and-type:
    - ruff check api/
    - mypy api/ --ignore-missing-imports
  test:
    - pytest tests/ -x --tb=short
  build-frontend:
    - npm run build
```

CI 触发条件：PR 到 dev 或 main 时运行。这是 `dev → main` 合并的前置条件。

**判断：✅ 现在做（独立 worktree）**

---

**Ideas 13 — 异常处理规范**

与 Ideas 3 合并，同一个 worktree 处理。

---

**Ideas 14 — dev → main 合并检查清单**

合并前需满足：
1. CI 全绿（pytest + mypy + ruff）
2. MVP 验收清单 6 步全部通过（用户手工验收）
3. 无硬编码密钥（`wechat_config.py` 默认 auth key 已清空）
4. CHANGELOG.md 已更新
5. 版本号已打 tag v0.1.0

这 5 条作为 PR 模板的 checklist。

**判断：✅ 与 CI worktree 一起准备**

---

## 三、自由讨论

### 讨论 1：Ideas 15（多平台 Pipeline）要做几个平台？

**Dev**：我建议本轮只做小红书 + 抖音，因为这两个平台用户基数最大，且已有基础 crawler 代码。B站、快手、知乎放下一版本。

**Researcher**：小红书的 Playwright 签名问题复杂，实际上 HTTP 搜索接口已经有了（`/api/sns/web/v1/search/notes`），只是稳定性不够好。建议先做抖音（API 相对稳定），小红书做到"能用但不保证稳定"。

**Code-Reviewer**：我有个顾虑——现在 `pipeline_steps.py` 里的 `subscription_crawl` 步骤直接调用 `CrawlerManager`，而 CrawlerManager 是 subprocess 模式。如果多平台并发跑，每个平台一个子进程，资源管理很复杂。

**Brain 仲裁**：
- 本轮（v0.1）：确保微信 Pipeline 100% 可靠
- 下轮（v0.2）：做抖音 Pipeline 打通，小红书标注"实验性"
- B站/快手/知乎放 v0.3
- **共识：降低 Ideas 15 的本轮范围，专注微信 Pipeline 的端到端可靠性**

---

### 讨论 2：Config 重构的边界在哪里？

**Dev**：我说的不是大重构——只是让所有读取有一个统一入口。具体就是在 `config_service.py` 里加一个 `get(key)` 方法，从 `.env` 读取的值缓存到这里，平台 config 模块作为这个值的"类型化视图"。

**Code-Reviewer**：问题是 `from config import wechat_config` 这种用法遍地都是，改的时候容易漏掉某个地方。需要有个方法确认所有读取路径都统一了。

**Brain 仲裁**：本轮只做"新代码必须走 config_service"，旧代码逐步迁移。添加一个 `config/config_service.py` 的 `get(key)` 方法，并在 PR 里 grep 确认没有新增的 `from config import *_config` 用法。**不做全量迁移。**

---

### 讨论 3：worktree 的并行度——4 个还是 6 个？

**PM**：太多并行分支容易产生合并冲突，特别是前端。建议不超过 5 个。

**Dev**：从代码耦合来看，以下几个方向是可以真正并行的：
- 后端纯清理（exceptions + config）→ 几乎不动前端
- Dashboard/UI 改进 → 几乎不动后端业务逻辑
- 平台 Pipeline 扩展 → 只动 `pipeline_steps.py` 和平台 media_platform 代码
- CI/DevOps → 只新增文件，不改任何业务代码
- 部署文档 → 只动 docs 和 requirements

**Brain 仲裁**：确定 5 个 worktree，方案见第四节。

---

## 四、Roadmap v1

### 里程碑定义

| 版本 | 代号 | 目标 | 预计完成 |
|------|------|------|----------|
| **v0.1.0** | `MVP` | 微信全流程端到端跑通 + 部署文档 + CI 基础 | 本轮迭代 |
| **v0.2.0** | `Stable` | 技术债清偿 + 健康监控 + 抖音 Pipeline | 下轮迭代 |
| **v0.3.0** | `MultiPlatform` | 多平台扩展（XHS/B站/快手）+ 可视化 Pipeline 编辑器 | 第三轮 |
| **v1.0.0** | `Production` | CI 全绿 + 测试覆盖 + dev→main 合并 + 商业化文档 | 远期 |

### v0.1.0 验收标准（MVP 6 步）

- [ ] WebUI 创建定时任务（subscription_crawl，微信，每天8点）
- [ ] 到点自动执行采集
- [ ] 采集结果入库，数据浏览页可见
- [ ] 飞书同步任务到点自动推送到多维表
- [ ] 执行日志可在执行历史查看
- [ ] 整个过程无需人工干预

### v0.2.0 验收标准

- [ ] 所有 `except Exception: pass` 消除
- [ ] GitHub Actions CI 全绿（ruff + mypy + pytest）
- [ ] Dashboard 健康面板展示各平台状态
- [ ] Config 读取统一入口
- [ ] 抖音 Pipeline 可用（标注实验性）

### v0.3.0 验收标准

- [ ] 小红书 Pipeline 可用
- [ ] B站/快手 Pipeline 可用
- [ ] Pipeline 步骤可视化拖拽编辑
- [ ] 单任务多 cron trigger 支持

### v1.0.0 验收标准

- [ ] pytest 覆盖率 > 60%（关键路径）
- [ ] mypy 全量通过
- [ ] dev → main PR 合并（附 CI 全绿 + code review）
- [ ] CHANGELOG.md 完整
- [ ] tag v1.0.0 打出

---

## 五、Worktree 并行开发方案

### 总体原则

- 每个 worktree 对应一个 `feature/*` 分支，从当前 `dev` checkout
- worktree 之间代码变更不重叠（确保 merge 无冲突）
- 完成后向 `dev` 发 PR，Brain 审核合并

---

### Worktree 1 — `feature/pipeline-reliability`

**目标**：确保微信全流程 Pipeline 端到端可靠跑通（MVP 核心）

**分支名**：`feature/pipeline-reliability`

**任务范围**：

| # | 任务 | 文件 | 详细说明 |
|---|------|------|----------|
| 1.1 | 验证微信 subscription_crawl 步骤 | `api/services/pipeline_steps.py` | 增加详细日志，确认每一步 input/output；失败时报告具体原因而非通用错误 |
| 1.2 | 飞书同步步骤入参验证 | `api/services/pipeline_steps.py` | `feishu_push` 步骤开始前检查 `app_token`/`table_id` 非空，缺失时抛出明确异常（而非等到飞书 API 报错） |
| 1.3 | Pipeline 执行结果持久化 | `api/services/scheduler_service.py` | 每个 step 执行完后将结果写入 `TaskExecution.log_output`（JSON 格式，记录 step 名称、耗时、输入输出摘要） |
| 1.4 | MVP 验收清单 5-6 项落地 | `api/services/`, `webui-src/` | 飞书同步任务创建 + 执行验证；执行历史页展示 step 级别日志 |
| 1.5 | Subscription 页面"创建定时任务"按钮 | `webui-src/src/views/Subscription.vue` | 从订阅行添加"创建采集任务"快捷入口，预填 TaskScheduler 新建弹窗的 platform + task_type |

**关键文件**：
- `api/services/pipeline_steps.py`
- `api/services/scheduler_service.py`
- `webui-src/src/views/Subscription.vue`
- `webui-src/src/views/TaskScheduler.vue`（仅执行历史展示改动）

**交付标准**：MVP 6 步验收全部通过

---

### Worktree 2 — `feature/dashboard-health`

**目标**：Dashboard 健康面板 + Config UI 优化 + Onboarding 提示

**分支名**：`feature/dashboard-health`

**任务范围**：

| # | 任务 | 文件 | 详细说明 |
|---|------|------|----------|
| 2.1 | 后端健康检测 API | `api/routers/health.py`（新建） | `GET /health/platforms` - 返回各平台连接状态、auth 有效期。对微信：ping `WECHAT_API_BASE_URL/health`；对飞书：调 `/open-apis/auth/v3/token/app` 验证 token；对数据库：`SELECT 1` |
| 2.2 | Dashboard 健康面板 | `webui-src/src/views/Dashboard.vue` | 替换现有静态统计卡片区域，增加平台健康状态表格。颜色：🟢 正常 / 🟡 警告（auth 48h内过期）/ 🔴 异常 |
| 2.3 | Config 分组折叠 | `webui-src/src/views/ConfigManager.vue` | 按平台（微信/飞书/数据库/各爬虫）分 `n-collapse` 展开折叠，必填项标红星 |
| 2.4 | Onboarding 警告条 | `webui-src/src/views/Dashboard.vue` | 首次访问检测 `WECHAT_API_BASE_URL` 是否配置，未配置时 Dashboard 顶部显示 `n-alert: "请先完成基础配置 →"` |
| 2.5 | auth key 有效期提示 | `webui-src/src/views/Dashboard.vue` | 从健康检测 API 返回的 auth 剩余时间，在健康面板里展示"还有 2 天过期"倒计时样式 |
| 2.6 | Dashboard 版本号显示 | `webui-src/src/views/Dashboard.vue` | 右下角显示 `v0.1.0`（从 `GET /version` 端点读取，后端返回 `pyproject.toml` 里的版本号） |

**关键文件**：
- `api/routers/health.py`（新建）
- `api/main.py`（注册 router）
- `webui-src/src/views/Dashboard.vue`
- `webui-src/src/views/ConfigManager.vue`

**交付标准**：Dashboard 展示各平台绿/黄/红状态，Config 页面分组折叠

---

### Worktree 3 — `feature/code-quality`

**目标**：技术债清偿——异常处理规范化 + CI 基础建设

**分支名**：`feature/code-quality`

**任务范围**：

| # | 任务 | 文件 | 详细说明 |
|---|------|------|----------|
| 3.1 | 扫描并修复 except pass | `api/**/*.py` | `ruff --select E722` + 手工审查。每处 pass 改为具体 exception + logger。重点：`api/services/`, `media_platform/`, `store/` |
| 3.2 | 统一 logging 配置 | `api/main.py`, `base/base_crawler.py` | 确保所有模块使用 `logging.getLogger(__name__)`，格式统一为 `%(asctime)s - %(name)s - %(levelname)s - %(message)s` |
| 3.3 | Config 统一入口 `get()` 方法 | `config/config_service.py` | 在 ConfigService 类里增加 `@staticmethod def get(key: str, default=None)` 方法，从已加载的 env 字典读取。新代码规范：任何新增的平台配置读取必须走这个方法 |
| 3.4 | GitHub Actions CI | `.github/workflows/ci.yml`（新建） | jobs: `lint`（ruff check）、`typecheck`（mypy api/ --ignore-missing-imports）、`build-frontend`（npm run build），触发：PR to dev 或 main |
| 3.5 | PR 模板 | `.github/pull_request_template.md`（新建） | v0.1.0 合并检查清单（CI 绿、MVP 验收、无硬编码密钥、CHANGELOG 更新） |
| 3.6 | 清空硬编码 auth key | `config/wechat_config.py` | `WECHAT_AUTH_KEY` 默认值改为 `""`，在注释里说明如何获取 |

**关键文件**：
- `api/**/*.py`（扫描范围）
- `config/config_service.py`
- `config/wechat_config.py`
- `.github/workflows/ci.yml`（新建）
- `.github/pull_request_template.md`（新建）

**交付标准**：`ruff check api/` 无 E722 告警；CI YAML 文件存在且语法有效；硬编码 key 消除

---

### Worktree 4 — `feature/deployment-docs`

**目标**：部署文档完善 + 平台分级依赖 + CHANGELOG

**分支名**：`feature/deployment-docs`

**任务范围**：

| # | 任务 | 文件 | 详细说明 |
|---|------|------|----------|
| 4.1 | Requirements 分级 | `requirements.txt`（改名），`requirements-base.txt`（新建），`requirements-playwright.txt`（新建） | base = FastAPI/SQLAlchemy/APScheduler 等 HTTP-only 依赖；playwright = playwright 及需要它的爬虫 |
| 4.2 | Docker 轻量模式 | `Dockerfile`，`docker-compose.yml` | 增加构建参数 `ENABLE_PLAYWRIGHT=true/false`，false 时跳过 `playwright install` |
| 4.3 | 快速部署文档 | `docs/guide/quick-deploy.md`（新建）或更新已有 | 轻量部署（仅微信，5步）+ 全功能部署（含 Playwright，10步）+ 常见问题 Q&A |
| 4.4 | CHANGELOG.md | `CHANGELOG.md`（新建） | 从 git log 整理，记录 v0.1.0 的所有主要变更 |
| 4.5 | 版本号写入 pyproject.toml | `pyproject.toml` | `version = "0.1.0"` |
| 4.6 | `/version` API 端点 | `api/routers/health.py`（与 worktree 2 协调，或单独 router） | 读 `pyproject.toml` 里的 version 返回 JSON |

**关键文件**：
- `requirements*.txt`
- `Dockerfile`
- `docker-compose.yml`
- `docs/guide/quick-deploy.md`
- `CHANGELOG.md`
- `pyproject.toml`

**交付标准**：`docker-compose up -d` 一条命令启动可用；部署文档覆盖轻量/全功能两个场景

> ⚠️ **冲突协调**：`/version` 端点与 Worktree 2 的 `health.py` 可能在同一文件，两个 worktree 需要协调谁先合并，或者拆到独立 router。

---

### Worktree 5 — `feature/multiplatform-pipeline`

**目标**：抖音 Pipeline 打通（实验性）+ XHS Pipeline 基础

**分支名**：`feature/multiplatform-pipeline`

**任务范围**：

| # | 任务 | 文件 | 详细说明 |
|---|------|------|----------|
| 5.1 | 抖音 subscription_crawl 对接 | `api/services/pipeline_steps.py` | 在 `subscription_crawl` step 里，对 platform="douyin" 走抖音 crawler。确认 `media_platform/douyin/` 里的 `DouyinCrawler` 可以在 Pipeline 模式下被调用 |
| 5.2 | 抖音订阅模型验证 | `model/m_douyin.py`、`store/douyin/` | 确认 `NoteItem`/`CommentItem` 等模型与 SQLite store 对齐，参考微信的 `NoteItem` 实现 |
| 5.3 | XHS HTTP 搜索稳定性 | `api/services/subscription_service.py` | 修复 XHS 创作者搜索 fallback 逻辑：优先走 `/api/sns/web/v1/search/user`（需要 cookie），cookie 失效时返回友好错误而非空列表 |
| 5.4 | 多平台 Pipeline 集成测试 | `tests/test_pipeline_multiplatform.py`（新建） | 分别对微信/抖音 mock 一个采集步骤，验证 pipeline context 传递正确 |
| 5.5 | Legacy _run_task 分支标注废弃 | `api/services/scheduler_service.py` | 在 legacy 分支开头加 `# DEPRECATED: 此分支将在 v0.2 移除，所有任务请使用 pipeline 模式` + `logger.warning`，但暂不删除代码 |

**关键文件**：
- `api/services/pipeline_steps.py`
- `media_platform/douyin/`
- `api/services/subscription_service.py`
- `tests/test_pipeline_multiplatform.py`（新建）

**交付标准**：抖音平台创建 subscription_crawl 任务后可以成功执行（日志可见），不报 "platform not supported" 错误

---

## 六、Worktree 冲突分析

| Worktree 对 | 潜在冲突文件 | 处理方式 |
|-------------|-------------|----------|
| WT1 + WT5 | `pipeline_steps.py` | WT1 先合并，WT5 rebase on top |
| WT2 + WT4 | `health.py`（新建） | WT2 定义 router 骨架并在 main.py 注册，WT4 的 `/version` 端点作为 PR 追加 |
| WT3 + 所有 | `api/**/*.py`（修改异常处理）| WT3 最后合并，其他 WT 先合并后 WT3 rebase |
| WT4 + WT3 | `pyproject.toml` | 分工明确：WT4 改 version 字段，WT3 不动此文件 |

---

## 七、决议总结

### 行动清单

| # | 决议 | 优先级 | Worktree |
|---|------|--------|----------|
| A1 | 启动 5 个 worktree 并行开发 | 立即 | — |
| A2 | WT1（pipeline-reliability）确保 MVP 6步跑通 | P0 | WT1 |
| A3 | WT2（dashboard-health）健康面板 + Config 折叠 | P1 | WT2 |
| A4 | WT3（code-quality）消除 except pass + CI + 清空硬编码 key | P1 | WT3 |
| A5 | WT4（deployment-docs）部署文档 + CHANGELOG + 版本号 | P1 | WT4 |
| A6 | WT5（multiplatform-pipeline）抖音 Pipeline + legacy deprecated | P2 | WT5 |
| A7 | 所有 WT 合并后，测试 MVP 6 步，通过则打 tag v0.1.0 | P0 | — |

### Ideas 最终取舍表

| Idea | 决议 | 归属 |
|------|------|------|
| 1 Config 单一入口 | ✅ 做（部分） | WT3 |
| 2 Pipeline dry-run | ⚠️ 推到 v0.2 | — |
| 3 消除 except pass | ✅ 做 | WT3 |
| 4 版本号管理 | ✅ 做 | WT4 |
| 5 Changelog | ✅ 做 | WT4 |
| 6 auth key 自动刷新 | ❌ 放弃（太难），仅做展示 | WT2 |
| 7 平台分级 | ✅ 做 | WT4 |
| 8 爬虫健康监控 | ✅ 做 | WT2 |
| 9 Onboarding Wizard | ✅ 简化版（警告条） | WT2 |
| 10 Dashboard 健康面板 | ✅ 做 | WT2 |
| 11 Config 分组折叠 | ✅ 做 | WT2 |
| 12 GitHub Actions CI | ✅ 做 | WT3 |
| 13 异常处理规范 | ✅ 做 | WT3 |
| 14 合并检查清单 | ✅ 做 | WT3 |
| 15 多平台 Pipeline | ✅ 做（仅抖音+XHS基础） | WT5 |
| 16 Subscription→Task 关联 | ✅ 做 | WT1 |
| 17 Pipeline 可视化拖拽 | ❌ 推到 v0.3 | — |
| 18 删除 legacy 分支 | ⚠️ 本轮标 deprecated，v0.2 删除 | WT5 |
| 19 单任务多 cron | ❌ 推到 v0.3 | — |

### 分歧记录

| 议题 | 立场 A | 立场 B | Brain 仲裁 |
|------|--------|--------|-----------|
| 多平台 Pipeline 范围 | Dev：只做抖音 | PM：看用户需求 | 本轮做抖音+XHS基础，B站/快手放 v0.3 |
| Config 重构深度 | Dev：引入 ConfigProvider 全量迁移 | Code-Reviewer：成本太高 | 只加 `get()` 入口，新代码走它，旧代码不强制迁移 |
| CI 何时建 | Code-Reviewer：立即 | PM：MVP 后 | 并行做，不阻塞 MVP 验收 |
| Pipeline dry-run | Dev：高价值 | PM：不紧迫 | 推到 v0.2 |

---

## 八、Brain 闭幕词

> 今天这次规划覆盖了过去所有会议里"提了但没做"的东西，我们终于把它们一一表了态。
>
> 5 个 worktree 是经过仔细设计的——它们之间的代码变更几乎不重叠，真正可以并行推进。唯一需要小心的是合并顺序：WT1 先，WT2/WT4 并行，WT3 最后（因为它改动文件最广）。WT5 可以一直并行，不阻塞其他。
>
> 核心原则还是那句话：**先把现有功能端到端跑通（WT1），再填充质量和监控（WT2/WT3/WT4），最后扩展功能范围（WT5）**。
>
> 开始建 worktree 吧。

---

*纪要由 Brain 整理，归档于 `docs/meetings/`*  
*所有 worktree 从当前 `dev` 分支 checkout，完成后向 `dev` 发 PR*
