"""飞书相关配置（供 WebUI 与同步服务共享）"""

import os

FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_BITABLE_APP_TOKEN = os.getenv("FEISHU_BITABLE_APP_TOKEN", "")
FEISHU_TABLE_ID = os.getenv("FEISHU_TABLE_ID", "")
FEISHU_BATCH_SIZE = int(os.getenv("FEISHU_BATCH_SIZE", "50"))

# 兼容旧键（逐步废弃）
if not FEISHU_BITABLE_APP_TOKEN:
	FEISHU_BITABLE_APP_TOKEN = os.getenv("FEISHU_APP_TOKEN", "")
