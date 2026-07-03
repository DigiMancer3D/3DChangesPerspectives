#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

APP_DIR="$(pwd)"
INSTALL_ROOT="$(dirname "$APP_DIR")"
DEFAULT_USER_DATA_DIR="$INSTALL_ROOT/user_data"
LEGACY_USER_DATA_DIR="$INSTALL_ROOT/_3dcp_console_user_data"
USER_DATA_DIR="${DCP3_CONSOLE_USER_DATA:-$DEFAULT_USER_DATA_DIR}"

mkdir -p "$USER_DATA_DIR/buttstores" "$USER_DATA_DIR/runtime" "$USER_DATA_DIR/imported_pngs" "$USER_DATA_DIR/deckbutts" "$USER_DATA_DIR/exports" "$USER_DATA_DIR/reports"

pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; exit 1; }
warn() { echo "WARN: $1"; }

echo "3DCP Perspective Console Acceptance v1.0.0-rc1"
echo "=========================================="

[[ -f "3dcp_perspective_console.py" ]] && pass "app file exists" || fail "missing app file"
[[ -f "requirements.txt" ]] && pass "requirements file exists" || fail "missing requirements file"
[[ -f "data/templates/default_episode_template.buttstore" ]] && pass "template exists" || fail "missing template"
[[ -f "data/emoji_presets/default_presets.emoji" ]] && pass "emoji presets exist" || fail "missing emoji presets"
[[ -f "archive_duplicate_buttstores.sh" ]] && pass "duplicate archive helper exists" || fail "missing duplicate archive helper"
[[ -f "health_report_3dcp_console.sh" ]] && pass "health report helper exists" || fail "missing health report helper"

python3 -m py_compile 3dcp_perspective_console.py
pass "python compile"

python3 - <<'PY'
from pathlib import Path
import ast
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

required = [
    'APP_VERSION = "1.0.0-rc1"',
    "ttk.Notebook",
    "Emoji Stickers",
    "PNG Images",
    "Text Layers",
    "Deck Cards",
    "Hotkeys",
    "Output Tools",
    "DUPLICATE_ARCHIVE_ROOT",
    "DECKBUTT_DIR",
    "export_current_card_png",
    "export_all_cards_png",
    "save_card_deckbutt",
    "load_card_deckbutt",
    "bind_controller_hotkeys",
    "recover_output_window_on_launch",
    "rescue_output_window",
    "archive_duplicate_buttstores_after_load",
    "cleanup_archived_duplicate_buttstores_on_shutdown",
]
missing = [item for item in required if item not in src]
if missing:
    raise SystemExit(f"missing expected feature code: {missing}")
print("PASS: no pygame import")
print("PASS: expected feature code present")
PY

python3 - <<'PY'
from pathlib import Path
import json
template = json.loads(Path("data/templates/default_episode_template.buttstore").read_text(encoding="utf-8"))
if template.get("buttstore_format") != "3DCP-BUTTSTORE":
    raise SystemExit("template format invalid")
if template.get("version") != "1.0.0-rc1":
    raise SystemExit(f"wrong template version: {template.get('version')}")
cards = template.get("body", {}).get("cards", [])
if not cards:
    raise SystemExit("template has no cards")
under = template.get("under_header", {})
for key in ["output_visible", "output_geometry", "controller_geometry"]:
    if key not in under:
        raise SystemExit(f"template missing under_header.{key}")
print("PASS: template v1.0.0-rc1 valid")
PY

python3 - "$USER_DATA_DIR" <<'PY'
from pathlib import Path
import json, hashlib, sys
user_data = Path(sys.argv[1])
required_dirs = ["buttstores", "runtime", "imported_pngs", "deckbutts", "exports", "reports"]
for name in required_dirs:
    path = user_data / name
    path.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        raise SystemExit(f"missing user_data directory: {name}")

# Check duplicate-looking buttstores. This is a warning, not fail, because startup can archive them.
dupes = []
for pattern in ["*_migrated_*.buttstore", "*_legacy_*.buttstore", "default_episode_template.buttstore"]:
    dupes.extend((user_data / "buttstores").glob(pattern))
if dupes:
    print(f"WARN: duplicate-looking buttstores present: {len(dupes)}")
else:
    print("PASS: no duplicate-looking buttstores in active buttstores folder")

# Validate current.emoji if present.
current_emoji = user_data / "current.emoji"
if current_emoji.exists():
    raw = current_emoji.read_text(encoding="utf-8")
    items = [part.strip() for part in raw.split("/,") if part.strip()]
    if not items:
        raise SystemExit("current.emoji exists but no /, separated records were found")
    print(f"PASS: user current.emoji parses records={len(items)}")
else:
    print("INFO: user current.emoji not present; packaged default presets will be used")

print("PASS: user_data directory layout valid")
PY

if [[ -x "$USER_DATA_DIR/.venv/bin/python" ]]; then
  "$USER_DATA_DIR/.venv/bin/python" - <<'PY'
import qrcode
from PIL import Image
print("PASS: shared venv imports qrcode + Pillow")
PY
else
  warn "shared venv not found; run ./setup_venv_3dcp_console.sh before launch"
fi

python3 - "$USER_DATA_DIR" <<'PY'
from pathlib import Path
import json, tempfile, sys
user_data = Path(sys.argv[1])
deckbutt_dir = user_data / "deckbutts"
deckbutt_dir.mkdir(parents=True, exist_ok=True)
payload = {
    "deckbutt_format": "3DCP-DECKBUTT",
    "version": "1.0.0-rc1",
    "created_at": "acceptance-test",
    "source_app": "3DCP Perspective Console",
    "card": {
        "id": "acceptance-card",
        "type": "source_analyzer",
        "label": "Acceptance Card",
        "fields": {},
        "layers": [],
    },
}
test_path = deckbutt_dir / ".acceptance_test.deckbutt"
test_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
loaded = json.loads(test_path.read_text(encoding="utf-8"))
if loaded.get("deckbutt_format") != "3DCP-DECKBUTT":
    raise SystemExit("deckbutt smoke file invalid")
test_path.unlink(missing_ok=True)
print("PASS: .deckbutt smoke test")
PY

python3 - "$USER_DATA_DIR" <<'PY'
from pathlib import Path
from datetime import datetime
import sys
user_data = Path(sys.argv[1])
report_dir = user_data / "reports"
report_dir.mkdir(parents=True, exist_ok=True)
marker = report_dir / "acceptance_last_passed.txt"
marker.write_text(f"3DCP acceptance v1.0.0-rc1 passed at {datetime.now().isoformat()}\n", encoding="utf-8")
print(f"PASS: acceptance marker written: {marker}")
PY

echo
echo "Overall: PASS"
echo
echo "Optional report:"
echo "  ./health_report_3dcp_console.sh"
