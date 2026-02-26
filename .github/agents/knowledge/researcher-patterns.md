# Researcher — L2 验证模式库

> **层级：** L2 验证模式（Validated Patterns）
> **适用范围：** Researcher 角色积累的可信信息源、常见技术选型决策树
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

## pyproject.toml vs requirements.txt 的调研优先级判断

**适用场景：** 加入任何使用 uv/poetry 的 Python 项目时评估依赖完整性  
**验证场景：** MediaCrawler Sprint #002 Researcher 报告（2026-02-26），发现 P0-4  
**核心方法：** 调研顺序：① 查看 `pyproject.toml` 的 `[project] dependencies`（uv 唯一真相源）→ ② 与 `requirements.txt` 对比 → ③ 运行 `uv pip list` 确认实际已安装版本。三者不一致时为 P0 级风险  
**注意事项：** 检查时重点关注有 `try/except ImportError` 保护的 import 语句——这些是"静默缺失"的高发区  
**状态：** 活跃

## fork 仓库的团队权限边界判断

**适用场景：** 团队在他人 fork 仓库上工作时评估操作权限  
**验证场景：** MediaCrawler Playbook v2.0 适配会议（2026-02-26）—— §15/§16 适用性判断  
**核心方法：** 检查两点：① 仓库 owner 是否为团队成员 → 否则 GitHub API 品牌化操作（设置 Topics/Description）需要 owner 授权；② 工作分支是否为 fork 的 dev 分支 → 则 Release/Tag 操作应在 owner 确认后执行  
**注意事项：** Playbook 中品牌化规范（§16）默认团队是 owner，fork 场景需要显式确认权限边界  
**状态：** 活跃
