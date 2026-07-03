#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

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
SHARED_VENV="$USER_DATA_DIR/.venv"
DEP_STATE="$USER_DATA_DIR/runtime/dependency_state.json"

if [[ ! -x "$SHARED_VENV/bin/python3" ]]; then
  echo "No shared venv found."
  echo "Run this first:"
  echo "  ./setup_venv_3dcp_console.sh"
  exit 1
fi

echo "Launching 3DCP Perspective Console v1.0.0-rc1"

# Last fallback check only. No dependency install here.
if ! "$SHARED_VENV/bin/python3" - <<'PY'
import qrcode
from PIL import Image, ImageTk
PY
then
  echo "WARN: shared venv dependencies are missing."
  echo "Run:"
  echo "  ./setup_venv_3dcp_console.sh"
  python3 - "$DEP_STATE" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({"deps_ready_last_run": 0}, indent=2) + "\n", encoding="utf-8")
PY
  exit 1
fi

python3 - "$DEP_STATE" "$SHARED_VENV" <<'PY'
import json, sys, time
from pathlib import Path
p = Path(sys.argv[1])
venv = sys.argv[2]
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps({
    "deps_ready_last_run": 1,
    "venv_path": venv,
    "updated_at_unix": int(time.time()),
    "required_imports": ["qrcode", "PIL.Image", "PIL.ImageTk"]
}, indent=2) + "\n", encoding="utf-8")
PY

"$SHARED_VENV/bin/python3" 3dcp_perspective_console.py
