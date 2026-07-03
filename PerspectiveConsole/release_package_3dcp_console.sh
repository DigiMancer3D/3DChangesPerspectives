#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

APP_DIR="$(pwd)"
INSTALL_ROOT="$(dirname "$APP_DIR")"
VERSION="1.0.0-rc1"
RELEASE_NAME="3DCP_Perspective_Console_v${VERSION}_RELEASE"
OUT_ROOT="$APP_DIR/release_artifacts"
RELEASE_DIR="$OUT_ROOT/$RELEASE_NAME"

rm -rf "$RELEASE_DIR"
mkdir -p "$RELEASE_DIR"

copy_item() {
  local src="$1"
  local dest="$2"
  if [[ -e "$src" ]]; then
    mkdir -p "$(dirname "$dest")"
    cp -a "$src" "$dest"
  fi
}

copy_item "3dcp_perspective_console.py" "$RELEASE_DIR/3dcp_perspective_console.py"
copy_item "requirements.txt" "$RELEASE_DIR/requirements.txt"
copy_item "README.md" "$RELEASE_DIR/README.md"
copy_item "VERSION.txt" "$RELEASE_DIR/VERSION.txt"

for script in \
  doctor_3dcp_console.sh \
  setup_venv_3dcp_console.sh \
  launch_3dcp_console.sh \
  launch_3dcp_console_venv.sh \
  reset_window_positions.sh \
  migrate_legacy_buttstores.sh \
  archive_duplicate_buttstores.sh \
  acceptance_3dcp_console.sh \
  health_report_3dcp_console.sh \
  release_package_3dcp_console.sh
do
  copy_item "$script" "$RELEASE_DIR/$script"
done

copy_item "data" "$RELEASE_DIR/data"
copy_item "docs" "$RELEASE_DIR/docs"

python3 - "$RELEASE_DIR" "$VERSION" <<'PY'
from pathlib import Path
from datetime import datetime
import hashlib
import json
import sys

release_dir = Path(sys.argv[1])
version = sys.argv[2]

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

files = []
for path in sorted(release_dir.rglob("*")):
    if path.is_file():
        rel = path.relative_to(release_dir).as_posix()
        digest = sha256(path)
        files.append({
            "path": rel,
            "sha256": digest,
            "size_bytes": path.stat().st_size,
        })

manifest = {
    "release_name": release_dir.name,
    "version": version,
    "generated_at": datetime.now().isoformat(),
    "file_count": len(files),
    "files": files,
}

(release_dir / "RELEASE_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

with (release_dir / "SHA256SUMS.txt").open("w", encoding="utf-8") as f:
    for item in files:
        f.write(f"{item['sha256']}  {item['path']}\n")
PY

(
  cd "$OUT_ROOT"
  zip -qr "${RELEASE_NAME}.zip" "$RELEASE_NAME"
)

echo "PASS: release folder created:"
echo "  $RELEASE_DIR"
echo "PASS: release zip created:"
echo "  $OUT_ROOT/${RELEASE_NAME}.zip"
echo
echo "Recommended final checks:"
echo "  cd \"$RELEASE_DIR\""
echo "  chmod +x *.sh"
echo "  ./doctor_3dcp_console.sh"
echo "  ./acceptance_3dcp_console.sh"
