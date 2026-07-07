#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

python3 -m venv venv
source venv/bin/activate
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt

# Seed the shared emoji list only when the user has not already customized one.
mkdir -p "$HOME/SWAR"
if [ -f "current.emoji" ] && [ ! -f "$HOME/SWAR/current.emoji" ]; then
  cp "current.emoji" "$HOME/SWAR/current.emoji"
fi

echo "SWAR v0.6.0-rc1 installed."
echo "Run reader test with: ./launch_reader.sh examples/example.script"
echo "Run standard shell with: ./launch_standard.sh examples/example.script"
echo "Optional desktop launchers: ./install_desktop_entries.sh"
