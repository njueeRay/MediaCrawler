# MediaCrawler MVP 验收清单

> 本清单用于用户端到端验收，确保微信平台全流程跑通。

## 1. 配置管理
- [ ] WebUI 配置页填写并保存所有必需项（WECHAT_API_BASE_URL、WECHAT_AUTH_KEY、FEISHU_APP_TOKEN等）
- [ ] 测试连接全部通过（微信、飞书、数据库）

## 2. 订阅管理
- [ ] 搜索微信创作者（如“sparklab”），成功返回结果
- [ ] 添加订阅，订阅列表显示新增项

## 3. 任务调度
- [ ] 创建定时任务（task_type=subscription_crawl，platform=wechat，schedule_type=cron/interval）
- [ ] 任务列表显示新任务，状态为“活跃”

## 4. 自动采集
- [ ] 到点自动执行任务，采集日志可在执行历史中查看
- [ ] 采集结果入库，数据浏览页可见

## 5. 飞书同步
- [ ] 创建同步任务（task_type=sync/combo，platform=wechat）
- [ ] 到点自动推送数据到飞书多维表格
- [ ] 飞书表格中可见新数据

## 6. 日志与健康监控
- [ ] 执行历史页可查任务日志
- [ ] Dashboard 显示平台健康状态（微信/飞书/数据库）

---

> 验收通过后，进入部署阶段。