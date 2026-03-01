"""飞书相关配置（供 WebUI 与同步服务共享）"""

import os

FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_BITABLE_APP_TOKEN = os.getenv("FEISHU_BITABLE_APP_TOKEN", "")
FEISHU_TABLE_ID = os.getenv("FEISHU_TABLE_ID", "")
FEISHU_BATCH_SIZE = int(os.getenv("FEISHU_BATCH_SIZE", "50"))

# 任务失败告警机器人 Webhook（留空则不发送告警）
# 设置方法: 在飞书群内新增机器人 → 复制 Webhook URL → 写入 .env:
#   FEISHU_ALERT_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
FEISHU_ALERT_WEBHOOK_URL = os.getenv("FEISHU_ALERT_WEBHOOK_URL", "")

# 兼容旧键（逐步废弃）
if not FEISHU_BITABLE_APP_TOKEN:
	FEISHU_BITABLE_APP_TOKEN = os.getenv("FEISHU_APP_TOKEN", "")
