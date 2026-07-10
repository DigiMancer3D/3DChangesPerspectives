#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/install_desktop_identity.py \
  --desktop-id swar-reader \
  --wrapper-name swar-reader \
  --name "SWAR Reader" \
  --comment "Launch SWAR Reader" \
  --exec "./launch_reader.sh" \
  --accept-files \
  --wm-class Dcpdeckreader \
  --icon-name digimancer-dcp-reader \
  --text-icon-line1 DCP \
  --text-icon-line2 READ \
  --text-icon-bg '#241033' \
  --text-icon-fg '#ff4dff' \
  --qt-app-name Dcpdeckreader \
  --qt-display-name "SWAR Reader" \
  --qt-desktop-file swar-reader

python3 tools/install_desktop_identity.py \
  --desktop-id swar-standard \
  --wrapper-name swar-standard \
  --name "SWAR Standard" \
  --comment "Launch SWAR Standard" \
  --exec "./launch_standard.sh" \
  --accept-files \
  --wm-class Swarstandard \
  --icon-name digimancer-swar-standard \
  --text-icon-line1 SWAR \
  --text-icon-line2 STD \
  --text-icon-bg '#332610' \
  --text-icon-fg '#ffd36a' \
  --qt-app-name Swarstandard \
  --qt-display-name "SWAR Standard" \
  --qt-desktop-file swar-standard
