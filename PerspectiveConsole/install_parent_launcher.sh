#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

APP_DIR="$(pwd)"
INSTALL_ROOT="$(dirname "$APP_DIR")"
CURRENT_LINK="$INSTALL_ROOT/current"
LAUNCHER="$INSTALL_ROOT/launch_current_3dcp_console.sh"
USER_DATA_DIR="$INSTALL_ROOT/user_data"

mkdir -p "$USER_DATA_DIR"

# Create a stable current symlink when the filesystem supports it.
rm -f "$CURRENT_LINK"
ln -s "$(basename "$APP_DIR")" "$CURRENT_LINK"

cat > "$LAUNCHER" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
BASE_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ -L "$BASE_DIR/current" && -d "$BASE_DIR/current" ]]; then
  cd "$BASE_DIR/current"
else
  cd "$BASE_DIR/3DCP_Perspective_Console_v1_0_0_rc1_GitHub_Ready"
fi

exec ./launch_3dcp_console_venv.sh
EOF

chmod +x "$LAUNCHER"

echo "PASS: parent launcher installed:"
echo "  $LAUNCHER"
echo "PASS: current symlink points to:"
echo "  $(readlink "$CURRENT_LINK")"
echo
echo "Launch from parent folder with:"
echo "  ./launch_current_3dcp_console.sh"
