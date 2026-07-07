#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="GITHUB_UPLOAD"
rm -rf "$OUT"
mkdir -p "$OUT"

copy_with_python() {
  python3 - <<'PY'
from __future__ import annotations
import shutil
from pathlib import Path

root = Path.cwd()
out = root / "GITHUB_UPLOAD"
ignore_names = {
    "GITHUB_UPLOAD", "venv", ".venv", "__pycache__", ".pytest_cache", ".git"
}
ignore_suffixes = {".pyc"}
ignore_globs = ("*_preview.html", "*_outline.txt")

for src in root.iterdir():
    if src.name in ignore_names:
        continue
    if any(src.match(pattern) for pattern in ignore_globs):
        continue
    dst = out / src.name
    if src.is_dir():
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
            "GITHUB_UPLOAD", "venv", ".venv", "__pycache__", ".pytest_cache", ".git",
            "*.pyc", "*_preview.html", "*_outline.txt"
        ))
    elif src.is_file():
        if src.suffix in ignore_suffixes:
            continue
        shutil.copy2(src, dst)
PY
}

if command -v rsync >/dev/null 2>&1; then
  rsync -a \
    --exclude "$OUT" \
    --exclude 'venv/' \
    --exclude '.venv/' \
    --exclude '__pycache__/' \
    --exclude '.pytest_cache/' \
    --exclude '*.pyc' \
    --exclude '*_preview.html' \
    --exclude '*_outline.txt' \
    --exclude '.git/' \
    ./ "$OUT/"
else
  copy_with_python
fi

find "$OUT" -type d \( -name '__pycache__' -o -name '.pytest_cache' \) -prune -exec rm -rf {} +
find "$OUT" -name '*.pyc' -delete

# Confirm the upload copy self-tests independently, without mixing with the root tests.
PYTHON="python3"
if [ -x "venv/bin/python" ]; then
  PYTHON="$PWD/venv/bin/python"
elif [ -x ".venv/bin/python" ]; then
  PYTHON="$PWD/.venv/bin/python"
fi
if [ -d "$OUT/tests" ]; then
  (cd "$OUT" && "$PYTHON" -m pytest -q tests)
fi

echo "Built clean GitHub upload folder: $OUT"
echo "Upload the contents of $OUT/ as the repository root."
