# Code-Reviewer — L2 验证模式库

> **层级：** L2 验证模式（Validated Patterns）
> **适用范围：** Code-Reviewer 角色积累的项目特有高频检查点
> **维护规范：** 见 `docs/team-playbook.md` §14
> **审查周期：** 每次 Major 版本复盘时审查
> **首批写入：** 2026-02-26 全体会议（Playbook v2.0 落地适配会议）

---

<!-- 新增条目模板（复制使用）：

## [模式名称]

**适用场景：** 何时使用这个模式
**验证场景：** 在哪个项目/版本中验证过（不超过 3 例）
**核心方法：** 怎么做（简洁，重点突出）
**注意事项：** 容易踩的坑
**状态：** 活跃 / 待观察 / 已废弃（YYYY-MM-DD）

-->

## 模式 1：依赖双文件漂移检测

**适用场景：** 审查任何向 Python 项目新增依赖的 PR/提交  
**验证场景：** MediaCrawler Sprint #002 P0-4 — `apscheduler`/`lark-oapi` 仅在 `requirements.txt`，`uv sync` 完全不读取，导致调度器和飞书同步在生产环境静默禁用  
**核心方法：** PR 中每出现一个新 `import xxx`，立即检查 `pyproject.toml` `[project] dependencies` 是否包含该包。如果只在 `requirements.txt` 中 → 🔴 阻断  
**注意事项：** `try/except ImportError` 静默吞掉缺失是 P0 级问题的标志性特征，出现时必须升级审查强度  
**状态：** 活跃

---

## 模式 2：FastAPI @app.on_event 废弃标注

**适用场景：** 审查所有使用 FastAPI 0.95+ 的代码  
**验证场景：** MediaCrawler `api/main.py` — 当前使用 `@app.on_event("startup")` / `@app.on_event("shutdown")`，有 deprecation warning（P1-2，待修复）  
**核心方法：** 发现 `@app.on_event` 装饰器时，标注为 🟡 警告，建议迁移到 `@asynccontextmanager` + `lifespan` 模式。FastAPI 官方文档：https://fastapi.tiangolo.com/advanced/events/#lifespan  
**注意事项：** 当前版本仍然可用，不阻断运行，定级为 🟡 而非 🔴，但每次触碰 `api/main.py` 时应推动修复  
**状态：** 活跃

---

## 模式 3：CORS allow_origins 硬编码检测

**适用场景：** 审查 FastAPI / Flask / Starlette 的 CORS 配置  
**验证场景：** MediaCrawler Sprint #002 P0-3 — 原 CORS 配置硬编码 `http://localhost:3000` 等本地地址，服务器部署后所有跨域请求直接被拒绝  
**核心方法：** 检查 `CORSMiddleware` 的 `allow_origins` 参数：如果是字面量列表 `["http://localhost:xxx"]` → 🔴 阻断。正确做法是读取环境变量：`os.environ.get("ALLOWED_ORIGINS", "").split(",")`  
**注意事项：** 本地开发时 CORS 错误不会出现（origin 匹配），只有部署到生产服务器才暴露。属于典型"本地测没问题，上线出问题"类型  
**状态：** 活跃

---

## 模式 4：SAVE_DATA_OPTION 配置完整性检查（MediaCrawler 特有）

**适用场景：** 审查 MediaCrawler 项目任何涉及数据库或数据存储的 PR  
**验证场景：** MediaCrawler 已知最高风险项 — `SAVE_DATA_OPTION` 未设置为 `sqlite` 时，所有 WebUI DB 操作静默失败（无任何报错，功能表现为空数据）  
**核心方法：** 审查涉及 `StoreFactory`、`db_session`、`WebUI` 功能的代码时，确认：① `.env.example` 中 `SAVE_DATA_OPTION` 有明确的警告注释 ② 相关文档（如 deploy 指南）中有"首次部署必须设置此项"的提示  
**注意事项：** 这是 MediaCrawler 业务特有的"配置陷阱"，在七维度通用模型中归属"功能正确性"维度（🔴 级）；通用项目的 Reviewer 不会主动检查这一点  
**状态：** 活跃
