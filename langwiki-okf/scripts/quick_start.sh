#!/usr/bin/env bash
#
# OKF 知识包快速启动脚本（vendor 内置版）
#
# 用法：
#   ./quick_start.sh                                  # bootstrap + 基本检查
#   ./quick_start.sh /path/to/docs                    # 生成测试包
#   ./quick_start.sh /path/to/docs gemini-flash-latest
#   ./quick_start.sh --sync-vendor --upstream <path>  # 同步上游 reference_agent
#

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}✅ $1${NC}"; }
warn()  { echo -e "${YELLOW}⚠️  $1${NC}"; }
error() { echo -e "${RED}❌ $1${NC}"; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BOOTSTRAP="$SCRIPT_DIR/bootstrap_local.sh"
LOCAL_RA="$SCRIPT_DIR/reference-agent"
SYNC_VENDOR_SCRIPT="$SCRIPT_DIR/sync_vendor_from_upstream.sh"

ensure_reference_agent() {
  if [ -x "$LOCAL_RA" ]; then
    echo "$LOCAL_RA"
    return 0
  fi

  if command -v reference-agent >/dev/null 2>&1; then
    echo "reference-agent"
    return 0
  fi

  warn "未检测到可用 reference-agent，开始执行 bootstrap..."
  bash "$BOOTSTRAP"

  if [ -x "$LOCAL_RA" ]; then
    echo "$LOCAL_RA"
    return 0
  fi

  error "bootstrap 后仍未找到 reference-agent 入口"
  exit 1
}

echo "=========================================="
echo "  OKF 知识包快速启动（No-Clone）"
echo "=========================================="
echo ""

if [ "${1:-}" = "--sync-vendor" ]; then
  if [ ! -x "$SYNC_VENDOR_SCRIPT" ]; then
    error "未找到同步脚本: $SYNC_VENDOR_SCRIPT"
    exit 1
  fi
  shift
  bash "$SYNC_VENDOR_SCRIPT" "$@"
  info "vendor 同步流程完成"
  exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
  error "未找到 python3"
  exit 1
fi
info "Python: $(python3 --version 2>&1)"

RA_CMD="$(ensure_reference_agent)"
info "reference-agent 入口: $RA_CMD"

echo ""
echo "Step: 支持模型..."
"$RA_CMD" list-models 2>/dev/null || warn "无法列出模型（可忽略）"

if [ -n "${1:-}" ]; then
  SOURCE_DIR="$1"
  MODEL="${2:-gemini-flash-latest}"
  OUTPUT_DIR="./okf-test-bundle"

  if [ ! -d "$SOURCE_DIR" ]; then
    error "源目录不存在: $SOURCE_DIR"
    exit 1
  fi

  echo ""
  echo "Step: 生成测试包"
  echo "  源目录: $SOURCE_DIR"
  echo "  模型:   $MODEL"
  echo "  输出:   $OUTPUT_DIR"

  "$RA_CMD" localfile "$SOURCE_DIR" \
    --pattern "**/*" \
    --model "$MODEL" \
    -o "$OUTPUT_DIR" \
    -v

  info "生成完成"
  find "$OUTPUT_DIR" -name "*.md" | head -20 || true

  echo ""
  echo "Step: 验证 OKF 包"
  python3 "$SCRIPT_DIR/validate_bundle.py" "$OUTPUT_DIR" --verbose || true
else
  echo ""
  echo "Step: 跳过测试（未提供源目录）"
  echo "示例："
  echo "  $0 /path/to/your/docs"
  echo "  $0 /path/to/your/docs deepseek/deepseek-chat"
fi

echo ""
echo "=========================================="
echo "  快速启动完成"
echo "=========================================="
