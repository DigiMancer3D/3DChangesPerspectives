#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
status=0
for path in launch_reader.sh launch_standard.sh install_desktop_entries.sh icon-reader.svg icon-standard.svg; do
  if [ ! -e "$path" ]; then
    echo "MISSING: $path"
    status=1
  fi
done
for path in launch_reader.sh launch_standard.sh install_desktop_entries.sh; do
  if [ -e "$path" ] && [ ! -x "$path" ]; then
    echo "NOT EXECUTABLE: $path"
    status=1
  fi
done
for path in desktop/SWAR-Reader.desktop.template desktop/SWAR-Standard.desktop.template; do
  if [ ! -e "$path" ]; then
    echo "MISSING: $path"
    status=1
  fi
done
if [ "$status" -ne 0 ]; then
  exit "$status"
fi
echo "Desktop launcher files look ready."
echo "Optional install: ./install_desktop_entries.sh"
