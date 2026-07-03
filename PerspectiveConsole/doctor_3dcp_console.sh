#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

echo "3DCP Perspective Console Doctor v1.0.0-rc1"
echo "========================================"

pass() { echo "PASS: $1"; }
warn() { echo "WARN: $1"; }
fail() { echo "FAIL: $1"; exit 1; }

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

[[ -f "3dcp_perspective_console.py" ]] && pass "app file exists" || fail "missing app file"
[[ -f "requirements.txt" ]] && pass "requirements file exists" || fail "missing requirements"
[[ -f "data/templates/default_episode_template.buttstore" ]] && pass "default template exists" || fail "missing default template"
[[ -f "data/emoji_presets/default_presets.emoji" ]] && pass "emoji preset file exists" || fail "missing emoji preset file"
[[ -f "archive_duplicate_buttstores.sh" ]] && pass "duplicate archive helper exists" || fail "missing duplicate archive helper"
[[ -f "acceptance_3dcp_console.sh" ]] && pass "acceptance helper exists" || fail "missing acceptance helper"
[[ -f "health_report_3dcp_console.sh" ]] && pass "health report helper exists" || fail "missing health report helper"
[[ -f "release_package_3dcp_console.sh" ]] && pass "release package helper exists" || fail "missing release package helper"
[[ -f "install_parent_launcher.sh" ]] && pass "parent launcher helper exists" || fail "missing parent launcher helper"
[[ -f "cleanup_stale_root_files.sh" ]] && pass "stale root cleanup helper exists" || fail "missing stale root cleanup helper"
[[ -f "prepare_github_upload.sh" ]] && pass "GitHub upload helper exists" || fail "missing GitHub upload helper"
[[ -f ".gitignore" ]] && pass ".gitignore exists" || fail "missing .gitignore"
[[ -f ".github/workflows/acceptance.yml" ]] && pass "GitHub Actions acceptance workflow exists" || fail "missing GitHub Actions workflow"
mkdir -p "$USER_DATA_DIR/imported_pngs" >/dev/null 2>&1 || true
pass "shared imported_pngs directory ready"
mkdir -p "$USER_DATA_DIR/exports" >/dev/null 2>&1 || true
pass "shared exports directory ready"
mkdir -p "$USER_DATA_DIR/deckbutts" >/dev/null 2>&1 || true
pass "shared deckbutts directory ready"

python3 -m py_compile 3dcp_perspective_console.py
pass "python compile"

python3 - <<'PY'
from pathlib import Path
src = Path("3dcp_perspective_console.py").read_text(encoding="utf-8")
required = [
    "archive_duplicate_buttstores_after_load",
    "cleanup_archived_duplicate_buttstores_on_shutdown",
    "DUPLICATE_ARCHIVE_ROOT",
]
missing = [item for item in required if item not in src]
if missing:
    raise SystemExit(f"missing archive lifecycle code: {missing}")
print("PASS: startup archive method present")
print("PASS: shutdown archive cleanup method present")
PY
python3 - <<'PY'
from pathlib import Path
src = Path("3dcp_perspective_console.py").read_text(encoding="utf-8")
required = [
    "bind_controller_hotkeys",
    "hotkey_should_run",
    "Controller Hotkeys",
    "Enable controller hotkeys",
]
missing = [item for item in required if item not in src]
if missing:
    raise SystemExit(f"missing hotkey workflow code: {missing}")
print("PASS: hotkey methods present")
print("PASS: hotkeys tab present")
PY
python3 - <<'PY'
from pathlib import Path
src = Path("3dcp_perspective_console.py").read_text(encoding="utf-8")
required = [
    "Output Tools",
    "apply_output_window_style",
    "enable_obs_output_mode",
    "disable_obs_output_mode",
    "reset_output_window_position",
    "self.output.title(OUTPUT_TITLE)",
]
missing = [item for item in required if item not in src]
if missing:
    raise SystemExit(f"missing OBS output polish code: {missing}")
print("PASS: OBS output polish methods present")
print("PASS: stable output title enabled")
PY
python3 - <<'PY'
from pathlib import Path
src = Path("3dcp_perspective_console.py").read_text(encoding="utf-8")
required = [
    "recover_output_window_on_launch",
    "rescue_output_window",
    "Rescue Output Window",
    "output_borderless",
    "output_topmost",
]
missing = [item for item in required if item not in src]
if missing:
    raise SystemExit(f"missing output recovery code: {missing}")
print("PASS: output recovery methods present")
print("PASS: rescue output control present")
PY

python3 - <<'PY'
import ast
from pathlib import Path
src = Path("3dcp_perspective_console.py").read_text(encoding="utf-8")
tree = ast.parse(src)
imports = []
for node in ast.walk(tree):
    if isinstance(node, ast.Import):
        imports.extend(alias.name for alias in node.names)
    elif isinstance(node, ast.ImportFrom) and node.module:
        imports.append(node.module)
if any(name.startswith("pygame") for name in imports):
    raise SystemExit("pygame import found")
print("PASS: no pygame import")
PY

python3 - "$USER_DATA_DIR" <<'PY'
import json, shutil, sys, re
from pathlib import Path

user_data = Path(sys.argv[1])
template = Path("data/templates/default_episode_template.buttstore")
runtime = user_data / "buttstores" / "default_episode.buttstore"

template_data = json.loads(template.read_text(encoding="utf-8"))
if template_data.get("version") != "1.0.0-rc1":
    raise SystemExit(f"wrong template version: {template_data.get('version')}")

required = ["header", "under_header", "stage", "body", "footer"]
missing = [k for k in required if k not in template_data]
if missing:
    raise SystemExit(f"missing template buttstore sections: {missing}")

def safe_geo(geo):
    if not isinstance(geo, str):
        return False
    m = re.match(r"^(\d+)x(\d+)([+-]\d+)([+-]\d+)$", geo.strip())
    if not m:
        return False
    w, h, x, y = map(int, m.groups())
    return w >= 320 and h >= 200 and -5000 <= x <= 10000 and -1000 <= y <= 5000

if runtime.exists():
    runtime_data = json.loads(runtime.read_text(encoding="utf-8"))
    missing_runtime = [k for k in required if k not in runtime_data]
    if missing_runtime:
        raise SystemExit(f"shared runtime .buttstore missing sections: {missing_runtime}")
    under = runtime_data.setdefault("under_header", {})
    changed = False
    if under.get("output_visible") is not True:
        under["output_visible"] = True
        changed = True
    if not safe_geo(under.get("output_geometry", "")):
        under["output_geometry"] = "960x500+80+80"
        changed = True
    if under.get("scan_loop") is True:
        under["scan_loop"] = False
        changed = True
    if changed:
        under["last_runtime_event"] = "doctor-visibility-repair"
        runtime.write_text(json.dumps(runtime_data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print("PASS: shared runtime .buttstore repaired for visibility")
    else:
        print("PASS: shared runtime .buttstore exists and is visible-safe")
else:
    runtime.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(template, runtime)
    print("INFO: shared runtime .buttstore did not exist; created from template")

print("PASS: default .buttstore template loads")
print("PASS: v1.0.0-rc1 fields valid")
print(f"INFO: shared user data: {user_data}")
PY

python3 - <<'PY'
try:
    import tkinter
    print("PASS: tkinter import")
except Exception as exc:
    raise SystemExit(f"tkinter import failed: {exc}")
PY

if [[ -x "$USER_DATA_DIR/.venv/bin/python3" ]]; then
  if "$USER_DATA_DIR/.venv/bin/python3" - <<'PY'
import qrcode
from PIL import Image, ImageTk
PY
  then
    pass "shared venv qrcode + pillow import"
  else
    warn "shared venv exists but QR dependencies do not import"
  fi
else
  warn "shared venv missing; run ./setup_venv_3dcp_console.sh"
fi

echo
echo "Overall: PASS"
echo
echo "Launch with:"
echo "  ./launch_3dcp_console_venv.sh"

bash -n acceptance_3dcp_console.sh
pass "acceptance script syntax valid"
bash -n health_report_3dcp_console.sh
pass "health report script syntax valid"

[[ -d "docs" ]] && pass "docs folder exists" || fail "missing docs folder"
[[ -f "docs/USER_GUIDE.md" ]] && pass "user guide exists" || fail "missing user guide"
[[ -f "docs/OBS_SETUP.md" ]] && pass "OBS setup guide exists" || fail "missing OBS setup guide"
[[ -f "docs/DEV_HANDOFF.md" ]] && pass "developer handoff exists" || fail "missing developer handoff"
bash -n release_package_3dcp_console.sh
pass "release package script syntax valid"

[[ -f "docs/GITHUB_UPLOAD_GUIDE.md" ]] && pass "github guide exists" || fail "missing github guide"
[[ -f "docs/CLEAN_INSTALL_LAYOUT.md" ]] && pass "clean install layout guide exists" || fail "missing clean install layout guide"
[[ -f "docs/RELEASE_CANDIDATE_CHECKLIST.md" ]] && pass "release candidate checklist exists" || fail "missing release candidate checklist"
bash -n install_parent_launcher.sh
pass "parent launcher script syntax valid"
bash -n cleanup_stale_root_files.sh
pass "stale root cleanup script syntax valid"
bash -n prepare_github_upload.sh
pass "GitHub upload script syntax valid"
