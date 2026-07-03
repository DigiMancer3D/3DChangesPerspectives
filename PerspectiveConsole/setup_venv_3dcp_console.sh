#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "3DCP Perspective Console shared venv setup v1.0.0-rc1"
echo "=================================================="

APP_DIR="$(pwd)"
INSTALL_ROOT="$(dirname "$APP_DIR")"
DEFAULT_USER_DATA_DIR="$INSTALL_ROOT/user_data"
LEGACY_USER_DATA_DIR="$INSTALL_ROOT/_3dcp_console_user_data"
USER_DATA_DIR="${DCP3_CONSOLE_USER_DATA:-$DEFAULT_USER_DATA_DIR}"

if [[ -z "${DCP3_CONSOLE_USER_DATA:-}" && -d "$LEGACY_USER_DATA_DIR" && ! -e "$DEFAULT_USER_DATA_DIR" ]]; then
  mv "$LEGACY_USER_DATA_DIR" "$DEFAULT_USER_DATA_DIR"
elif [[ -z "${DCP3_CONSOLE_USER_DATA:-}" && -d "$LEGACY_USER_DATA_DIR" && -d "$DEFAULT_USER_DATA_DIR" ]]; then
  python3 - "$LEGACY_USER_DATA_DIR" "$DEFAULT_USER_DATA_DIR" <<'PY'
import shutil, sys
from pathlib import Path
legacy = Path(sys.argv[1])
target = Path(sys.argv[2])
target.mkdir(parents=True, exist_ok=True)
for item in legacy.iterdir():
    dest = target / item.name
    if dest.exists():
        continue
    if item.is_dir():
        shutil.copytree(item, dest)
    else:
        shutil.copy2(item, dest)
PY
fi
RUNTIME_DIR="$USER_DATA_DIR/runtime"
SHARED_VENV="$USER_DATA_DIR/.venv"
DEP_STATE="$RUNTIME_DIR/dependency_state.json"

mkdir -p "$RUNTIME_DIR"

if ! python3 - <<'PY'
import venv
PY
then
  echo
  echo "Python venv support is missing."
  echo "Install it with:"
  echo "  sudo apt install python3-venv python3-full"
  exit 1
fi

read_state_ready() {
  python3 - "$DEP_STATE" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
if not p.exists():
    print("0")
    raise SystemExit
try:
    data = json.loads(p.read_text(encoding="utf-8"))
    print("1" if data.get("deps_ready_last_run") == 1 else "0")
except Exception:
    print("0")
PY
}

write_state() {
  local ready="$1"
  python3 - "$DEP_STATE" "$ready" "$SHARED_VENV" <<'PY'
import json, sys, time
from pathlib import Path
p = Path(sys.argv[1])
ready = int(sys.argv[2])
venv = sys.argv[3]
data = {
    "deps_ready_last_run": ready,
    "venv_path": venv,
    "updated_at_unix": int(time.time()),
    "required_imports": ["qrcode", "PIL.Image", "PIL.ImageTk"]
}
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
}

venv_import_check() {
  "$SHARED_VENV/bin/python3" - <<'PY'
import qrcode
from PIL import Image, ImageTk
PY
}

if [[ ! -x "$SHARED_VENV/bin/python3" ]]; then
  echo "INFO: creating shared venv:"
  echo "  $SHARED_VENV"
  python3 -m venv "$SHARED_VENV"
else
  echo "PASS: shared venv exists:"
  echo "  $SHARED_VENV"
fi

PRECHECK="$(read_state_ready)"

if [[ "$PRECHECK" == "1" ]]; then
  echo "PASS: dependency precheck says deps worked last run"
  echo "INFO: verifying imports inside shared venv without installing"
  if venv_import_check; then
    echo "PASS: shared venv imports qrcode + Pillow"
    echo "INFO: skipping dependency install"
    write_state 1
    echo
    echo "PASS: virtual environment ready"
    echo
    echo "Launch with:"
    echo "  ./launch_3dcp_console_venv.sh"
    exit 0
  else
    echo "WARN: precheck was ready, but import verification failed"
    echo "INFO: dependency install will run as fallback"
  fi
else
  echo "INFO: dependency precheck not ready yet"
fi

if venv_import_check; then
  echo "PASS: qrcode + Pillow already installed in shared venv"
  echo "INFO: skipping dependency install"
  write_state 1
else
  echo "INFO: installing missing QR dependencies into shared venv"
  "$SHARED_VENV/bin/python3" -m pip install -r requirements.txt
  if venv_import_check; then
    write_state 1
  else
    write_state 0
    echo "FAIL: dependencies still do not import after install"
    exit 1
  fi
fi

echo
echo "PASS: virtual environment ready"
echo
echo "Launch with:"
echo "  ./launch_3dcp_console_venv.sh"
