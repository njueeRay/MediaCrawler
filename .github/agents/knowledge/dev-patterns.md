# Dev — L2 验证模式库

> **层级：** L2 验证模式（Validated Patterns）
> **适用范围：** Dev 角色在实现过程中验证过的代码片段模板、依赖兼容性坑
> **维护规范：** 见 `docs/team-playbook.md` §14
> **审查周期：** 每次 Major 版本复盘时审查

---

<!-- 新增条目模板（复制使用）：

## [模式名称]

**适用场景：** 何时使用这个模式
**验证场景：** 在哪个项目/版本中验证过（不超过 3 例）
**核心方法：** 怎么做（简洁，重点突出）
**注意事项：** 容易踩的坑
**状态：** 活跃 / 待观察 / 已废弃（YYYY-MM-DD）

-->

## uv 项目依赖必须在 pyproject.toml 声明

**适用场景：** 所有使用 uv 作为包管理器的 Python 项目  
**验证场景：** MediaCrawler Sprint #002 P0-4 修复（2026-02-26）  
**核心方法：** `uv sync` 只读取 `pyproject.toml`，完全不读 `requirements.txt`。新增依赖必须写入 `pyproject.toml` 的 `[project] dependencies` 列表，格式为 `"pkg>=x.y.z"`。`requirements.txt` 降格为参考文档，可以保留但不产生效果  
**注意事项：** `try/except ImportError` 会静默吞掉缺失的包（看起来功能被禁用但无报错），这是 P0 级问题的常见掩盖形式  
**状态：** 活跃

## APScheduler 任务重启后恢复模式

**适用场景：** FastAPI + APScheduler 的 WebUI 应用  
**验证场景：** MediaCrawler Sprint #002 P0-1 修复（2026-02-26）  
**核心方法：** APScheduler 不持久化任务，进程重启后内存中的 job 清空。必须在 startup 事件中查询 DB 里所有 `is_active=True` 的任务，逐一调用 `scheduler.add_job()` 恢复注册。参考 `api/main.py` `webui_startup()` 实现  
**注意事项：** 恢复逻辑必须在 scheduler `start()` 之后执行，否则 `add_job` 会报 scheduler 未启动的错  
**状态：** 活跃
