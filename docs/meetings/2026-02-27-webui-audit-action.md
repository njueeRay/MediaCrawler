# 全体会议纪要 — WebUI 功能审计后行动决策

> **日期**: 2026-02-27  
> **主持**: Brain (战略协调)  
> **参与**: Dev, Code-Reviewer, PM  
> **类型**: 紧急修复 + 功能补全会议  
> **会议触发**: 用户验收测试反馈 → Dev 完成全面代码审计

---

## 一、审计结果确认

### 经 Brain 复核确认的问题清单

| # | 严重度 | 问题 | 根因 | 影响范围 |
|---|--------|------|------|----------|
| BUG-1 | **P0** | 微信连接测试永远失败 | 前端传 `type="wechat"`, 后端判断 `conn_type == "wechat_source"` | 配置管理页 |
| BUG-2 | **P0** | WebUI 修改 WECHAT_AUTH_KEY 后不生效 | `reload_from_env()` 未 reload 平台 config 模块 | 微信创作者搜索 |
| BUG-3 | **P1** | 任务调度无编辑功能 | 前端缺编辑按钮和编辑弹窗；后端 PUT 已就绪 | 任务调度页 |
| FEAT-4 | **P2** | 小红书创作者搜索未实现 | `search_creators()` 对 xhs return `[]` | 订阅管理页 |

### Brain 补充发现的体验问题

| # | 严重度 | 问题 | 发现方式 |
|---|--------|------|----------|
| UX-1 | **P1** | 不支持搜索的平台（抖音/快手/贴吧/知乎）点击搜索后无任何反馈，静默返回空列表 | 代码审查：`search_creators()` 直接 `return []`，前端无提示 |
| UX-2 | **P2** | 任务调度操作列 4 个按钮（加上编辑）会显得拥挤 | UI 布局分析：当前列宽 200px，3 按钮已紧凑 |
| UX-3 | **P2** | 新建/编辑任务弹窗缺少表单验证 | 代码审查：`createTask()` 无前端校验 |
| UX-4 | **P1** | 任务调度平台列表缺少快手/贴吧/知乎 | 代码比对：Subscription 有 8 平台，TaskScheduler 只有 5 平台 |

---

## 二、决策与行动计划

### 决策原则

1. **P0 BUG 立即修复** — 用户核心流程阻断
2. **P1 功能补全与 P0 并行** — 编辑功能和体验改善独立于 BUG 修复
3. **P2 新功能本轮实现** — 用户明确要求"像微信一样搜索小红书"
4. **XHS 搜索采用 HTTP API 方案** — 小红书 Web 端有 `/api/sns/web/v1/search/notes` 但无公开用户搜索 API；改用 note 搜索提取作者信息（无需 Playwright），失败时 fallback 到 URL/ID 精确查找

### 执行清单

#### 阶段 1: P0 BUG 修复（立即）

| 任务 | 文件 | 改动 | 负责 |
|------|------|------|------|
| BUG-1: 微信连接测试 type 匹配 | `api/routers/config.py` L121 | `conn_type == "wechat_source"` → `conn_type in ("wechat_source", "wechat")` | Dev |
| BUG-2: 热重载追加平台 config | `config/__init__.py` L32-63 | `reload_from_env()` 追加 reload 所有 `*_config` 模块 | Dev |

#### 阶段 2: P1 功能补全 + 体验优化（与阶段 1 并行）

| 任务 | 文件 | 改动 | 负责 |
|------|------|------|------|
| BUG-3: 任务编辑按钮+弹窗 | `webui-src/src/views/TaskScheduler.vue` | 操作列增加编辑按钮；复用新建弹窗（传入已有数据预填）；提交时调用 PUT | Dev |
| UX-1: 不支持搜索的平台给出提示 | `api/services/subscription_service.py` | 对不支持的平台返回带 `unsupported` 标记的空结果或抛出友好异常 | Dev |
| UX-3: 新建/编辑表单增加验证 | `webui-src/src/views/TaskScheduler.vue` | 必填项校验（名称、调度类型） | Dev |
| UX-4: 任务调度平台列表对齐 | `webui-src/src/views/TaskScheduler.vue` | `platformOptions` 增加快手/贴吧/知乎 | Dev |

#### 阶段 3: P2 新功能

| 任务 | 文件 | 改动 | 负责 |
|------|------|------|------|
| FEAT-4: XHS 创作者搜索 | `api/services/subscription_service.py` | 新增 `_search_xhs()` 方法 — 通过小红书笔记搜索提取作者信息 | Dev |

#### 阶段 4: 构建 + 验证

| 任务 | 说明 | 负责 |
|------|------|------|
| 前端构建 | `npm run build` 输出到 `api/webui/` | Dev |
| 集成测试 | 启动服务，验证所有修复项 | Code-Reviewer |
| 更新 DEVLOG | 记录本次修复 | PM |

---

## 三、技术决策记录

### TD-1: XHS 创作者搜索方案

**决策**: 使用小红书 Web 端笔记搜索 API 提取作者信息（HTTP 方式）  

**理由**:
- 小红书没有公开的用户搜索 API
- 笔记搜索 `/api/sns/web/v1/search/notes` 返回结果中包含 `note_card.user` 信息
- 需要已登录的 cookie（从 `browser_data/cdp_xhs_user_data_dir` 读取）
- 对搜索结果中的 user 去重，提取 creator_id / creator_name / creator_avatar
- 如果无 cookie 可用，fallback 到提示用户需要先登录小红书

**备选（已否决）**:
- Playwright 实时搜索：过重，WebUI API 调用不应启动浏览器
- 爬取个人主页：需要已知 user_id，无法实现关键词搜索

### TD-2: 不支持搜索平台的处理

**决策**: 后端对不支持的平台返回空列表 + `message` 字段说明原因，前端展示友好提示

---

## 四、执行顺序

```
BUG-1 + BUG-2 (Python 后端, 并行)
       ↓
BUG-3 + UX-1~4 (前端 + 少量后端, 并行)
       ↓
FEAT-4 (小红书搜索, 依赖后端)
       ↓
前端构建 → 集成验证 → DEVLOG 更新
```

---

## 五、DoD (Definition of Done)

- [ ] 微信连接测试：前端点击测试 → 后端正确路由到 wechat_source 逻辑
- [ ] WECHAT_AUTH_KEY 热重载：WebUI 修改 → 立即生效于创作者搜索
- [ ] 任务编辑：点击编辑 → 弹窗预填 → 提交 PUT → 列表刷新
- [ ] XHS 搜索：输入关键词 → 返回创作者列表（含头像、粉丝数等）
- [ ] 不支持平台提示：搜索抖音/快手/贴吧/知乎 → 弹出友好提示
- [ ] 前端构建产物更新到 `api/webui/`
- [ ] 所有改动无类型错误 / lint 错误

---

**下次检查点**: 全部实施完成后进行集成验证
