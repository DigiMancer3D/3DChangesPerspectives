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

python3 - "$USER_DATA_DIR" <<'PY'
import json, shutil, sys
from pathlib import Path

user_data = Path(sys.argv[1])
runtime = user_data / "buttstores" / "default_episode.buttstore"
template = Path("data/templates/default_episode_template.buttstore")
runtime.parent.mkdir(parents=True, exist_ok=True)

if not runtime.exists():
    shutil.copy2(template, runtime)
    print("INFO: shared runtime default .buttstore was missing; created from template")

data = json.loads(runtime.read_text(encoding="utf-8"))

data.setdefault("under_header", {})
data["under_header"]["output_visible"] = True
data["under_header"]["output_geometry"] = "960x500+80+80"
data["under_header"]["controller_geometry"] = "1120x720+80+620"
data["under_header"]["scan_loop"] = False
data["under_header"]["last_runtime_event"] = "manual-window-reset"

data.setdefault("header", {})
data["header"]["active_card_id"] = "source-analyzer"

runtime.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print("PASS: reset output window to 960x500+80+80 and enabled visibility")
print(f"Shared user data: {user_data}")
PY
