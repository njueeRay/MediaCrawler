#!/usr/bin/env bash
# scripts/check_wechat_auth.sh
#
# 检测 WECHAT_AUTH_KEY 是否仍有效，适合用于 cron 定时检测
# 用法：
#   bash scripts/check_wechat_auth.sh
#   bash scripts/check_wechat_auth.sh --api-url http://myserver:8080
#
# 退出码：0=有效  1=已过期或不可用  2=无法连接 API

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# ── 参数解析 ─────────────────────────────────────────────────────────
API_URL="${WECHAT_HEALTH_API_URL:-http://localhost:8080}"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --api-url) API_URL="$2"; shift 2 ;;
        *) shift ;;
    esac
done

# ── 颜色 ────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; NC='\033[0m'
TS="[$(date '+%Y-%m-%d %H:%M:%S')]"

# ── 上次轮换时间 ─────────────────────────────────────────────────────
RENEWAL_LOG="$PROJECT_ROOT/.wechat_auth_renewal_history"
LAST_RENEWED="未知"
if [[ -f "$RENEWAL_LOG" ]]; then
    LAST_RENEWED="$(tail -1 "$RENEWAL_LOG" | awk '{print $1}' | sed 's/_/ /g')"
fi

# ── 调用健康检查接口 ──────────────────────────────────────────────────
HTTP_STATUS=0
RESPONSE=""
if command -v curl &>/dev/null; then
    RESPONSE=$(curl -s -o /tmp/_mc_health.json -w "%{http_code}" \
        --connect-timeout 5 --max-time 10 \
        "${API_URL}/api/health/platforms" 2>/dev/null || echo "000")
    HTTP_STATUS="$RESPONSE"
    [[ -f /tmp/_mc_health.json ]] && RESPONSE=$(cat /tmp/_mc_health.json) || RESPONSE=""
else
    echo -e "${YELLOW}${TS} curl 未安装，使用 .env 文件直接检测${NC}"
    # 降级：直接检查 .env 中的 key 是否为空
    ENV_FILE="$PROJECT_ROOT/.env"
    if [[ -f "$ENV_FILE" ]]; then
        KEY=$(grep "^WECHAT_AUTH_KEY=" "$ENV_FILE" | cut -d= -f2 | tr -d '"' | tr -d "'")
        if [[ -z "$KEY" ]]; then
            echo -e "${RED}${TS} ⚠️  WECHAT_AUTH_KEY 为空，请立即轮换！${NC}"
            exit 1
        else
            echo -e "${GREEN}${TS} WECHAT_AUTH_KEY 已配置（无法验证有效性，请用 curl 检测）${NC}"
            exit 0
        fi
    fi
    echo -e "${RED}${TS} 无法检测（curl 未安装且 .env 不存在）${NC}"
    exit 2
fi

# ── 解析响应 ──────────────────────────────────────────────────────────
if [[ "$HTTP_STATUS" == "000" ]] || [[ "$HTTP_STATUS" -eq 0 ]]; then
    echo -e "${YELLOW}${TS} ⚠️  无法连接 MediaCrawler API: ${API_URL}${NC}"
    echo -e "${YELLOW}${TS}    请确认 WebUI 服务已启动${NC}"
    exit 2
fi

if [[ "$HTTP_STATUS" -ne 200 ]]; then
    echo -e "${RED}${TS} API 返回异常状态码: ${HTTP_STATUS}${NC}"
    exit 2
fi

# 检查 wechat 平台状态
if echo "$RESPONSE" | grep -q '"wechat"'; then
    WECHAT_STATUS=$(echo "$RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    wechat = data.get('wechat') or data.get('platforms', {}).get('wechat', {})
    if isinstance(wechat, dict):
        print(wechat.get('status', 'unknown'))
    else:
        print(str(wechat))
except Exception as e:
    print('parse_error')
" 2>/dev/null || echo "unknown")
else
    WECHAT_STATUS="not_in_response"
fi

# ── 输出结果 ──────────────────────────────────────────────────────────
case "$WECHAT_STATUS" in
    ok|valid|connected)
        echo -e "${GREEN}${TS} WECHAT_AUTH_KEY 状态: OK（上次轮换: ${LAST_RENEWED}）${NC}"
        exit 0
        ;;
    auth_invalid|unauthorized|expired)
        echo -e "${RED}${TS} ⚠️  WECHAT_AUTH_KEY 已过期，请立即轮换！${NC}"
        echo -e "${RED}${TS}    执行: NEW_AUTH_KEY=\"<新key>\" bash scripts/renew_wechat_auth.sh${NC}"
        echo -e "${RED}${TS}    参考文档: docs/wechat/auth-key-renewal.md${NC}"
        exit 1
        ;;
    not_configured|empty)
        echo -e "${YELLOW}${TS} ⚠️  WECHAT_AUTH_KEY 未配置，微信功能不可用${NC}"
        exit 1
        ;;
    *)
        echo -e "${YELLOW}${TS} WECHAT_AUTH_KEY 状态未知: ${WECHAT_STATUS}（上次轮换: ${LAST_RENEWED}）${NC}"
        echo -e "${YELLOW}${TS} 原始响应已写入 /tmp/_mc_health.json 供排查${NC}"
        exit 1
        ;;
esac
