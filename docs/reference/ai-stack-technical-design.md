# AI Stack 技术设计（feat/ai_stack）

- 版本：v0.1-draft
- 日期：2026-03-17
- 状态：草案（待评审）
- 目标：以本地 AI 编排栈替代飞书 AI 自动化链路

## 1. 范围与目标

### 1.1 目标

1. 本地执行 AI 文本分析列与图片理解列。
2. 支持多列顺序触发（依赖 DAG）。
3. 支持 data_arrival 自动触发。
4. 支持可追溯执行日志、重试与幂等。

### 1.2 非目标

1. 本阶段不做可视化拖拽编排器。
2. 本阶段不做 Docker/Linux 生产部署验证（backlog）。
3. 本阶段不替换全部历史飞书流程，仅覆盖 MVP 场景。

## 2. 总体架构

```text
Data Arrival / Manual / Schedule Trigger
                |
                v
        AI Trigger Service
                |
                v
       AI Pipeline Orchestrator
          |             |
          |             +--> Template Engine (DSL 渲染)
          |
          +--> AI Gateway (OpenRouter)
                |
                v
          Result Writer (本地回写)
                |
                v
   Execution/Audit Store（执行与审计）
```

## 3. 模块设计

### 3.1 AI Gateway

职责：
- OpenRouter API 统一调用封装。
- 模型选择、超时、重试、限流、错误分类。
- 统一返回结构（output/token/cost/latency）。

建议路径：
- `api/services/ai_gateway.py`

核心接口：
```python
class AIGateway:
    async def run_text(self, *, model: str, prompt: str, temperature: float, max_tokens: int) -> dict: ...
    async def run_vision(self, *, model: str, prompt: str, images: list[str], max_tokens: int) -> dict: ...
```

### 3.2 Template Engine

职责：
- 解析模板 DSL 与变量引用。
- 渲染输入上下文（record/steps/system）。
- 提供发布前静态校验。

建议路径：
- `api/services/ai_template_engine.py`

变量命名空间：
- `record.*`：当前记录字段
- `steps.<step_id>.output.*`：前序步骤输出
- `system.now` / `system.task_id`

### 3.3 Orchestrator

职责：
- DAG 拓扑排序。
- 逐 step 执行（支持无依赖并行）。
- 失败传播、重试、断点续跑。

建议路径：
- `api/services/ai_orchestrator.py`

### 3.4 Trigger Service

触发类型：
- `data_arrival`（新数据自动触发）
- `manual`
- `schedule`

建议路径：
- `api/services/ai_trigger_service.py`

### 3.5 Result Writer

职责：
- 将步骤结果写入本地业务字段。
- 维护 step 级快照与状态。
- 执行幂等冲突处理。

建议路径：
- `api/services/ai_result_writer.py`

## 4. DSL 设计（MVP）

```jsonc
{
  "template_id": "wechat_content_pipeline",
  "version": "1.0.0",
  "steps": [
    {
      "step_id": "text_analysis",
      "type": "ai_text_analysis",
      "input": {
        "context": ["{{record.title}}", "{{record.content}}", "{{record.author_name}}"]
      },
      "prompt": "请基于以下内容生成摘要、观点、风险点，输出 JSON。\n{{input.context}}",
      "model": "openai/gpt-4o-mini",
      "output": {
        "target_field": "ai_text_analysis",
        "format": "json"
      },
      "retry": 1
    },
    {
      "step_id": "image_understanding",
      "type": "ai_image_understanding",
      "depends_on": ["text_analysis"],
      "input": {
        "images": ["{{record.cover}}"],
        "hint": "{{steps.text_analysis.output.summary}}"
      },
      "prompt": "结合文本摘要和图片，输出图文一致性评分（0-100）及理由。",
      "model": "openai/gpt-4o-mini",
      "output": {
        "target_field": "ai_image_understanding",
        "format": "json"
      },
      "retry": 1
    }
  ]
}
```

校验规则：
1. `step_id` 全局唯一。
2. `depends_on` 引用必须存在。
3. 禁止循环依赖。
4. `output.target_field` 必填。

## 5. 数据模型草案

### 5.1 ai_template
- `id` PK
- `template_id` unique
- `name`
- `status` (`draft`/`published`/`archived`)
- `created_by`
- `created_at`

### 5.2 ai_template_version
- `id` PK
- `template_id` FK
- `version`
- `dsl_json` (TEXT/JSON)
- `checksum`
- `is_active`
- `published_at`

### 5.3 ai_execution
- `id` PK
- `trigger_type` (`data_arrival`/`manual`/`schedule`)
- `task_execution_id` (可选，挂接现有调度)
- `template_version_id` FK
- `record_pk`
- `status` (`pending`/`running`/`success`/`failed`/`partial`)
- `started_at` / `finished_at`
- `error_message`

### 5.4 ai_step_execution
- `id` PK
- `execution_id` FK
- `step_id`
- `step_type`
- `status`
- `retry_count`
- `model_name`
- `input_hash`
- `idempotency_key` unique
- `input_snapshot_json`
- `output_snapshot_json`
- `token_in` / `token_out`
- `cost_estimate`
- `latency_ms`
- `error_message`

### 5.5 ai_event_inbox
- `id` PK
- `event_type`
- `source_table`
- `source_pk`
- `payload_json`
- `dedupe_key` unique
- `status`
- `created_at` / `consumed_at`

## 6. API 草案

### 6.1 模板管理
- `POST /api/ai/templates`
- `POST /api/ai/templates/{template_id}/versions`
- `POST /api/ai/templates/{template_id}/publish`
- `GET /api/ai/templates`

### 6.2 执行与触发
- `POST /api/ai/trigger/manual`
- `POST /api/ai/trigger/data-arrival`
- `GET /api/ai/executions`
- `GET /api/ai/executions/{id}`
- `POST /api/ai/executions/{id}/retry-failed-steps`

### 6.3 预检
- `POST /api/ai/templates/validate`
- `POST /api/ai/templates/render-preview`

## 7. 幂等、重试与错误策略

### 7.1 幂等
- `idempotency_key = template_version_id + record_pk + step_id + input_hash`
- 命中成功记录且输入未变：跳过执行。

### 7.2 重试
- 网关层：429/5xx 指数退避（2s/5s/10s）。
- 步骤层：`retry` 配置（默认 1）。

### 7.3 错误分类
- `TEMPLATE_ERROR`（模板变量缺失）
- `MODEL_ERROR`（模型调用失败）
- `TIMEOUT_ERROR`
- `WRITEBACK_ERROR`
- `DEPENDENCY_BLOCKED`

## 8. 里程碑与 DoD

### Week 1
- 完成网关 + 模板渲染 + 单步文本分析闭环。
- DoD：文本 step 可执行并入库 execution/step_execution。

### Week 2
- 完成图片理解 step + DAG 执行 + data_arrival 触发。
- DoD：两步依赖链稳定运行，失败可重试。

### Week 3
- 完成模板版本化 + 预检 + 输入输出快照。
- DoD：执行可追溯到模板版本，预检可发现依赖错误。

### Week 4
- 联调现有任务系统 + 灰度 + 回退开关。
- DoD：可并行跑旧链路并对比结果，回退路径可用。

## 9. Backlog（本阶段不阻塞）

1. Docker/Linux 正式部署验证
2. 可视化 DAG 编排器
3. 多模型自动路由策略
4. 质量评测与提示词 A/B 实验平台
