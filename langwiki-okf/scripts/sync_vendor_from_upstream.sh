#!/usr/bin/env bash
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
VENDOR_DIR="$SKILL_ROOT/vendor/reference_agent"
UPSTREAM_LIST="$SKILL_ROOT/vendor/_upstream_filelist.txt"
VERSION_FILE="$SKILL_ROOT/vendor/VERSION.txt"

DRY_RUN=0
UPSTREAM_PATH=""

usage() {
  cat <<'EOF'
用法：
  bash scripts/sync_vendor_from_upstream.sh --upstream /abs/path/to/knowledge-catalog/okf/src/reference_agent [--dry-run]

参数：
  --upstream <path>   上游 reference_agent 目录（必填，绝对路径）
  --dry-run           仅预览，不实际写入
EOF
}

while [ "$#" -gt 0 ]; do
  case "$1" in
    --upstream)
      UPSTREAM_PATH="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      error "未知参数: $1"
      usage
      exit 1
      ;;
  esac
done

if [ -z "$UPSTREAM_PATH" ]; then
  error "缺少 --upstream 参数"
  usage
  exit 1
fi

if [ "${UPSTREAM_PATH#/}" = "$UPSTREAM_PATH" ]; then
  error "--upstream 需要绝对路径"
  exit 1
fi

if [ ! -d "$UPSTREAM_PATH" ]; then
  error "上游目录不存在: $UPSTREAM_PATH"
  exit 1
fi

if ! command -v rsync >/dev/null 2>&1; then
  error "需要 rsync，请先安装"
  exit 1
fi

info "上游目录: $UPSTREAM_PATH"
info "目标目录: $VENDOR_DIR"

if [ "$DRY_RUN" -eq 1 ]; then
  warn "dry-run 模式：不会写入文件"
fi

RSYNC_ARGS=(
  -a
  --delete
  --exclude
  '__pycache__/'
  --exclude
  '*.pyc'
)

if [ "$DRY_RUN" -eq 1 ]; then
  RSYNC_ARGS+=(--dry-run --itemize-changes)
fi

rsync "${RSYNC_ARGS[@]}" "$UPSTREAM_PATH/" "$VENDOR_DIR/"

if [ "$DRY_RUN" -eq 1 ]; then
  info "已完成 dry-run，同步未落盘"
  exit 0
fi

# 生成上游文件清单（过滤缓存文件）
find "$UPSTREAM_PATH" -type f \
  ! -path '*/__pycache__/*' \
  ! -name '*.pyc' \
  | sort > "$UPSTREAM_LIST"

TODAY="$(date +%F)"
UPSTREAM_COMMIT="unknown"
if command -v git >/dev/null 2>&1; then
  if git -C "$UPSTREAM_PATH" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    UPSTREAM_COMMIT="$(git -C "$UPSTREAM_PATH" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  elif git -C "$(dirname "$UPSTREAM_PATH")" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    UPSTREAM_COMMIT="$(git -C "$(dirname "$UPSTREAM_PATH")" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  fi
fi

cat > "$VERSION_FILE" <<EOF
vendor: reference-agent
upstream_repo: https://github.com/bluewms/knowledge-catalog
upstream_branch: zh
upstream_commit: $UPSTREAM_COMMIT
snapshot_date: $TODAY
snapshot_scope: knowledge-catalog/okf/src/reference_agent
EOF

info "同步完成并更新："
info "- $UPSTREAM_LIST"
info "- $VERSION_FILE"
