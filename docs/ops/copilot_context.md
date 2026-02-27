# MediaCrawler Copilot Context 交接文档

> 本文档用于项目交接，供服务器部署与后续维护参考。

---

## 一、项目结构
- 后端：FastAPI（api/、base/、database/、store/）
- 前端：Vue3（webui-src/）
- 配置：config/、.env.example
- 调度：APScheduler（api/services/scheduler_service.py）
- 同步：飞书（api/services/feishu_service.py）
- 日志：logs/（如有）、执行历史（WebUI）

---

## 二、环境与依赖
- Python 3.9+
- Node.js 16+
- MongoDB、Redis
- pip 依赖：见 requirements.txt
- npm 依赖：见 package.json

---

## 三、配置说明
- .env.example 为环境变量模板，部署时需复制为 .env 并填写
- 所有配置读取统一通过 `config_service.get(key)`，禁止直接读 .env
- 关键配置项：
  - WECHAT_API_BASE_URL
  - WECHAT_AUTH_KEY
  - FEISHU_APP_TOKEN
  - MONGODB_URI
  - REDIS_URI

---

## 四、全流程说明
1. WebUI 配置页填写并保存所有必需项
2. 搜索并订阅微信创作者
3. 创建定时任务（微信采集/飞书同步）
4. 到点自动采集并推送数据
5. 日志与执行历史可查

---

## 五、部署流程
- 支持 Docker 与 systemd 双轨部署，详见 deploy_guide.md
- 推荐先用 Docker 快速部署，生产环境用 systemd

---

## 六、常见问题与排查
- 配置项未生效：确认通过 WebUI 保存，重启服务
- MongoDB/Redis 连接失败：检查 .env 与服务状态
- 日志异常：检查 logs/ 与 systemd 日志
- 前端构建失败：确认 Node.js 版本与依赖

---

## 七、会议纪要与MVP清单
- 路线与验收标准见 meetings/2026-02-27-full-team-open-discussion.md、MVP_checklist.md

---

> Copilot context 已交接，后续如需补充请参考 docs/ops/meetings/ 与 .env.example。