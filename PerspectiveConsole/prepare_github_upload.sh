#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

APP_DIR="$(pwd)"
VERSION="1.0.0-rc1"
PROJECT_NAME="3DCP_Perspective_Console"
EXPORT_ROOT="$APP_DIR/github_export"
EXPORT_DIR="$EXPORT_ROOT/${PROJECT_NAME}_${VERSION}_GITHUB_UPLOAD"

rm -rf "$EXPORT_DIR"
mkdir -p "$EXPORT_DIR"

copy_path() {
  local src="$1"
  local dest="$2"
  if [[ -e "$src" ]]; then
    mkdir -p "$(dirname "$dest")"
    cp -a "$src" "$dest"
  fi
}

copy_path ".gitignore" "$EXPORT_DIR/.gitignore"
copy_path "README.md" "$EXPORT_DIR/README.md"
copy_path "VERSION.txt" "$EXPORT_DIR/VERSION.txt"
copy_path "requirements.txt" "$EXPORT_DIR/requirements.txt"
copy_path "3dcp_perspective_console.py" "$EXPORT_DIR/3dcp_perspective_console.py"

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
  release_package_3dcp_console.sh \
  install_parent_launcher.sh \
  cleanup_stale_root_files.sh \
  prepare_github_upload.sh
do
  copy_path "$script" "$EXPORT_DIR/$script"
done

copy_path "data" "$EXPORT_DIR/data"
copy_path "docs" "$EXPORT_DIR/docs"
copy_path ".github" "$EXPORT_DIR/.github"

python3 - "$EXPORT_DIR" "$VERSION" <<'PY'
from pathlib import Path
from datetime import datetime
import hashlib
import json
import sys

export_dir = Path(sys.argv[1])
version = sys.argv[2]

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

files = []
for path in sorted(export_dir.rglob("*")):
    if path.is_file():
        rel = path.relative_to(export_dir).as_posix()
        if rel.startswith(".git/"):
            continue
        files.append({
            "path": rel,
            "sha256": sha256(path),
            "size_bytes": path.stat().st_size,
        })

manifest = {
    "project": "3DCP Perspective Console",
    "version": version,
    "export_name": export_dir.name,
    "generated_at": datetime.now().isoformat(),
    "file_count": len(files),
    "files": files,
}

(export_dir / "GITHUB_UPLOAD_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
with (export_dir / "SHA256SUMS.txt").open("w", encoding="utf-8") as f:
    for item in files:
        f.write(f"{item['sha256']}  {item['path']}\n")
PY

(
  cd "$EXPORT_ROOT"
  zip -qr "${PROJECT_NAME}_${VERSION}_GITHUB_UPLOAD.zip" "${PROJECT_NAME}_${VERSION}_GITHUB_UPLOAD"
)

echo "PASS: GitHub upload folder created:"
echo "  $EXPORT_DIR"
echo "PASS: GitHub upload zip created:"
echo "  $EXPORT_ROOT/${PROJECT_NAME}_${VERSION}_GITHUB_UPLOAD.zip"
echo
echo "Do NOT upload user_data/, .venv/, old update folders, or stale root files."
echo "Use the generated folder/zip above for GitHub."
