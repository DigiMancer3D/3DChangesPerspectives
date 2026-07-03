#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

APP_DIR="$(pwd)"
INSTALL_ROOT="$(dirname "$APP_DIR")"
USER_DATA_DIR="${DCP3_CONSOLE_USER_DATA:-$INSTALL_ROOT/user_data}"
REPORT_DIR="$USER_DATA_DIR/reports"
mkdir -p "$REPORT_DIR"

STAMP="$(date +%Y%m%d_%H%M%S)"
JSON_REPORT="$REPORT_DIR/health_$STAMP.json"
TXT_REPORT="$REPORT_DIR/health_$STAMP.txt"

python3 - "$APP_DIR" "$USER_DATA_DIR" "$JSON_REPORT" "$TXT_REPORT" <<'PY'
from pathlib import Path
from datetime import datetime
import json
import hashlib
import sys

app_dir = Path(sys.argv[1])
user_data = Path(sys.argv[2])
json_report = Path(sys.argv[3])
txt_report = Path(sys.argv[4])

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def count_files(path: Path, pattern: str) -> int:
    return len(list(path.glob(pattern))) if path.exists() else 0

app_file = app_dir / "3dcp_perspective_console.py"
template = app_dir / "data" / "templates" / "default_episode_template.buttstore"

report = {
    "report_type": "3DCP Perspective Console Health Report",
    "generated_at": datetime.now().isoformat(),
    "app_dir": str(app_dir),
    "user_data": str(user_data),
    "app_file_exists": app_file.exists(),
    "app_sha256": sha256(app_file) if app_file.exists() else None,
    "template_exists": template.exists(),
    "template_sha256": sha256(template) if template.exists() else None,
    "directories": {},
    "counts": {},
    "warnings": [],
}

for name in ["buttstores", "runtime", "imported_pngs", "deckbutts", "exports", "reports", "archived_duplicate_buttstores"]:
    path = user_data / name
    report["directories"][name] = {
        "exists": path.exists(),
        "path": str(path),
    }

buttstores = user_data / "buttstores"
report["counts"]["buttstores"] = count_files(buttstores, "*.buttstore")
report["counts"]["migrated_buttstores"] = count_files(buttstores, "*_migrated_*.buttstore")
report["counts"]["legacy_buttstores"] = count_files(buttstores, "*_legacy_*.buttstore")
report["counts"]["deckbutts"] = count_files(user_data / "deckbutts", "*.deckbutt")
report["counts"]["imported_pngs"] = count_files(user_data / "imported_pngs", "*.png")
report["counts"]["export_pngs"] = count_files(user_data / "exports", "**/*.png")

if report["counts"]["migrated_buttstores"] or report["counts"]["legacy_buttstores"]:
    report["warnings"].append("Duplicate-looking buttstores are present in active buttstores folder.")

current_emoji = user_data / "current.emoji"
if current_emoji.exists():
    raw = current_emoji.read_text(encoding="utf-8")
    records = [part.strip() for part in raw.split("/,") if part.strip()]
    report["current_emoji"] = {"exists": True, "records": len(records)}
else:
    report["current_emoji"] = {"exists": False, "records": 0}

json_report.write_text(json.dumps(report, indent=2), encoding="utf-8")

lines = [
    "3DCP Perspective Console Health Report",
    "======================================",
    f"Generated: {report['generated_at']}",
    f"App dir: {report['app_dir']}",
    f"User data: {report['user_data']}",
    "",
    "Counts:",
]
for key, value in report["counts"].items():
    lines.append(f"  {key}: {value}")
lines.append("")
lines.append("Directories:")
for key, value in report["directories"].items():
    lines.append(f"  {key}: {'yes' if value['exists'] else 'no'}")
if report["warnings"]:
    lines.append("")
    lines.append("Warnings:")
    for warning in report["warnings"]:
        lines.append(f"  - {warning}")
else:
    lines.append("")
    lines.append("Warnings: none")
txt_report.write_text("\n".join(lines) + "\n", encoding="utf-8")

print(f"PASS: health JSON written: {json_report}")
print(f"PASS: health TXT written: {txt_report}")
PY
