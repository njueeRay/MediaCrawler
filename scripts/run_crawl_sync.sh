#!/usr/bin/env bash
# ============================================================
# Step 1+2: 采集微信订阅创作者近一个月文章 → 同步到飞书表1
# cron: 0 16 * * *  (北京时间每天 00:00)
# ============================================================
set -euo pipefail

export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
# 激活 Python venv（提供 python 命令 + 已安装的依赖）
VENV_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/.venv"
[[ -f "${VENV_DIR}/bin/activate" ]] && source "${VENV_DIR}/bin/activate"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
BASE_ENV="${SCRIPT_DIR}/wechat_feishu_workflow.env"
LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "${LOG_DIR}"

# 生成临时 env（继承 base env，末尾追加覆盖项）
TEMP_ENV=$(mktemp /tmp/wechat_crawl_XXXXXX.env)
trap 'rm -f "${TEMP_ENV}"' EXIT

cp "${BASE_ENV}" "${TEMP_ENV}"

# 动态计算近 30 天日期范围 + 覆盖 RUN 标志
cat >> "${TEMP_ENV}" << EOF

# --- cron override ---
RUN_CRAWL=1
RUN_SYNC_TABLE1=1
RUN_PARSE_TO_TABLE2=0
WECHAT_ARTICLE_DATE_START="$(date -d '30 days ago' +%Y-%m-%d)"
WECHAT_ARTICLE_DATE_END="$(date +%Y-%m-%d)"
SAVE_DATA_OPTION="sqlite"
EOF

echo "[$(date '+%F %T')] === run_crawl_sync.sh START ==="
exec "${SCRIPT_DIR}/wechat_feishu_workflow.sh" "${TEMP_ENV}"
