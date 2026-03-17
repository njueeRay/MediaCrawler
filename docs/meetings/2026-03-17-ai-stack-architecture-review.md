# AI Stack 改造架构评审会（brain 召集）

- 时间：2026-03-17
- 参会：brain / pm / dev / researcher / code-reviewer
- 分支：feat/ai_stack
- 背景：将“飞书AI自动化链路”迁移为“本地AI编排链路（OpenRouter）”

## 会话起始 Roadmap（固定）

- [x] 需求收敛：确认本地替代飞书AI的目标与边界
- [x] PM 输出需求说明：背景/目标/P0-P1/验收/风险/里程碑
- [x] brain 召集团队会议并形成统一方案
- [x] 创建分支 feat/ai_stack
- [ ] 详细技术设计落地（模块、表结构、DSL、触发器）
- [ ] MVP 开发与联调
- [ ] 灰度验收与切换

## 结论

1. 主链路改造方向确定：
   本地入库 -> Trigger -> Pipeline Orchestrator -> Template Engine -> OpenRouter Gateway -> Result Writer -> 审计日志。
2. MVP 必做能力确定：
   - 图片理解列
   - AI 文本分析列（引用图片理解输出作为上下文）
   - 多列顺序触发（依赖前置输出）
   - 新数据自动触发（data_arrival）
3. 约束确认：
   Docker/Linux 部署验证移入 backlog，不阻塞当前改造主线。

## 方案要点（摘要）

### 1) 模块边界

- AI Gateway：统一封装 OpenRouter 调用、超时重试、成本统计
- Template Engine：模板渲染与变量引用（record/system/steps）
- Orchestrator：DAG 拓扑执行、依赖控制、失败策略
- Trigger Service：数据到达/手动/定时触发
- Result Writer：本地字段回写（飞书转下游可选）
- Observability：执行链路日志、快照、错误分类、重试轨迹

### 2) 幂等与重试

- 幂等键：task_id + record_pk + template_version + step_id + input_hash
- 规则：成功且输入未变时跳过；支持失败步骤重跑
- 重试：网关层指数退避，业务层按 step 配置重试

### 3) DSL 最小规范（MVP）

- 字段引用：{{record.title}} / {{record.content}} / {{record.images[0]}}
- 依赖引用：{{steps.step_id.output.xxx}}
- 类型：ai_text_analysis / ai_image_understanding
- 输出：声明 target_field + format

## MVP 里程碑（4 周）

- Week 1：OpenRouter 网关 + 模板解析最小闭环 + 执行记录入库
- Week 2：DAG 执行（图片 step → 文本 step）+ data_arrival 触发 + 幂等/断点续跑
- Week 3：模板版本化 + 输入输出快照 + 成本/耗时看板
- Week 4：联调验收 + 灰度切换 + 回退开关

## 行动项

1. PM：输出需求冻结版与验收清单（P0/P1）
2. Dev：起草技术设计文档（架构/表设计/DSL/API）
3. Researcher：给出 OpenRouter 文本/视觉模型组合建议与成本基线
4. Code-Reviewer：定义阻断门禁（幂等、版本绑定、回退策略）

## DoD（本阶段）

- [ ] 设计文档完成并过评审
- [ ] schema 与 migration 草案完成
- [ ] 第一个端到端样例（图片列 + 文本列 + 顺序依赖）跑通
- [ ] 执行日志可追溯到模板版本与 step 级输入输出
