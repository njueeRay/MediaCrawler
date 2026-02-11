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

## Phase 1: 配置管理 + 仪表盘 (5天)
- [ ] 1.1 ConfigService 完整实现
- [ ] 1.2 连接测试端点
- [ ] 1.3 ConfigManager.vue 页面
- [ ] 1.4 Dashboard 数据聚合 API
- [ ] 1.5 Dashboard.vue 页面

## Phase 2: 订阅管理 (5天)
- [ ] 2.1 Subscription 模型（已在 Phase 0 创建）
- [ ] 2.2 SubscriptionService 完整实现
- [ ] 2.3 搜索创作者页面
- [ ] 2.4 订阅列表页面
- [ ] 2.5 创作者详情页面

## Phase 3: 数据浏览 + 字段映射 (7天)
- [ ] 3.1 数据查询 API（DB 查询 + 分页 + 过滤）
- [ ] 3.2 FieldMapping 模型（已在 Phase 0 创建）
- [ ] 3.3 FieldMappingService 完整实现
- [ ] 3.4 默认映射种子数据（已在 Phase 0 创建）
- [ ] 3.5 DataExplorer.vue
- [ ] 3.6 FieldMapping.vue
- [ ] 3.7 映射 ↔ 数据浏览集成

## Phase 4: 飞书同步 (5天)
- [ ] 4.1 FeishuService 完整实现
- [ ] 4.2 异步同步 + WebSocket 进度
- [ ] 4.3 同步历史 API
- [ ] 4.4 FeishuSync.vue
- [ ] 4.5 同步进度 + 历史

## Phase 5: 任务调度 (5天)
- [ ] 5.1 APScheduler 集成
- [ ] 5.2 ScheduledTask + TaskExecution 模型（已在 Phase 0 创建）
- [ ] 5.3 SchedulerService 完整实现
- [ ] 5.4 TaskScheduler.vue
- [ ] 5.5 执行历史 + 调度状态

## Phase 6: 日志监控 + 优化 (5天)
- [ ] 6.1 Logs.vue（WebSocket 日志流）
- [ ] 6.2 仪表盘增强
- [ ] 6.3 全局错误处理 / Loading / 空状态
- [ ] 6.4 暗色主题
- [ ] 6.5 生产构建 + README
