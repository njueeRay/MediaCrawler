#!/usr/bin/env bash
# scripts/renew_wechat_auth.sh
#
# WECHAT_AUTH_KEY 半自动轮换脚本
# 用法：
#   交互式：bash scripts/renew_wechat_auth.sh
#   非交互：NEW_AUTH_KEY="your-new-key" bash scripts/renew_wechat_auth.sh
#
# 功能：
#   1. 备份 .env 文件
#   2. 替换 WECHAT_AUTH_KEY 的值
#   3. 提示重启 WebUI 服务

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_ROOT/.env"
BACKUP_DIR="$PROJECT_ROOT/.env_backups"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

# ── 颜色 ────────────────────────────────────────────────────────────
RED='\033[0;31m'; YELLOW='\033[1;33m'; GREEN='\033[0;32m'; NC='\033[0m'

log_info()  { echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠  $*${NC}"; }
log_error() { echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ✗  $*${NC}" >&2; }

# ── 1. 获取新 Key ────────────────────────────────────────────────────
if [[ -n "${NEW_AUTH_KEY:-}" ]]; then
    NEW_KEY="$NEW_AUTH_KEY"
    log_info "使用环境变量 NEW_AUTH_KEY"
else
    echo ""
    echo "请在 wechat-article-exporter 中重新登录后，复制 Auth-Key："
    echo "  参考文档: docs/wechat/auth-key-renewal.md §二"
    echo ""
    read -r -p "请粘贴新的 WECHAT_AUTH_KEY（直接回车取消）: " NEW_KEY
    if [[ -z "$NEW_KEY" ]]; then
        log_warn "未输入 Key，已取消"
        exit 0
    fi
fi

# ── 2. 检查 .env 文件 ────────────────────────────────────────────────
if [[ ! -f "$ENV_FILE" ]]; then
    log_warn ".env 文件不存在，将创建新文件: $ENV_FILE"
    touch "$ENV_FILE"
fi

# ── 3. 备份 .env ─────────────────────────────────────────────────────
mkdir -p "$BACKUP_DIR"
BACKUP_FILE="$BACKUP_DIR/.env.$TIMESTAMP.bak"
cp "$ENV_FILE" "$BACKUP_FILE"
log_info "已备份: $BACKUP_FILE"

# ── 4. 替换或追加 WECHAT_AUTH_KEY ────────────────────────────────────
if grep -q "^WECHAT_AUTH_KEY=" "$ENV_FILE"; then
    # 已有该行，替换之（兼容 macOS sed 和 GNU sed）
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s|^WECHAT_AUTH_KEY=.*|WECHAT_AUTH_KEY=${NEW_KEY}|" "$ENV_FILE"
    else
        sed -i "s|^WECHAT_AUTH_KEY=.*|WECHAT_AUTH_KEY=${NEW_KEY}|" "$ENV_FILE"
    fi
    log_info "WECHAT_AUTH_KEY 已更新"
else
    # 追加到文件末尾
    echo "" >> "$ENV_FILE"
    echo "WECHAT_AUTH_KEY=${NEW_KEY}" >> "$ENV_FILE"
    log_info "WECHAT_AUTH_KEY 已追加到 .env"
fi

# ── 5. 写入轮换时间戳 ─────────────────────────────────────────────────
RENEWAL_LOG="$PROJECT_ROOT/.wechat_auth_renewal_history"
echo "$TIMESTAMP  renewed" >> "$RENEWAL_LOG"
log_info "轮换记录已追加: $RENEWAL_LOG"

# ── 6. 提示重启 ──────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════════════════════"
echo "  ✅ WECHAT_AUTH_KEY 轮换完成"
echo ""
echo "  下一步：重启 WebUI 服务，使新 Key 生效："
echo ""
echo "    # systemd 环境："
echo "    sudo systemctl restart mediacrawler-api.service"
echo ""
echo "    # 直接 uvicorn 启动时，重新运行："
echo "    uv run uvicorn api.main:app --port 8080"
echo ""
echo "    # 验证新 Key 是否有效："
echo "    curl -s http://localhost:8080/api/health/platforms | python -m json.tool | grep wechat"
echo "════════════════════════════════════════════════════════"
echo ""
