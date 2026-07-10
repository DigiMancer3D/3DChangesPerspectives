#!/usr/bin/env python3
from __future__ import annotations
import argparse
import subprocess
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("desktop_ids", nargs="*", help="Desktop ids without .desktop")
    args = p.parse_args()

    app_dir = Path.home() / ".local/share/applications"
    ids = args.desktop_ids or [
        "streamer-board-console",
        "bitninja-mocap-lite",
        "deck-card-widget",
        "3dcp-perspective-console",
        "swar-reader",
        "swar-standard",
        "g502v",
        "soundcard-visualizer",
    ]

    for desktop_id in ids:
        path = app_dir / f"{desktop_id}.desktop"
        print(f"\n--- {path} ---")
        if not path.exists():
            print("missing")
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith(("Name=", "Exec=", "Icon=", "StartupWMClass=")):
                print(line)

    print("\nManual runtime check:")
    print("  1. Open an app.")
    print("  2. Run: xprop WM_CLASS")
    print("  3. Click the app window.")
    print("  4. The SECOND WM_CLASS value should match StartupWMClass.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
