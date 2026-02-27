#!/usr/bin/env bash
# ============================================================
# 虚拟测试：模拟 cron 两次触发（第1次=0点采集同步，第2次=12点解析推送）
# 用法: bash scripts/run_test_simulation.sh [--skip-crawl]
# ============================================================
set -euo pipefail

export PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
LOG_DIR="${PROJECT_ROOT}/logs"
mkdir -p "${LOG_DIR}"
LOG_FILE="${LOG_DIR}/test_simulation_$(date +%Y%m%d_%H%M%S).log"

SKIP_CRAWL=0
for arg in "$@"; do
  [[ "$arg" == "--skip-crawl" ]] && SKIP_CRAWL=1
done

log() { printf '[%s] %s\n' "$(date '+%F %T')" "$*" | tee -a "${LOG_FILE}"; }

# ── 生成第1次触发的测试 env（0点：爬取+同步表1，缩小范围） ──
TEMP_ENV_1=$(mktemp /tmp/wechat_test_crawl_XXXXXX.env)
trap 'rm -f "${TEMP_ENV_1}" "${TEMP_ENV_2:-}"' EXIT

cp "${SCRIPT_DIR}/wechat_feishu_workflow.env" "${TEMP_ENV_1}"
CRAWL_FLAG=$([ "${SKIP_CRAWL}" = "1" ] && echo "0" || echo "1")
cat >> "${TEMP_ENV_1}" << EOF

# --- TEST SIMULATION OVERRIDE (0点触发) ---
RUN_CRAWL=${CRAWL_FLAG}
RUN_SYNC_TABLE1=1
RUN_PARSE_TO_TABLE2=0
WECHAT_ARTICLE_DATE_START="$(date -d '7 days ago' +%Y-%m-%d)"
WECHAT_ARTICLE_DATE_END="$(date +%Y-%m-%d)"
WECHAT_MAX_ARTICLES_PER_CREATOR=2
SAVE_DATA_OPTION="sqlite"
EOF

# ── 生成第2次触发的测试 env（12点：读表1+解析+推表2） ──
TEMP_ENV_2=$(mktemp /tmp/wechat_test_parse_XXXXXX.env)
cp "${SCRIPT_DIR}/wechat_feishu_workflow.env" "${TEMP_ENV_2}"
cat >> "${TEMP_ENV_2}" << EOF

# --- TEST SIMULATION OVERRIDE (12点触发) ---
RUN_CRAWL=0
RUN_SYNC_TABLE1=0
RUN_PARSE_TO_TABLE2=1
EOF

echo "" | tee -a "${LOG_FILE}"
log "============================================="
log "  媒体爬虫 Cron 虚拟测试开始"
log "  近7天 / 每创作者最多2篇"
log "  日志文件: ${LOG_FILE}"
log "============================================="
echo "" | tee -a "${LOG_FILE}"

# ═══════════════════════════════════════════════
# 模拟第1次触发：0点 run_crawl_sync
# ═══════════════════════════════════════════════
log "▶ [第1次触发] 0点 - 爬取 + 同步到飞书表1"

cd "${PROJECT_ROOT}"
{ "${SCRIPT_DIR}/wechat_feishu_workflow.sh" "${TEMP_ENV_1}" 2>&1; } | tee -a "${LOG_FILE}"
EXIT1=${PIPESTATUS[0]}

echo "" | tee -a "${LOG_FILE}"
if [[ ${EXIT1} -eq 0 ]]; then
  log "✅ 第1次触发成功（爬取+同步表1）"
else
  log "❌ 第1次触发失败（exit=${EXIT1}）— 后续步骤仍然继续..."
fi
echo "" | tee -a "${LOG_FILE}"

# ═══════════════════════════════════════════════
# 模拟第2次触发：12点 run_parse_push
# ═══════════════════════════════════════════════
log "▶ [第2次触发] 12点 - 读取表1 → 解析 JSON → 推送到表2"

{ "${SCRIPT_DIR}/wechat_feishu_workflow.sh" "${TEMP_ENV_2}" 2>&1; } | tee -a "${LOG_FILE}"
EXIT2=${PIPESTATUS[0]}

echo "" | tee -a "${LOG_FILE}"
if [[ ${EXIT2} -eq 0 ]]; then
  log "✅ 第2次触发成功（解析+推表2）"
else
  log "❌ 第2次触发失败（exit=${EXIT2}）"
fi
echo "" | tee -a "${LOG_FILE}"

log "============================================="
if [[ ${EXIT1} -eq 0 && ${EXIT2} -eq 0 ]]; then
  log "🎉 全流程测试通过！cron 逻辑验证 OK"
else
  log "⚠️  有步骤失败，请检查日志: ${LOG_FILE}"
fi
log "============================================="
