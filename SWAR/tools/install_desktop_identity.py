#!/usr/bin/env python3
"""Install repo-safe Linux desktop identity for Tk/Qt apps.

This installer is intended to be copied into a repo as:

    tools/install_desktop_identity.py

It installs per-user launcher files into XDG locations:
- ~/.local/share/digimancer_desktop_identity_py/sitecustomize.py
- ~/.local/bin/<wrapper-name>
- ~/.local/share/applications/<desktop-id>.desktop
- ~/.local/share/icons/hicolor/scalable/apps/<icon-name>.svg

The repo stays free of personal paths. Absolute paths are only written into the
current user's local desktop files during installation, which is normal for a
per-user Linux desktop launcher.
"""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

SITE_CUSTOMIZE_TEXT = r'''"""
DigiMancer Desktop Identity shim (installed local copy).

Loaded through PYTHONPATH by selected wrappers only.
"""
from __future__ import annotations
import os
import sys

_tk_cls = os.environ.get("DIGIMANCER_TK_CLASS", "").strip()
if _tk_cls:
    try:
        import tkinter as _tk
        _orig_tk_init = _tk.Tk.__init__
        _orig_top_init = _tk.Toplevel.__init__
        def _digimancer_tk_init(self, *args, **kwargs):
            kwargs["className"] = _tk_cls
            return _orig_tk_init(self, *args, **kwargs)
        def _digimancer_toplevel_init(self, *args, **kwargs):
            kwargs["class_"] = _tk_cls
            return _orig_top_init(self, *args, **kwargs)
        _tk.Tk.__init__ = _digimancer_tk_init
        _tk.Toplevel.__init__ = _digimancer_toplevel_init
    except Exception:
        pass

_qt_app = os.environ.get("DIGIMANCER_QT_APP_NAME", "").strip()
_qt_display = os.environ.get("DIGIMANCER_QT_DISPLAY_NAME", "").strip() or _qt_app
_qt_desktop = os.environ.get("DIGIMANCER_QT_DESKTOP_FILE", "").strip()
if _qt_app:
    try:
        if sys.argv:
            sys.argv[0] = _qt_app
    except Exception:
        pass
    try:
        from PySide6 import QtCore, QtGui, QtWidgets
        try:
            QtCore.QCoreApplication.setApplicationName(_qt_app)
        except Exception:
            pass
        try:
            if _qt_desktop:
                QtGui.QGuiApplication.setDesktopFileName(_qt_desktop)
        except Exception:
            pass
        _orig_qapp_init = QtWidgets.QApplication.__init__
        def _digimancer_qapp_init(self, *args, **kwargs):
            result = _orig_qapp_init(self, *args, **kwargs)
            try:
                self.setApplicationName(_qt_app)
            except Exception:
                pass
            try:
                self.setApplicationDisplayName(_qt_display)
            except Exception:
                pass
            try:
                if _qt_desktop:
                    self.setDesktopFileName(_qt_desktop)
            except Exception:
                pass
            return result
        QtWidgets.QApplication.__init__ = _digimancer_qapp_init
    except Exception:
        pass
'''


def xdg_data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))).expanduser()


def xdg_bin_home() -> Path:
    return Path.home() / ".local/bin"


def write_text_icon(path: Path, line1: str, line2: str, bg: str, fg: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 256 256">
  <rect x="10" y="10" width="236" height="236" rx="34" fill="{bg}"/>
  <rect x="22" y="22" width="212" height="212" rx="24" fill="none" stroke="{fg}" stroke-width="8" opacity="0.78"/>
  <text x="128" y="108" text-anchor="middle" font-family="DejaVu Sans, Arial, sans-serif" font-size="58" font-weight="800" fill="{fg}">{line1}</text>
  <text x="128" y="176" text-anchor="middle" font-family="DejaVu Sans, Arial, sans-serif" font-size="50" font-weight="800" fill="{fg}">{line2}</text>
</svg>
''', encoding="utf-8")


def make_wrapper(args: argparse.Namespace, helper_dir: Path, repo_root: Path, wrapper_path: Path) -> None:
    env_lines: list[str] = []
    if args.tk_class:
        env_lines.append(f'export DIGIMANCER_TK_CLASS="{args.tk_class}"')
    if args.qt_app_name:
        env_lines.append(f'export DIGIMANCER_QT_APP_NAME="{args.qt_app_name}"')
        env_lines.append(f'export DIGIMANCER_QT_DISPLAY_NAME="{args.qt_display_name or args.name}"')
        env_lines.append(f'export DIGIMANCER_QT_DESKTOP_FILE="{args.qt_desktop_file or args.desktop_id}"')
    env_lines.append(f'export PYTHONPATH="{helper_dir}:${{PYTHONPATH:-}}"')

    wrapper_path.parent.mkdir(parents=True, exist_ok=True)
    wrapper_text = "\n".join([
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        f'APP_DIR="${{DIGIMANCER_APP_DIR:-{repo_root}}}"',
        *env_lines,
        'cd "$APP_DIR"',
        f'exec {args.exec_command} "$@"',
        "",
    ])
    wrapper_path.write_text(wrapper_text, encoding="utf-8")
    wrapper_path.chmod(wrapper_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def make_desktop(args: argparse.Namespace, wrapper_path: Path, desktop_path: Path) -> None:
    exec_value = str(wrapper_path)
    if args.accept_files:
        exec_value += " %f"

    lines = [
        "[Desktop Entry]",
        "Type=Application",
        f"Name={args.name}",
        f"Comment={args.comment or args.name}",
        f"Exec={exec_value}",
        f"Icon={args.icon_name}",
        "Terminal=false",
        "Categories=Utility;AudioVideo;",
    ]
    if args.wm_class:
        lines.append(f"StartupWMClass={args.wm_class}")
    if args.mime_type:
        lines.append(f"MimeType={args.mime_type}")

    desktop_path.parent.mkdir(parents=True, exist_ok=True)
    desktop_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def refresh_caches() -> None:
    for cmd in [
        ["gtk-update-icon-cache", str(xdg_data_home() / "icons/hicolor")],
        ["update-desktop-database", str(xdg_data_home() / "applications")],
        ["kbuildsycoca6"],
        ["kbuildsycoca5"],
    ]:
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        except FileNotFoundError:
            pass


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--repo-root", default=".", help="Repo/app root. Default: current directory.")
    p.add_argument("--desktop-id", required=True, help="Desktop file base name, e.g. streamer-board-console")
    p.add_argument("--wrapper-name", required=True, help="Wrapper command name installed into ~/.local/bin")
    p.add_argument("--name", required=True, help="Displayed launcher name")
    p.add_argument("--comment", default="")
    p.add_argument("--exec", dest="exec_command", required=True, help="Command run from repo root, e.g. ./launch_app.sh")
    p.add_argument("--wm-class", default="", help="StartupWMClass value, must match xprop WM_CLASS second value")
    p.add_argument("--icon-name", required=True, help="Icon name used by .desktop")
    p.add_argument("--icon-file", default="", help="Existing icon file to install as icon-name, optional")
    p.add_argument("--text-icon-line1", default="", help="Generate SVG text icon line 1")
    p.add_argument("--text-icon-line2", default="", help="Generate SVG text icon line 2")
    p.add_argument("--text-icon-bg", default="#10351f")
    p.add_argument("--text-icon-fg", default="#00ff75")
    p.add_argument("--tk-class", default="", help="DIGIMANCER_TK_CLASS for Tk apps")
    p.add_argument("--qt-app-name", default="", help="DIGIMANCER_QT_APP_NAME for PySide/Qt apps")
    p.add_argument("--qt-display-name", default="")
    p.add_argument("--qt-desktop-file", default="")
    p.add_argument("--accept-files", action="store_true")
    p.add_argument("--mime-type", default="")
    args = p.parse_args()

    repo_root = Path(args.repo_root).expanduser().resolve()
    data_home = xdg_data_home()
    apps_dir = data_home / "applications"
    icons_dir = data_home / "icons/hicolor/scalable/apps"
    helper_dir = data_home / "digimancer_desktop_identity_py"
    bin_dir = xdg_bin_home()

    helper_dir.mkdir(parents=True, exist_ok=True)
    (helper_dir / "sitecustomize.py").write_text(SITE_CUSTOMIZE_TEXT, encoding="utf-8")

    if args.icon_file:
        src = Path(args.icon_file).expanduser()
        if not src.is_absolute():
            src = repo_root / src
        suffix = src.suffix or ".png"
        dst = icons_dir / f"{args.icon_name}{suffix}"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    elif args.text_icon_line1 or args.text_icon_line2:
        write_text_icon(
            icons_dir / f"{args.icon_name}.svg",
            args.text_icon_line1 or args.icon_name[:3].upper(),
            args.text_icon_line2 or "APP",
            args.text_icon_bg,
            args.text_icon_fg,
        )

    wrapper_path = bin_dir / args.wrapper_name
    desktop_path = apps_dir / f"{args.desktop_id}.desktop"
    make_wrapper(args, helper_dir, repo_root, wrapper_path)
    make_desktop(args, wrapper_path, desktop_path)
    refresh_caches()

    print("Installed desktop identity:")
    print(f"  desktop: {desktop_path}")
    print(f"  wrapper: {wrapper_path}")
    print(f"  helper : {helper_dir / 'sitecustomize.py'}")
    print(f"  class  : {args.wm_class or '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
