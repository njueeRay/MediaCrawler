# WebUI 开发 TODO

> 按 Phase 追踪实施进度，每完成一项打 ✅

---

## Phase 0: 基础设施准备 (3天)

### 后端
- [x] 0.7 创建 `database/webui_models.py`（7 个 ORM 模型，共享 Base）
- [x] 0.8 修改 `database/db.py`（添加 `import database.webui_models`）
- [x] 0.6a 创建 `api/deps.py`（DB session 依赖注入）
- [x] 0.6b 创建 `api/schemas/common.py`（统一响应格式）
- [x] 创建 `api/schemas/config.py`
- [x] 创建 `api/schemas/subscription.py`
- [x] 创建 `api/schemas/field_mapping.py`
- [x] 创建 `api/schemas/feishu.py`
- [x] 创建 `api/schemas/scheduler.py`
- [x] 创建 `api/services/config_service.py`
- [x] 创建 `api/services/subscription_service.py`
- [x] 创建 `api/services/field_mapping_service.py`
- [x] 创建 `api/services/feishu_service.py`
- [x] 创建 `api/services/scheduler_service.py`
- [x] 0.9 创建 `api/services/webui_init.py`（种子数据）
- [x] 创建 `api/routers/config.py`
- [x] 创建 `api/routers/subscription.py`
- [x] 创建 `api/routers/field_mapping.py`
- [x] 创建 `api/routers/feishu.py`
- [x] 创建 `api/routers/scheduler.py`
- [x] 更新 `api/routers/__init__.py`
- [x] 更新 `api/schemas/__init__.py`
- [x] 更新 `api/main.py`（注册路由 + startup）

### 前端
- [x] 0.1 创建 `webui-src/` 项目骨架
- [x] 0.2 安装 Naive UI + TailwindCSS
- [x] 0.3 AppLayout 主布局
- [x] 0.4 Vite 开发代理配置
- [x] 0.5 构建输出配置
- [x] 0.6 8 个页面视图组件
- [x] 0.7 TypeScript 检查通过
- [x] 0.8 Vite 生产构建成功

---

## Phase 1: 前端-后端全面对接 ✅

> 后端审计结论：Phase 0 已实现全部 Service + Router。本阶段将 8 个前端页面从 stub 升级为真实 API 调用。

- [x] 1.1 Dashboard.vue — `/api/dashboard` 聚合 + 爬虫控制 + 最近日志
- [x] 1.2 ConfigManager.vue — 多类型测试连接 + 变更历史 Tab
- [x] 1.3 Subscription.vue — 统计卡片 + 手动添加 + toggle active + 触发采集
- [x] 1.4 DataExplorer.vue — 类型过滤 + 预览 + 下载 + 统计
- [x] 1.5 FieldMapping.vue — 方案详情编辑器 + 行内 item 编辑 + 增删 item
- [x] 1.6 FeishuSync.vue — 同步表单启用 + 方案联动 + `POST /feishu/sync`
- [x] 1.7 TaskScheduler.vue — 执行历史 Tab + cron + toggle enable/disable
- [x] 1.8 Logs.vue — 加载历史按钮 + WebSocket 实时流
- [x] 1.9 TypeScript + Vite 构建验证通过

## Phase 2: 增强与完善 ✅

- [x] 2.1 后端启动验证 + apscheduler 依赖安装
- [x] 2.2 全局 DB 错误检测 + `DbRequiredAlert` 组件
- [x] 2.3 Dashboard 图表增强（平台数据分布进度条）
- [x] 2.4 全局错误处理 / Loading / 空状态优化
- [x] 2.5 暗色主题完善（localStorage 持久化 + dark class 同步）
- [x] 2.6 Vite chunk 分割优化（vendor 拆分）
- [x] 2.7 文档更新 (DEVLOG + TODO)

## Phase 3: 真实功能实现 + 实时进度 ✅

- [x] 3.1 `search_creators()` 真实平台搜索 — B 站/微博/微信 HTTP API 适配器
- [x] 3.2 Subscription.vue 搜索结果展示 + 一键快捷订阅
- [x] 3.3 WebSocket `/ws/sync` 端点 + `sync_progress_queue` + 后台广播
- [x] 3.4 `feishu_service` 子进程 → WS 实时进度推送 (start/progress/complete)
- [x] 3.5 FeishuSync.vue 实时进度条 + 日志面板 + 自动重连
- [x] 3.6 Logs.vue WebSocket 自动重连
- [x] 3.7 Dashboard 30s 自动刷新
- [x] 3.8 构建验证 (Python AST + vue-tsc + vite build)
- [x] 3.9 DEVLOG/TODO 文档更新

## Phase 4: 配置系统修复 + E2E 测试 ✅

- [x] 4.0 诊断 WebUI 配置切换死循环 (PUT /config 依赖 get_db 在 CSV 模式返回 400)
- [x] 4.1 base_config.py 全量 _env() 环境变量支持
- [x] 4.2 config/__init__.py reload_from_env() 热重载
- [x] 4.3 api/deps.py get_db_optional 依赖 (无 DB 时返回 None)
- [x] 4.4 api/routers/config.py PUT/history 改用 get_db_optional
- [x] 4.5 ConfigManager.vue switch/number 类型转换修复
- [x] 4.6 .env.example 重写 (65+ 环境变量, 10 配置组)
- [x] 4.7 test/test_e2e_config.py E2E 集成测试 (25/25 passed)
- [x] 4.8 构建验证 (Python AST + vue-tsc + vite build)
- [x] 4.9 DEVLOG/TODO 文档更新

## Phase 5: 待办 (后续推进)
- [ ] 5.1 Dashboard 更多图表（时间趋势、采集频率折线图）
- [ ] 5.2 生产部署文档 / README 更新
- [ ] 5.3 小红书/抖音/快手搜索支持（需 cookie/浏览器会话）
- [x] 5.4 订阅触发采集 schema 阻塞修复（wechat 平台枚举补齐）
- [x] 5.4b 订阅触发采集增强（批量触发 + 执行状态可视化，内存态）
- [ ] 5.4c 订阅采集状态持久化（落库/重启恢复）
- [ ] 5.5 字段映射预览功能实现
- [x] 5.6 配置元数据单一真源 `config/config_meta.py`
- [x] 5.7 配置一致性检测脚本 `test/test_config_consistency.py`
- [x] 5.8 微信订阅触发最小 E2E `test/test_subscription_wechat_e2e.py`
- [x] 5.9 批量采集最小 E2E `test/test_subscription_batch_crawl_e2e.py`
- [x] 5.10 配置自检接口 `GET /config/validate`
- [x] 5.11 开发模式 WS 日志回归（Vite proxy ws + `test/test_ws_logs_smoke.py`）
- [x] 5.12 DB 模式数据浏览（DB browse API + DataExplorer 自适配 + `test/test_db_browse_e2e.py`）
- [x] 5.13 全面 smoke 回归套件（`test/test_webui_smoke_suite.py`）

