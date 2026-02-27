## 变更说明

<!-- 简要描述本 PR 做了什么 -->

## 关联 Issue / 会议纪要

<!-- Closes #xxx 或 会议纪要链接 -->

## 变更类型

- [ ] 🐛 Bug 修复
- [ ] ✨ 新功能
- [ ] ♻️ 重构
- [ ] 📝 文档
- [ ] 🔧 CI/配置

---

## 合并前检查清单

### 代码质量
- [ ] CI 全部通过（lint + type-check + build-frontend）
- [ ] 无 `except Exception: pass` 静默吞异常
- [ ] 无硬编码密钥或 token（`WECHAT_AUTH_KEY` 等必须走环境变量）
- [ ] 新增代码的配置读取走 `config_service.get(key)` 而非直接 `from config import *`

### 功能验证
- [ ] 本地 `python -m api.main` 启动无报错
- [ ] 相关功能页面手工验证通过
- [ ] （若涉及 Pipeline）对应任务类型执行历史可见且日志完整

### MVP 验收（合并到 main 前额外确认）
- [ ] MVP 6 步端到端验收通过（微信全流程）
- [ ] `CHANGELOG.md` 已更新
- [ ] `pyproject.toml` 版本号已更新（如需打 tag）
