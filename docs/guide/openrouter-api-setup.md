# OpenRouter API 获取与接入教程

本文用于 MediaCrawler AI Stack（MVP）接入 OpenRouter。

## 1. 创建 OpenRouter API Key

1. 打开 https://openrouter.ai
2. 注册或登录账号
3. 进入 Key 管理页面（Dashboard -> Keys）
4. 点击 Create Key，生成新的 API Key
5. 复制并妥善保管（只会展示一次）

## 2. 在项目中配置环境变量

在项目 `.env`（或系统环境变量）中添加：

```bash
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxx
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_TEXT_MODEL=openai/gpt-4o-mini
OPENROUTER_VISION_MODEL=openai/gpt-4o-mini
```

> 如果暂时没有 API Key，MVP 路由支持 mock 运行（`use_mock_if_no_key=true`）。

## 3. 验证是否生效

### 方式 A：调用引导接口

```bash
GET /api/ai/openrouter/setup-guide
```

### 方式 B：跑一次模板执行

```json
POST /api/ai/executions/run
{
  "template": {
    "template_id": "demo",
    "version": "1.0.0",
    "steps": [
      {
        "step_id": "text_analysis",
        "type": "ai_text_analysis",
        "input": {},
        "prompt": "请总结：{{record.content}}",
        "output": {"target_field": "ai_text_analysis", "format": "text"},
        "retry": 1
      }
    ]
  },
  "record": {"content": "这是一个测试文本"},
  "use_mock_if_no_key": false
}
```

若返回 `执行成功`，说明 Key 与模型配置有效。

## 4. 常见问题

1. 401 Unauthorized
- API Key 错误或未生效，检查 `OPENROUTER_API_KEY`。

2. 429 Too Many Requests
- 调用频率过高，建议降低并发或添加重试退避。

3. 模型不存在
- 检查模型名是否可用，替换为 OpenRouter 当前支持模型。

4. 网络连接失败
- 检查代理、DNS 或公司网络策略。
