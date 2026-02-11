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

## Phase 2: 增强与完善 (待开始)
- [ ] 2.1 `search_creators()` 真实平台搜索（需各平台 API 适配器）
- [ ] 2.2 WebSocket 同步进度推送（FeishuSync 实时进度条）
- [ ] 2.3 Dashboard 图表增强（趋势图、平台分布）
- [ ] 2.4 全局错误处理 / Loading / 空状态优化
- [ ] 2.5 暗色主题完善
- [ ] 2.6 Vite chunk 分割优化（vendor 拆分）
- [ ] 2.7 生产部署文档 / README 更新
