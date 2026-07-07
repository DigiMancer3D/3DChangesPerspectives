#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
APP_DIR="$(pwd)"
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"

chmod +x "$APP_DIR/launch_reader.sh" "$APP_DIR/launch_standard.sh"

cat > "$DESKTOP_DIR/swar-reader.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=SWAR Reader
Comment=Open SWAR in local-only reader mode
Exec=$APP_DIR/launch_reader.sh %f
Icon=$APP_DIR/icon-reader.svg
Terminal=false
Categories=Utility;Viewer;
MimeType=text/plain;text/markdown;
EOF

cat > "$DESKTOP_DIR/swar-standard.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=SWAR Standard
Comment=Open SWAR in standard reader/editor mode
Exec=$APP_DIR/launch_standard.sh %f
Icon=$APP_DIR/icon-standard.svg
Terminal=false
Categories=Utility;TextEditor;
MimeType=text/plain;text/markdown;
EOF

chmod +x "$DESKTOP_DIR/swar-reader.desktop" "$DESKTOP_DIR/swar-standard.desktop"
update-desktop-database "$DESKTOP_DIR" >/dev/null 2>&1 || true

echo "Installed SWAR desktop entries:"
echo "  $DESKTOP_DIR/swar-reader.desktop"
echo "  $DESKTOP_DIR/swar-standard.desktop"
