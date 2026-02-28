#!/usr/bin/env bash
# ============================================================
# Step 3: 从飞书表1拉取数据 → 解析 JSON 列 → 推送到表2
# cron: 0 4 * * *  (北京时间每天 12:00)
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

TEMP_ENV=$(mktemp /tmp/wechat_parse_XXXXXX.env)
trap 'rm -f "${TEMP_ENV}"' EXIT

cp "${BASE_ENV}" "${TEMP_ENV}"

cat >> "${TEMP_ENV}" << EOF

# --- cron override ---
RUN_CRAWL=0
RUN_SYNC_TABLE1=0
RUN_PARSE_TO_TABLE2=1
EOF

echo "[$(date '+%F %T')] === run_parse_push.sh START ==="
exec "${SCRIPT_DIR}/wechat_feishu_workflow.sh" "${TEMP_ENV}"
