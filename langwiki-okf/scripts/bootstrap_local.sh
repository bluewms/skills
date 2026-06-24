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
VENDOR_DIR="$SKILL_ROOT/vendor"
REQ_FILE="$SCRIPT_DIR/requirements-vendor.txt"
WRAPPER="$SCRIPT_DIR/reference-agent"

pick_python() {
  local candidates=()
  if [ -n "${PYTHON_BIN:-}" ]; then
    candidates+=("$PYTHON_BIN")
  fi
  candidates+=("python3.11" "python3")

  for py in "${candidates[@]}"; do
    if command -v "$py" >/dev/null 2>&1; then
      local real_py
      real_py="$(command -v "$py")"
      local ok
      ok="$($real_py - <<'PY'
import sys
print(1 if sys.version_info >= (3,11) else 0)
PY
)"
      if [ "$ok" = "1" ]; then
        echo "$real_py"
        return 0
      fi
    elif [ -x "$py" ]; then
      local ok
      ok="$($py - <<'PY'
import sys
print(1 if sys.version_info >= (3,11) else 0)
PY
)"
      if [ "$ok" = "1" ]; then
        echo "$py"
        return 0
      fi
    fi
  done

  return 1
}

if [ ! -d "$VENDOR_DIR/reference_agent" ]; then
  error "找不到 vendor/reference_agent，请先同步 vendor 源码"
  exit 1
fi

PYTHON_EXE="$(pick_python || true)"
if [ -z "$PYTHON_EXE" ]; then
  error "需要 Python 3.11+，未找到可用解释器。可设置: export PYTHON_BIN=/path/to/python3.11"
  exit 1
fi

info "使用 Python: $($PYTHON_EXE --version 2>&1) ($PYTHON_EXE)"
info "安装 vendor 依赖..."
"$PYTHON_EXE" -m pip install --user -r "$REQ_FILE"

cat > "$WRAPPER" <<EOF
#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="\$(cd "\$(dirname "\$0")" && pwd)"
SKILL_ROOT="\$(cd "\$SCRIPT_DIR/.." && pwd)"
export PYTHONPATH="\$SKILL_ROOT/vendor\${PYTHONPATH:+:\$PYTHONPATH}"
exec "$PYTHON_EXE" -c "from reference_agent.cli import main; main()" "\$@"
EOF
chmod +x "$WRAPPER"

info "已生成本地 CLI 包装器: $WRAPPER"
info "可执行验证: $WRAPPER --help"
info "建议加入 PATH: export PATH=\"$SCRIPT_DIR:\$PATH\""
