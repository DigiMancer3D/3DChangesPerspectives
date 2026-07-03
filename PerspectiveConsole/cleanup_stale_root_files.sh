#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

APP_DIR="$(pwd)"
INSTALL_ROOT="$(dirname "$APP_DIR")"
STAMP="$(date +%Y%m%d_%H%M%S)"
STALE_DIR="$INSTALL_ROOT/_stale_root_files_$STAMP"

mkdir -p "$STALE_DIR"

moved=0
for item in \
  3dcp_perspective_console.py \
  README.md \
  requirements.txt \
  doctor_3dcp_console.sh \
  launch_3dcp_console.sh \
  setup_venv_3dcp_console.sh \
  launch_3dcp_console_venv.sh \
  reset_window_positions.sh \
  migrate_legacy_buttstores.sh \
  archive_duplicate_buttstores.sh \
  acceptance_3dcp_console.sh \
  health_report_3dcp_console.sh \
  release_package_3dcp_console.sh \
  data \
  docs \
  __pycache__
do
  if [[ -e "$INSTALL_ROOT/$item" ]]; then
    mv -v "$INSTALL_ROOT/$item" "$STALE_DIR/"
    moved=$((moved + 1))
  fi
done

if [[ "$moved" -eq 0 ]]; then
  rmdir "$STALE_DIR" 2>/dev/null || true
  echo "PASS: no stale root files found"
else
  echo "PASS: moved $moved stale root item(s) to:"
  echo "  $STALE_DIR"
fi

echo
echo "Safe items that should remain in parent folder:"
echo "  user_data/"
echo "  current -> app folder"
echo "  launch_current_3dcp_console.sh"
echo "  3DCP_Perspective_Console_v1_0_0_rc1_GitHub_Ready/"
