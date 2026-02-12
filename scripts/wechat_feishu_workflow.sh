#!/usr/bin/env bash
set -euo pipefail

# 微信订阅全流程：
# 1) creator 模式爬取指定日期范围内容
# 2) 自动同步到飞书表1（原始数据）
# 3) 从表1读取指定字段（包含 JSON 列）导出 CSV
# 4) 解析 JSON 列并上传到飞书表2

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT_DEFAULT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${1:-${SCRIPT_DIR}/wechat_feishu_workflow.env}"

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
fi

PROJECT_ROOT="${PROJECT_ROOT:-${PROJECT_ROOT_DEFAULT}}"
cd "${PROJECT_ROOT}"

log() {
  printf '[%s] %s\n' "$(date '+%F %T')" "$*"
}

die() {
  echo "[ERROR] $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "缺少命令: $1"
}

require_cmd uv
require_cmd python

RUN_CRAWL="${RUN_CRAWL:-1}"
RUN_SYNC_TABLE1="${RUN_SYNC_TABLE1:-1}"
RUN_PARSE_TO_TABLE2="${RUN_PARSE_TO_TABLE2:-1}"

LOGIN_TYPE="${LOGIN_TYPE:-cookie}"
SAVE_DATA_OPTION="${SAVE_DATA_OPTION:-csv}"
CREATOR_IDS="${CREATOR_IDS:-}"
WECHAT_ARTICLE_DATE_START="${WECHAT_ARTICLE_DATE_START:-}"
WECHAT_ARTICLE_DATE_END="${WECHAT_ARTICLE_DATE_END:-}"
WECHAT_MAX_ARTICLES_PER_CREATOR="${WECHAT_MAX_ARTICLES_PER_CREATOR:-10}"
WECHAT_CRAWL_TAG="${WECHAT_CRAWL_TAG:-}"

TABLE1_ID="${TABLE1_ID:-}"
TABLE1_BATCH_SIZE="${TABLE1_BATCH_SIZE:-50}"
TABLE1_SOURCE_CSV="${TABLE1_SOURCE_CSV:-}"

TABLE1_EXPORT_CSV="${TABLE1_EXPORT_CSV:-data/wechat/csv/table1_export_for_parse.csv}"
TABLE1_SELECT_FIELDS="${TABLE1_SELECT_FIELDS:-文章ID,标题}"
TABLE1_FILTER_FIELD="${TABLE1_FILTER_FIELD:-}"
TABLE1_FILTER_OPERATOR="${TABLE1_FILTER_OPERATOR:-}"
TABLE1_FILTER_VALUES="${TABLE1_FILTER_VALUES:-}"
TABLE1_FILTER_CONJUNCTION="${TABLE1_FILTER_CONJUNCTION:-or}"

TABLE2_ID="${TABLE2_ID:-}"
JSON_COLUMNS="${JSON_COLUMNS:-}"
JSON_KEEP_COLUMNS="${JSON_KEEP_COLUMNS:-}"
TABLE2_PRIMARY="${TABLE2_PRIMARY:-}"
JSON_FLATTEN_SEP="${JSON_FLATTEN_SEP:-.}"
TABLE2_BATCH_SIZE="${TABLE2_BATCH_SIZE:-50}"

export WECHAT_ARTICLE_DATE_START WECHAT_ARTICLE_DATE_END WECHAT_MAX_ARTICLES_PER_CREATOR WECHAT_CRAWL_TAG

if [[ -n "${FEISHU_APP_ID:-}" ]]; then export FEISHU_APP_ID; fi
if [[ -n "${FEISHU_APP_SECRET:-}" ]]; then export FEISHU_APP_SECRET; fi
if [[ -n "${FEISHU_APP_TOKEN:-}" ]]; then export FEISHU_APP_TOKEN; fi

find_latest_contents_csv() {
  local csv_file
  csv_file="$(ls -t data/wechat/csv/*_contents.csv 2>/dev/null | head -n1 || true)"
  if [[ -z "${csv_file}" ]]; then
    die "未找到 data/wechat/csv/*_contents.csv，请先执行爬取或指定 TABLE1_SOURCE_CSV"
  fi
  echo "${csv_file}"
}

run_crawler() {
  log "步骤1/4：开始爬虫（wechat creator）"

  local cmd=(uv run python main.py --platform wechat --type creator --lt "${LOGIN_TYPE}" --save_data_option "${SAVE_DATA_OPTION}")
  if [[ -n "${CREATOR_IDS}" ]]; then
    cmd+=(--creator_id "${CREATOR_IDS}")
  fi

  "${cmd[@]}"
  log "步骤1/4：爬虫完成"
}

sync_table1() {
  [[ -n "${TABLE1_ID}" ]] || die "TABLE1_ID 不能为空（用于同步表1）"

  local source_csv="${TABLE1_SOURCE_CSV}"
  if [[ -z "${source_csv}" ]]; then
    source_csv="$(find_latest_contents_csv)"
  fi
  [[ -f "${source_csv}" ]] || die "表1源文件不存在: ${source_csv}"

  log "步骤2/4：同步到表1，源文件=${source_csv}"

  uv run python sync_to_feishu.py \
    --platform wechat \
    --file "${source_csv}" \
    --append-table-id "${TABLE1_ID}" \
    --batch-size "${TABLE1_BATCH_SIZE}"

  log "步骤2/4：表1同步完成"
}

read_table1() {
  [[ -n "${TABLE1_ID}" ]] || die "TABLE1_ID 不能为空（用于读取表1）"

  mkdir -p "$(dirname "${TABLE1_EXPORT_CSV}")"
  log "步骤3/4：读取表1并导出 CSV -> ${TABLE1_EXPORT_CSV}"

  local cmd=(uv run python feishu_sync/read_from_feishu.py
    --table-id "${TABLE1_ID}"
    --select-fields "${TABLE1_SELECT_FIELDS}"
    --output-csv "${TABLE1_EXPORT_CSV}")

  if [[ -n "${TABLE1_FILTER_FIELD}" ]]; then
    cmd+=(--filter-field "${TABLE1_FILTER_FIELD}")
  fi
  if [[ -n "${TABLE1_FILTER_OPERATOR}" ]]; then
    cmd+=(--filter-operator "${TABLE1_FILTER_OPERATOR}")
  fi
  if [[ -n "${TABLE1_FILTER_VALUES}" ]]; then
    cmd+=(--filter-values "${TABLE1_FILTER_VALUES}" --filter-conjunction "${TABLE1_FILTER_CONJUNCTION}")
  fi

  "${cmd[@]}"

  [[ -f "${TABLE1_EXPORT_CSV}" ]] || die "导出 CSV 不存在: ${TABLE1_EXPORT_CSV}"
  log "步骤3/4：表1读取完成"
}

parse_and_sync_table2() {
  [[ -n "${TABLE2_ID}" ]] || die "TABLE2_ID 不能为空（用于上传表2）"
  [[ -n "${JSON_COLUMNS}" ]] || die "JSON_COLUMNS 不能为空（指定要解析的 JSON 列）"
  [[ -f "${TABLE1_EXPORT_CSV}" ]] || die "缺少导出 CSV: ${TABLE1_EXPORT_CSV}"

  log "步骤4/4：解析 JSON 列并上传到表2"

  local cmd=(uv run python sync_to_feishu.py
    --platform wechat
    --file "${TABLE1_EXPORT_CSV}"
    --json-columns "${JSON_COLUMNS}"
    --json-flatten-sep "${JSON_FLATTEN_SEP}"
    --batch-size "${TABLE2_BATCH_SIZE}")

  if [[ -n "${JSON_KEEP_COLUMNS}" ]]; then
    cmd+=(--json-keep-columns "${JSON_KEEP_COLUMNS}")
  fi
  if [[ -n "${TABLE2_PRIMARY}" ]]; then
    cmd+=(--json-primary "${TABLE2_PRIMARY}")
  fi

  # 注意：json-columns 分支不走 --append-table-id，需临时覆盖 FEISHU_TABLE_ID 到表2
  FEISHU_TABLE_ID="${TABLE2_ID}" "${cmd[@]}"

  log "步骤4/4：表2同步完成"
}

main() {
  log "工作流开始：wechat crawl -> table1 -> read table1 -> parse json -> table2"

  if [[ "${RUN_CRAWL}" == "1" ]]; then
    run_crawler
  else
    log "跳过步骤1（RUN_CRAWL=${RUN_CRAWL}）"
  fi

  if [[ "${RUN_SYNC_TABLE1}" == "1" ]]; then
    sync_table1
  else
    log "跳过步骤2（RUN_SYNC_TABLE1=${RUN_SYNC_TABLE1}）"
  fi

  if [[ "${RUN_PARSE_TO_TABLE2}" == "1" ]]; then
    read_table1
    parse_and_sync_table2
  else
    log "跳过步骤3/4（RUN_PARSE_TO_TABLE2=${RUN_PARSE_TO_TABLE2}）"
  fi

  log "工作流完成 ✅"
}

main "$@"
