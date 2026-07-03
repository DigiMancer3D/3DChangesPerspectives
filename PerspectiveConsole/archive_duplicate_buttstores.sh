#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

APP_DIR="$(pwd)"
INSTALL_ROOT="$(dirname "$APP_DIR")"
USER_DATA_DIR="${DCP3_CONSOLE_USER_DATA:-$INSTALL_ROOT/user_data}"
BUTTSTORE_DIR="$USER_DATA_DIR/buttstores"
STAMP="$(date +%Y%m%d_%H%M%S)"
ARCHIVE_DIR="$USER_DATA_DIR/archived_duplicate_buttstores/$STAMP"

if [[ ! -d "$BUTTSTORE_DIR" ]]; then
  echo "No buttstores directory found: $BUTTSTORE_DIR"
  exit 0
fi

mkdir -p "$ARCHIVE_DIR"

moved=0
shopt -s nullglob
for f in "$BUTTSTORE_DIR"/*_migrated_*.buttstore "$BUTTSTORE_DIR"/*_legacy_*.buttstore "$BUTTSTORE_DIR"/default_episode_template.buttstore; do
  mv "$f" "$ARCHIVE_DIR/"
  moved=$((moved + 1))
done

if [[ "$moved" -eq 0 ]]; then
  rmdir "$ARCHIVE_DIR" 2>/dev/null || true
  echo "PASS: no duplicate-looking buttstores found to archive"
else
  echo "PASS: archived $moved duplicate-looking buttstore file(s)"
  echo "Archive folder: $ARCHIVE_DIR"
fi
