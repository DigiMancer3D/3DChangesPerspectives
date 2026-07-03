#!/usr/bin/env python3
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tkinter import filedialog, messagebox
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont
from urllib.parse import urlparse

try:
    import qrcode
    from PIL import Image, ImageTk
    QR_AVAILABLE = True
except Exception:
    qrcode = None
    Image = None
    ImageTk = None
    QR_AVAILABLE = False

APP_NAME = "3DCP Perspective Console"
THEME_NAME = "The Perspective Lab"
APP_VERSION = "1.0.0-rc1"
BUTTSTORE_FORMAT = "3DCP-BUTTSTORE"
BUTTSTORE_ABI = "3dcp.perspective_console.buttstore.v0"

PROJECT_DIR = Path(__file__).resolve().parent

# Version folders should be disposable. Runtime state should not be.
# By default, active .buttstore files and dependency-state files live beside all version folders:
#   ~/3DCP_Perspective_Console_MVP_v0_1/_3dcp_console_user_data/
# This prevents app updates/unzips from overwriting or hiding saved episode files.
INSTALL_ROOT = PROJECT_DIR.parent

DEFAULT_USER_DATA_DIR = INSTALL_ROOT / "user_data"
LEGACY_USER_DATA_DIR = INSTALL_ROOT / "_3dcp_console_user_data"

def file_sha256(path: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def merge_legacy_user_data(legacy_dir: Path, target_dir: Path) -> None:
    """Merge missing runtime files from _3dcp_console_user_data into user_data.

    Existing files in user_data are preserved. ButtStore files are hash-checked so
    exact duplicates are not copied again under migrated_N names.
    """
    if not legacy_dir.exists() or not legacy_dir.is_dir():
        return

    target_dir.mkdir(parents=True, exist_ok=True)

    existing_butt_hashes = set()
    target_buttstores = target_dir / "buttstores"
    if target_buttstores.exists():
        for path in target_buttstores.glob("*.buttstore"):
            try:
                existing_butt_hashes.add(file_sha256(path))
            except Exception:
                pass

    for item in legacy_dir.iterdir():
        dest = target_dir / item.name
        if item.name == "buttstores" and item.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            for src_butt in item.glob("*.buttstore"):
                try:
                    src_hash = file_sha256(src_butt)
                except Exception:
                    continue
                if src_hash in existing_butt_hashes:
                    continue
                target = dest / src_butt.name
                if target.exists():
                    n = 1
                    while True:
                        candidate = dest / f"{src_butt.stem}_legacy_{n}{src_butt.suffix}"
                        if not candidate.exists():
                            target = candidate
                            break
                        n += 1
                shutil.copy2(src_butt, target)
                existing_butt_hashes.add(src_hash)
            continue

        if dest.exists():
            continue
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

def resolve_user_data_dir() -> Path:
    env_path = os.environ.get("DCP3_CONSOLE_USER_DATA")
    if env_path:
        return Path(env_path).expanduser()

    # v0.8.1 rename: _3dcp_console_user_data -> user_data.
    if LEGACY_USER_DATA_DIR.exists() and not DEFAULT_USER_DATA_DIR.exists():
        shutil.move(str(LEGACY_USER_DATA_DIR), str(DEFAULT_USER_DATA_DIR))
    elif LEGACY_USER_DATA_DIR.exists() and DEFAULT_USER_DATA_DIR.exists():
        merge_legacy_user_data(LEGACY_USER_DATA_DIR, DEFAULT_USER_DATA_DIR)

    return DEFAULT_USER_DATA_DIR

USER_DATA_DIR = resolve_user_data_dir()
BUTTSTORE_DIR = USER_DATA_DIR / "buttstores"
RUNTIME_DIR = USER_DATA_DIR / "runtime"
IMPORTED_PNG_DIR = USER_DATA_DIR / "imported_pngs"
DECKBUTT_DIR = USER_DATA_DIR / "deckbutts"
EXPORT_ROOT_DIR = USER_DATA_DIR / "exports"
DUPLICATE_ARCHIVE_ROOT = USER_DATA_DIR / "archived_duplicate_buttstores"

PACKAGE_DATA_DIR = PROJECT_DIR / "data"
TEMPLATE_DIR = PACKAGE_DATA_DIR / "templates"
EMOJI_PRESET_DIR = PACKAGE_DATA_DIR / "emoji_presets"
DEFAULT_TEMPLATE_PATH = TEMPLATE_DIR / "default_episode_template.buttstore"
DEFAULT_EMOJI_PRESET_PATH = EMOJI_PRESET_DIR / "default_presets.emoji"
DEFAULT_BUTTSTORE_PATH = BUTTSTORE_DIR / "default_episode.buttstore"

OUTPUT_TITLE = "3DCP Perspective Console - Output"
CONTROLLER_TITLE = "3DCP Perspective Console - Controller"

OUTPUT_WIDTH = 960
OUTPUT_HEIGHT = 500
DEFAULT_CONTROLLER_GEOMETRY = "1083x874+80+80"
DEFAULT_OUTPUT_GEOMETRY = f"{OUTPUT_WIDTH}x{OUTPUT_HEIGHT}+80+80"

RESOURCE_PROFILES = {
    "low": {"label": "Low resources", "scan_ms": 67, "max_scan_fps": 15, "autosave_delay_ms": 1500},
    "normal": {"label": "Normal resources", "scan_ms": 42, "max_scan_fps": 24, "autosave_delay_ms": 1000},
    "full": {"label": "Full performance", "scan_ms": 33, "max_scan_fps": 30, "autosave_delay_ms": 600},
}
SOURCE_TYPES = ["Official", "Primary", "Secondary", "Unknown"]
CONFIDENCE_LEVELS = ["High", "Medium", "Low", "Still Checking"]
VERDICTS = ["Supported", "Partial", "Unsupported", "Needs Proof", "Still Checking"]

FALLBACK_EMOJI_PRESETS = [
    {"emoji": "✅", "name": "Check", "category": "Status"},
    {"emoji": "❌", "name": "Cross", "category": "Status"},
    {"emoji": "✨", "name": "Sparkles", "category": "Lab"},
    {"emoji": "🔥", "name": "Fire", "category": "Lab"},
    {"emoji": "🔍", "name": "Magnifier", "category": "Lab"},
    {"emoji": "👀", "name": "Eyes", "category": "People"},
    {"emoji": "💀", "name": "Skull", "category": "People"},
    {"emoji": "🫠", "name": "Melting Face", "category": "People"},
    {"emoji": "📍", "name": "Pin", "category": "Places"},
    {"emoji": "👉", "name": "Point Right", "category": "Arrows"},
    {"emoji": "👇", "name": "Point Down", "category": "Arrows"},
    {"emoji": "➡️", "name": "Arrow Right", "category": "Arrows"},
    {"emoji": "⬇️", "name": "Arrow Down", "category": "Arrows"},
    {"emoji": "⬅️", "name": "Arrow Left", "category": "Arrows"},
    {"emoji": "🔜", "name": "Soon", "category": "Arrows"},
    {"emoji": "🔙", "name": "Back", "category": "Arrows"},
    {"emoji": "🔚", "name": "End", "category": "Arrows"},
    {"emoji": "💚", "name": "Green Heart", "category": "Shapes"},
    {"emoji": "🟢", "name": "Green Circle", "category": "Shapes"},
    {"emoji": "🟩", "name": "Green Square", "category": "Shapes"},
    {"emoji": "9️⃣", "name": "Number Nine", "category": "Numbers"},
    {"emoji": "📱", "name": "Phone", "category": "Objects"},
    {"emoji": "☢️", "name": "Radioactive", "category": "Symbols"},
    {"emoji": "🔗", "name": "Link", "category": "Objects"},
    {"emoji": "⛓️", "name": "Chains", "category": "Objects"},
    {"emoji": "🧠", "name": "Brain", "category": "Lab"},
    {"emoji": "🧪", "name": "Test Tube", "category": "Lab"},
    {"emoji": "🧾", "name": "Receipt", "category": "Objects"},
    {"emoji": "🛰️", "name": "Satellite", "category": "Objects"},
    {"emoji": "📊", "name": "Chart", "category": "Objects"},
    {"emoji": "📈", "name": "Up Chart", "category": "Objects"},
    {"emoji": "📉", "name": "Down Chart", "category": "Objects"},
    {"emoji": "₿", "name": "Bitcoin", "category": "Crypto"},
    {"emoji": "🪙", "name": "Coin", "category": "Crypto"},
    {"emoji": "🔒", "name": "Lock", "category": "Crypto"},
    {"emoji": "🔓", "name": "Unlock", "category": "Crypto"},
    {"emoji": "🐂", "name": "Bull", "category": "Animals"},
    {"emoji": "🐻", "name": "Bear", "category": "Animals"},
    {"emoji": "🌍", "name": "Globe", "category": "Places"},
    {"emoji": "🏛️", "name": "Bank", "category": "Places"},
    {"emoji": "🍞", "name": "Bread", "category": "Food"},
    {"emoji": "🍕", "name": "Pizza", "category": "Food"},
    {"emoji": "☕", "name": "Coffee", "category": "Food"},
]

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def safe_read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)

def safe_write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    with temp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")
    temp_path.replace(path)


def load_emoji_presets_from_file(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8")
    items: list[dict] = []
    for record in raw.split("/,"):
        record = record.strip()
        if not record:
            continue
        parts = [part.strip() for part in record.split("|")]
        emoji = parts[0] if len(parts) >= 1 else ""
        name = parts[1] if len(parts) >= 2 and parts[1] else f"Emoji {len(items) + 1}"
        category = parts[2] if len(parts) >= 3 and parts[2] else "General"
        if emoji:
            items.append({"emoji": emoji, "name": name[:32], "category": category[:24]})
    return items

def normalize_hex_color(value: str, fallback: str = "#e8fff5") -> str:
    value = (value or "").strip()
    if re.match(r"^#[0-9a-fA-F]{6}$", value):
        return value.lower()
    return fallback.lower()

def blend_hex_colors(fg_hex: str, bg_hex: str, opacity: float) -> str:
    fg_hex = normalize_hex_color(fg_hex, "#e8fff5")
    bg_hex = normalize_hex_color(bg_hex, "#121418")
    opacity = max(0.0, min(1.0, float(opacity)))

    def parts(h: str) -> tuple[int, int, int]:
        return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)

    fr, fg, fb = parts(fg_hex)
    br, bg, bb = parts(bg_hex)
    r = int((fr * opacity) + (br * (1.0 - opacity)))
    g = int((fg * opacity) + (bg * (1.0 - opacity)))
    b = int((fb * opacity) + (bb * (1.0 - opacity)))
    return f"#{r:02x}{g:02x}{b:02x}"

def new_card(card_type: str = "source_analyzer", label: str = "Source Analyzer") -> dict:
    if card_type == "blank":
        return {"id": "blank-hide", "label": "Blank / Hide", "type": "blank", "fields": {}, "layers": []}
    return {
        "id": "source-analyzer",
        "label": label,
        "type": "source_analyzer",
        "fields": {
            "sourceType": "Primary",
            "confidence": "Medium",
            "sourceLink": "",
            "claim": "Current claim goes here.",
            "evidence": "Evidence shown on browser or cited source.",
            "openQuestion": "What still needs checking?",
            "verdict": "Still Checking",
        },
        "layers": [
            {"id": "emoji-default-scan", "type": "emoji", "name": "Scan Magnifier", "text": "🔍", "x": 900, "y": 210, "size": 26, "opacity": 1.0, "z": 10}
        ],
    }

def make_default_buttstore(preserve_footer: dict | None = None) -> dict:
    now = utc_now()
    footer = {
        "serial": 1, "high_water_serial": 1, "save_count": 0, "created_serial": 1,
        "last_wipe_serial": 0, "public_clean_ready": False, "history": [],
        "notes": "Footer values are forward-only unless the user performs a to-default wipe.",
    }
    if preserve_footer:
        previous_high = int(preserve_footer.get("high_water_serial", 1))
        previous_save_count = int(preserve_footer.get("save_count", 0))
        previous_history = list(preserve_footer.get("history", []))[-20:]
        footer.update({
            "serial": previous_high + 1,
            "high_water_serial": previous_high + 1,
            "save_count": previous_save_count,
            "created_serial": preserve_footer.get("created_serial", 1),
            "last_wipe_serial": previous_high + 1,
            "history": previous_history,
        })
    cards = [new_card(), new_card("blank", "Blank / Hide")]
    return {
        "buttstore_format": BUTTSTORE_FORMAT,
        "version": APP_VERSION,
        "header": {
            "magic": "3DCP_BUTTSTORE", "abi": BUTTSTORE_ABI, "project": APP_NAME, "theme": THEME_NAME,
            "created_at": now, "modified_at": now, "active_card_id": "source-analyzer",
            "resource_profile": "low",
            "output": {"width": OUTPUT_WIDTH, "height": OUTPUT_HEIGHT, "background": "#121418", "title": OUTPUT_TITLE},
            "quick_cards": [{"id": c["id"], "label": c["label"], "type": c["type"]} for c in cards],
        },
        "under_header": {
            "dirty": False, "output_visible": True, "output_topmost": False, "output_borderless": False,
            "controller_geometry": DEFAULT_CONTROLLER_GEOMETRY,
            "output_geometry": DEFAULT_OUTPUT_GEOMETRY,
            "scan_loop": False, "scan_speed_ms": 67, "scanner_color": "#00ff99",
            "last_loaded_path": str(DEFAULT_BUTTSTORE_PATH), "last_runtime_event": "default-created",
            "scratch": {"selected_layer_id": None, "unsaved_note": ""},
        },
        "stage": {"abi_style": "draft values live here before they are applied into body/cards", "draft_cards": {}, "save_body_pending": False},
        "body": {"cards": cards},
        "footer": footer,
    }

def is_safe_geometry(geometry: str, min_w: int = 320, min_h: int = 200) -> bool:
    """Basic guard against invisible/off-screen saved geometry.

    Tk geometry examples:
      960x500+80+80
      960x500-32000+40
    """
    if not geometry or not isinstance(geometry, str):
        return False

    import re
    m = re.match(r"^(\d+)x(\d+)([+-]\d+)([+-]\d+)$", geometry.strip())
    if not m:
        return False

    width = int(m.group(1))
    height = int(m.group(2))
    x = int(m.group(3))
    y = int(m.group(4))

    if width < min_w or height < min_h:
        return False

    # Multi-monitor safe guard: allow reasonable negative X, but reject huge phantom coordinates.
    if x < -5000 or x > 10000 or y < -1000 or y > 5000:
        return False

    return True


def repair_runtime_visibility(data: dict) -> bool:
    """Repair output visibility/geometry without deleting user card content.

    Returns True if changes were made.
    """
    changed = False
    under = data.setdefault("under_header", {})

    if under.get("output_visible") is not True:
        under["output_visible"] = True
        changed = True

    output_geo = under.get("output_geometry", "")
    if not is_safe_geometry(output_geo, 320, 200):
        under["output_geometry"] = DEFAULT_OUTPUT_GEOMETRY
        changed = True

    controller_geo = under.get("controller_geometry", "")
    if under.get("controller_geometry_migrated_v082") is not True:
        under["controller_geometry"] = DEFAULT_CONTROLLER_GEOMETRY
        under["controller_geometry_migrated_v082"] = True
        changed = True
    elif controller_geo and not is_safe_geometry(controller_geo, 320, 200):
        under["controller_geometry"] = DEFAULT_CONTROLLER_GEOMETRY
        changed = True

    if under.get("scan_loop") is True:
        under["scan_loop"] = False
        changed = True

    if changed:
        under["last_runtime_event"] = "auto-visibility-geometry-repair"

    return changed


def discover_legacy_buttstores() -> list[Path]:
    """Find .buttstore files saved inside older version folders.

    This is read-only discovery. It never deletes or modifies legacy files.
    """
    candidates: list[Path] = []
    search_roots = [INSTALL_ROOT, PROJECT_DIR]
    seen: set[Path] = set()

    for root in search_roots:
        if not root.exists():
            continue
        for path in root.glob("**/*.buttstore"):
            try:
                resolved = path.resolve()
            except Exception:
                resolved = path
            if resolved in seen:
                continue
            seen.add(resolved)

            # Skip files already in shared user data and package templates.
            # Also skip templates from older version folders; those are package defaults, not user saves.
            if USER_DATA_DIR in path.parents:
                continue
            if TEMPLATE_DIR in path.parents:
                continue
            if path.name.endswith(".tmp"):
                continue
            if "template" in path.name.lower():
                continue
            if any(part.lower() == "templates" for part in path.parts):
                continue
            candidates.append(path)

    candidates.sort(key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
    return candidates


def migrate_legacy_buttstores() -> list[Path]:
    """Conservative no-op migration inside the app.

    Older builds copied .buttstore files from every old version folder, which could
    re-create duplicates after the user had cleaned them up. v0.8.3 keeps app launch
    safe and non-copying. The standalone migration script only merges the old shared
    data folder and no longer imports old version-folder .buttstore files by default.
    """
    BUTTSTORE_DIR.mkdir(parents=True, exist_ok=True)
    return []


def ensure_default_buttstore_exists() -> None:
    """Create the shared default .buttstore only if missing.

    Priority:
    1. If old version folders contain default_episode.buttstore, migrate/copy the newest one.
    2. Else use the package template.
    3. Else generate a default from code.

    Existing shared .buttstore files are never replaced here.
    """
    BUTTSTORE_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    IMPORTED_PNG_DIR.mkdir(parents=True, exist_ok=True)
    DECKBUTT_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_ROOT_DIR.mkdir(parents=True, exist_ok=True)

    copied = migrate_legacy_buttstores()

    if DEFAULT_BUTTSTORE_PATH.exists():
        data = safe_read_json(DEFAULT_BUTTSTORE_PATH)
        ButtStore.validate_or_repair(data)
        if repair_runtime_visibility(data):
            safe_write_json(DEFAULT_BUTTSTORE_PATH, data)
        return

    # Prefer a migrated old default_episode.buttstore if one exists.
    migrated_defaults = [p for p in copied if p.name == "default_episode.buttstore"]
    if migrated_defaults:
        newest = max(migrated_defaults, key=lambda p: p.stat().st_mtime if p.exists() else 0)
        if newest != DEFAULT_BUTTSTORE_PATH:
            shutil.copy2(newest, DEFAULT_BUTTSTORE_PATH)
        return

    # If migration copied only custom names, leave them intact and create a runtime default.
    if DEFAULT_TEMPLATE_PATH.exists():
        data = safe_read_json(DEFAULT_TEMPLATE_PATH)
        ButtStore.validate_or_repair(data)
        data["under_header"]["last_runtime_event"] = "created-from-template-shared-user-data"
        repair_runtime_visibility(data)
        safe_write_json(DEFAULT_BUTTSTORE_PATH, data)
        return

    safe_write_json(DEFAULT_BUTTSTORE_PATH, make_default_buttstore())



@dataclass
class ButtStore:
    path: Path
    data: dict

    @classmethod
    def load_or_create(cls, path: Path) -> "ButtStore":
        path.parent.mkdir(parents=True, exist_ok=True)

        # Safety rule:
        # Loading or updating the app must never delete, wipe, or overwrite an existing .buttstore.
        if path == DEFAULT_BUTTSTORE_PATH:
            ensure_default_buttstore_exists()

        if not path.exists():
            data = make_default_buttstore()
            safe_write_json(path, data)
            return cls(path=path, data=data)

        data = safe_read_json(path)
        cls.validate_or_repair(data)
        if path == DEFAULT_BUTTSTORE_PATH and repair_runtime_visibility(data):
            safe_write_json(path, data)
        return cls(path=path, data=data)

    @staticmethod
    def validate_or_repair(data: dict) -> None:
        if data.get("buttstore_format") != BUTTSTORE_FORMAT:
            raise ValueError("This file is not a 3DCP .buttstore file.")
        data.setdefault("version", APP_VERSION)
        data.setdefault("header", {})
        data.setdefault("under_header", {})
        data.setdefault("stage", {})
        data.setdefault("body", {})
        data.setdefault("footer", {})
        header = data["header"]
        header.setdefault("magic", "3DCP_BUTTSTORE")
        header.setdefault("abi", BUTTSTORE_ABI)
        header.setdefault("project", APP_NAME)
        header.setdefault("theme", THEME_NAME)
        header.setdefault("created_at", utc_now())
        header.setdefault("modified_at", utc_now())
        header.setdefault("active_card_id", "source-analyzer")
        header.setdefault("resource_profile", "low")
        header.setdefault("output", {"width": OUTPUT_WIDTH, "height": OUTPUT_HEIGHT, "background": "#121418", "title": OUTPUT_TITLE})
        under = data["under_header"]
        under.setdefault("dirty", False)
        under.setdefault("output_visible", True)
        under.setdefault("output_topmost", False)
        under.setdefault("output_borderless", False)
        # v0.9.2 safety: never restore borderless/topmost automatically at launch.
        # Apply OBS Mode can still enable it during a session.
        if under.get("output_borderless") is True or under.get("output_topmost") is True:
            under["output_borderless"] = False
            under["output_topmost"] = False
            changed = True
        under.setdefault("controller_geometry", DEFAULT_CONTROLLER_GEOMETRY)
        under.setdefault("output_geometry", DEFAULT_OUTPUT_GEOMETRY)
        under.setdefault("scan_loop", False)
        under.setdefault("scan_speed_ms", RESOURCE_PROFILES["low"]["scan_ms"])
        under.setdefault("scanner_color", "#00ff99")
        under.setdefault("scratch", {})
        stage = data["stage"]
        stage.setdefault("draft_cards", {})
        stage.setdefault("save_body_pending", False)
        body = data["body"]
        if not body.get("cards"):
            body["cards"] = [new_card(), new_card("blank", "Blank / Hide")]
        for card in body["cards"]:
            fields = card.setdefault("fields", {})
            card.setdefault("layers", [])
            if card.get("type") == "source_analyzer":
                fields.setdefault("sourceType", "Unknown")
                fields.setdefault("confidence", "Still Checking")
                fields.setdefault("sourceLink", "")
                fields.setdefault("claim", "")
                fields.setdefault("evidence", "")
                fields.setdefault("openQuestion", "")
                fields.setdefault("verdict", "Still Checking")
            emoji_index = 1
            image_index = 1
            text_index = 1
            for layer in card.get("layers", []):
                if layer.get("type") == "emoji":
                    layer.setdefault("visible", True)
                    if not str(layer.get("name", "")).strip():
                        if layer.get("id") == "emoji-default-scan":
                            layer["name"] = "Scan Magnifier"
                        else:
                            layer["name"] = f"Emoji {emoji_index}"
                    emoji_index += 1
                elif layer.get("type") == "image":
                    layer.setdefault("visible", True)
                    if not str(layer.get("name", "")).strip():
                        layer["name"] = f"Image {image_index}"
                    layer.setdefault("source_path", "")
                    layer.setdefault("scale", 100)
                    layer.setdefault("opacity", 1.0)
                    image_index += 1
                elif layer.get("type") == "text":
                    layer.setdefault("visible", True)
                    if not str(layer.get("name", "")).strip():
                        layer["name"] = f"Text {text_index}"
                    layer.setdefault("text", "New text layer")
                    layer.setdefault("size", 22)
                    layer.setdefault("color", "#e8fff5")
                    layer.setdefault("opacity", 1.0)
                    layer.setdefault("wrap_width", 260)
                    text_index += 1
        footer = data["footer"]
        footer.setdefault("serial", 1)
        footer.setdefault("high_water_serial", max(1, int(footer.get("serial", 1))))
        footer.setdefault("save_count", 0)
        footer.setdefault("created_serial", 1)
        footer.setdefault("last_wipe_serial", 0)
        footer.setdefault("public_clean_ready", False)
        footer.setdefault("history", [])
        header["quick_cards"] = [{"id": c.get("id"), "label": c.get("label"), "type": c.get("type")} for c in body["cards"]]

    def cards(self) -> list[dict]:
        return self.data["body"]["cards"]

    def get_card(self, card_id: str) -> dict | None:
        for card in self.cards():
            if card.get("id") == card_id:
                return card
        return None

    def active_card(self) -> dict:
        active_id = self.data["header"].get("active_card_id", "source-analyzer")
        card = self.get_card(active_id)
        if card is None:
            card = self.cards()[0]
            self.data["header"]["active_card_id"] = card.get("id")
        return card

    def set_active_card(self, card_id: str) -> None:
        if self.get_card(card_id) is None:
            return
        self.data["header"]["active_card_id"] = card_id
        self.mark_dirty("active-card-changed")

    def mark_dirty(self, event: str = "changed") -> None:
        self.data["under_header"]["dirty"] = True
        self.data["under_header"]["last_runtime_event"] = event
        self.data["header"]["modified_at"] = utc_now()

    def bump_footer_for_save(self, reason: str) -> None:
        footer = self.data["footer"]
        high = int(footer.get("high_water_serial", 1)) + 1
        footer["serial"] = high
        footer["high_water_serial"] = high
        footer["save_count"] = int(footer.get("save_count", 0)) + 1
        footer.setdefault("history", [])
        footer["history"].append({"serial": high, "at": utc_now(), "reason": reason, "path": str(self.path)})
        footer["history"] = footer["history"][-50:]

    def save(self, reason: str = "manual-save") -> None:
        self.data["header"]["modified_at"] = utc_now()
        self.data["under_header"]["dirty"] = False
        self.data["stage"]["save_body_pending"] = False
        self.data["header"]["quick_cards"] = [{"id": c.get("id"), "label": c.get("label"), "type": c.get("type")} for c in self.cards()]
        self.bump_footer_for_save(reason)
        safe_write_json(self.path, self.data)

    def save_as(self, path: Path) -> None:
        self.path = path
        self.data["under_header"]["last_loaded_path"] = str(path)
        self.save("save-as")

    def wipe_to_default(self) -> None:
        preserved_footer = copy.deepcopy(self.data.get("footer", {}))
        self.data = make_default_buttstore(preserve_footer=preserved_footer)
        self.data["under_header"]["last_runtime_event"] = "to-default-wipe"
        self.data["footer"]["public_clean_ready"] = True
        self.save("to-default-wipe")

class PerspectiveConsoleApp:
    def __init__(self) -> None:
        self.store = ButtStore.load_or_create(DEFAULT_BUTTSTORE_PATH)
        self.root = tk.Tk()
        self.root.title(f"{CONTROLLER_TITLE} v{APP_VERSION}")
        self.root.minsize(1080, 760)
        saved_controller_geo = self.store.data["under_header"].get("controller_geometry") or DEFAULT_CONTROLLER_GEOMETRY
        try:
            self.root.geometry(saved_controller_geo)
        except tk.TclError:
            self.root.geometry(DEFAULT_CONTROLLER_GEOMETRY)
        self.output = tk.Toplevel(self.root)
        self.output.title(OUTPUT_TITLE)
        self.output.geometry(self.store.data["under_header"].get("output_geometry", f"{OUTPUT_WIDTH}x{OUTPUT_HEIGHT}+960+80"))
        self.output.resizable(False, False)
        self.output.protocol("WM_DELETE_WINDOW", self.hide_output)
        self.output_canvas = tk.Canvas(self.output, width=OUTPUT_WIDTH, height=OUTPUT_HEIGHT, bg=self.store.data["header"]["output"].get("background", "#121418"), highlightthickness=0)
        self.output_canvas.pack(fill="both", expand=True)

        self.scan_y = 0
        self.scan_active = False
        self.scan_token = 0
        self.scan_loop_var = tk.BooleanVar(value=bool(self.store.data["under_header"].get("scan_loop", False)))
        self.output_visible_var = tk.BooleanVar(value=bool(self.store.data["under_header"].get("output_visible", True)))
        # v0.9.2 output recovery: always start in normal framed mode.
        # Borderless/topmost can be re-enabled from Output Tools after the window is visible.
        self.output_topmost_var = tk.BooleanVar(value=False)
        self.output_borderless_var = tk.BooleanVar(value=False)
        self.resource_profile_var = tk.StringVar(value=self.store.data["header"].get("resource_profile", "low"))
        if self.resource_profile_var.get() not in RESOURCE_PROFILES:
            self.resource_profile_var.set("low")
        self.scan_speed_var = tk.IntVar(value=int(self.store.data["under_header"].get("scan_speed_ms", RESOURCE_PROFILES["low"]["scan_ms"])))
        self.scanner_color_var = tk.StringVar(value=self.store.data["under_header"].get("scanner_color", "#00ff99"))
        self.source_type_var = tk.StringVar()
        self.confidence_var = tk.StringVar()
        self.verdict_var = tk.StringVar()
        self.source_link_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Ready")
        self.card_label_var = tk.StringVar(value="Source Analyzer")

        # v0.3.1 emoji sticker editor state
        self.selected_sticker_id_var = tk.StringVar(value="")
        self.selected_sticker_label_var = tk.StringVar(value="")
        self.sticker_text_var = tk.StringVar(value="🧪")
        self.sticker_name_var = tk.StringVar(value="Emoji 1")
        self.sticker_x_var = tk.IntVar(value=820)
        self.sticker_y_var = tk.IntVar(value=340)
        self.sticker_size_var = tk.IntVar(value=28)
        self.sticker_opacity_var = tk.DoubleVar(value=1.0)
        self.sticker_label_to_id = {}
        self.emoji_preset_items = []
        self.emoji_preset_listbox = None

        # v0.4 image layer editor state
        self.selected_image_id_var = tk.StringVar(value="")
        self.selected_image_label_var = tk.StringVar(value="")
        self.image_name_var = tk.StringVar(value="Image 1")
        self.image_x_var = tk.IntVar(value=760)
        self.image_y_var = tk.IntVar(value=245)
        self.image_scale_var = tk.IntVar(value=100)
        self.image_opacity_var = tk.DoubleVar(value=1.0)
        self.image_path_var = tk.StringVar(value="")
        self.image_label_to_id = {}
        self.image_selector = None
        self.render_image_refs = []
        self.base_image_cache = {}
        self.rendered_image_cache = {}

        # v0.5 text layer editor state
        self.selected_text_layer_id_var = tk.StringVar(value="")
        self.selected_text_layer_label_var = tk.StringVar(value="")
        self.text_layer_name_var = tk.StringVar(value="Text 1")
        self.text_layer_x_var = tk.IntVar(value=740)
        self.text_layer_y_var = tk.IntVar(value=185)
        self.text_layer_size_var = tk.IntVar(value=22)
        self.text_layer_opacity_var = tk.DoubleVar(value=1.0)
        self.text_layer_color_var = tk.StringVar(value="#e8fff5")
        self.text_layer_wrap_var = tk.IntVar(value=260)
        self.text_layer_label_to_id = {}
        self.text_layer_selector = None
        self.text_layer_text = None

        self.card_buttons = {}
        self.deck_button_frame = None
        self.deck_storage_listbox = None
        self.deck_storage_ids = []
        self.pending_deck_swap = None
        self.max_deck_buttons = 6
        self.hotkeys_enabled_var = tk.BooleanVar(value=True)
        self.sticker_selector = None
        self.autosave_after_id = None
        self.qr_photo = None
        self.qr_cache_link = None
        self.build_controller()
        self.load_active_card_into_editor()
        self.redraw_output()
        self.recover_output_window_on_launch()
        if not self.output_visible_var.get():
            self.output.withdraw()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind_controller_hotkeys()
        # Archive duplicate-looking buttstores after the UI is ready so the user can review them during the session.
        self.root.after(1200, self.archive_duplicate_buttstores_after_load)

    def hotkey_should_run(self) -> bool:
        if not self.hotkeys_enabled_var.get():
            return False
        focused = self.root.focus_get()
        # Let normal text entry/editing widgets keep their expected typing shortcuts.
        if focused is not None and isinstance(focused, (tk.Entry, tk.Text, ttk.Entry, ttk.Combobox, ttk.Spinbox)):
            return False
        return True

    def run_hotkey(self, callback) -> str:
        if self.hotkey_should_run():
            callback()
            return "break"
        return ""

    def select_deck_hotkey(self, index: int) -> None:
        cards = self.store.cards()
        if 0 <= index < min(len(cards), self.max_deck_buttons):
            self.select_card(cards[index]["id"])

    def toggle_scan_loop_hotkey(self) -> None:
        self.scan_loop_var.set(not bool(self.scan_loop_var.get()))
        self.toggle_scan_loop()

    def delete_active_card_hotkey(self) -> None:
        # Safer hotkey delete: still asks through the normal delete path.
        self.delete_active_card()

    def bind_controller_hotkeys(self) -> None:
        # Deck/card selection.
        for n in range(1, 7):
            self.root.bind_all(f"<Control-Key-{n}>", lambda _event, idx=n-1: self.run_hotkey(lambda: self.select_deck_hotkey(idx)))

        self.root.bind_all("<Control-b>", lambda _event: self.run_hotkey(lambda: self.select_card("blank-hide")))
        self.root.bind_all("<Control-B>", lambda _event: self.run_hotkey(lambda: self.select_card("blank-hide")))

        # Card management.
        self.root.bind_all("<Control-d>", lambda _event: self.run_hotkey(self.duplicate_active_card))
        self.root.bind_all("<Control-D>", lambda _event: self.run_hotkey(self.duplicate_active_card))
        self.root.bind_all("<Control-Shift-D>", lambda _event: self.run_hotkey(self.delete_active_card_hotkey))

        # Output / scanner.
        self.root.bind_all("<Control-o>", lambda _event: self.run_hotkey(self.show_output))
        self.root.bind_all("<Control-O>", lambda _event: self.run_hotkey(self.show_output))
        self.root.bind_all("<Control-Shift-O>", lambda _event: self.run_hotkey(self.hide_output))
        self.root.bind_all("<Control-r>", lambda _event: self.run_hotkey(self.scan_once))
        self.root.bind_all("<Control-R>", lambda _event: self.run_hotkey(self.scan_once))
        self.root.bind_all("<Control-l>", lambda _event: self.run_hotkey(self.toggle_scan_loop_hotkey))
        self.root.bind_all("<Control-L>", lambda _event: self.run_hotkey(self.toggle_scan_loop_hotkey))

        # Save / load / export.
        self.root.bind_all("<Control-s>", lambda _event: self.run_hotkey(self.save_now))
        self.root.bind_all("<Control-S>", lambda _event: self.run_hotkey(self.save_now))
        self.root.bind_all("<Control-Shift-S>", lambda _event: self.run_hotkey(self.save_as))
        self.root.bind_all("<Control-Shift-L>", lambda _event: self.run_hotkey(self.load_buttstore))
        self.root.bind_all("<Control-e>", lambda _event: self.run_hotkey(self.export_current_card_png))
        self.root.bind_all("<Control-E>", lambda _event: self.run_hotkey(self.export_current_card_png))
        self.root.bind_all("<Control-Shift-E>", lambda _event: self.run_hotkey(self.export_all_cards_png))
        self.root.bind_all("<Control-Shift-R>", lambda _event: self.run_hotkey(self.reset_output_window_position))
        self.root.bind_all("<Control-Alt-r>", lambda _event: self.run_hotkey(self.rescue_output_window))
        self.root.bind_all("<Control-Alt-R>", lambda _event: self.run_hotkey(self.rescue_output_window))
        self.root.bind_all("<Control-Alt-o>", lambda _event: self.run_hotkey(lambda: self.disable_obs_output_mode() if self.output_borderless_var.get() else self.enable_obs_output_mode()))
        self.root.bind_all("<Control-Alt-O>", lambda _event: self.run_hotkey(lambda: self.disable_obs_output_mode() if self.output_borderless_var.get() else self.enable_obs_output_mode()))

    def build_controller(self) -> None:
        self.root.columnconfigure(0, weight=0)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)
        left = ttk.Frame(self.root, padding=10)
        left.grid(row=0, column=0, sticky="ns")
        right = ttk.Frame(self.root, padding=10)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(1, weight=1)
        right.rowconfigure(8, weight=1)
        right.rowconfigure(10, weight=1)
        right.rowconfigure(12, weight=1)
        ttk.Label(left, text="The Perspective Lab", font=("TkDefaultFont", 13, "bold")).pack(anchor="w")
        ttk.Label(left, text="Deck buttons").pack(anchor="w", pady=(8, 4))
        self.deck_button_frame = ttk.Frame(left)
        self.deck_button_frame.pack(fill="x")
        self.refresh_deck_buttons()

        ttk.Separator(left).pack(fill="x", pady=10)
        ttk.Button(left, text="Show Output", command=self.show_output).pack(fill="x", pady=2)
        ttk.Button(left, text="Hide Output", command=self.hide_output).pack(fill="x", pady=2)
        ttk.Checkbutton(left, text="Output visible on restart", variable=self.output_visible_var, command=self.on_setting_changed).pack(anchor="w", pady=(6, 2))
        ttk.Separator(left).pack(fill="x", pady=10)
        ttk.Button(left, text="Scan Once", command=self.scan_once).pack(fill="x", pady=2)
        ttk.Checkbutton(left, text="Scan Loop", variable=self.scan_loop_var, command=self.toggle_scan_loop).pack(anchor="w", pady=(6, 2))
        ttk.Label(left, text="Resource profile").pack(anchor="w", pady=(10, 2))
        profile_combo = ttk.Combobox(left, state="readonly", textvariable=self.resource_profile_var, values=list(RESOURCE_PROFILES.keys()), width=21)
        profile_combo.pack(fill="x")
        profile_combo.bind("<<ComboboxSelected>>", self.on_resource_profile_changed)
        ttk.Label(left, text="Scan frame delay ms").pack(anchor="w", pady=(10, 2))
        speed = ttk.Scale(left, from_=20, to=120, orient="horizontal", command=self.on_scan_speed_drag)
        speed.set(self.scan_speed_var.get())
        speed.pack(fill="x")
        self.speed_scale = speed
        self.speed_label = ttk.Label(left, text=f"{self.scan_speed_var.get()} ms")
        self.speed_label.pack(anchor="w")
        ttk.Label(left, text="Scanner color").pack(anchor="w", pady=(8, 2))
        ttk.Entry(left, textvariable=self.scanner_color_var, width=22).pack(fill="x")
        ttk.Button(left, text="Apply Style", command=self.apply_editor_to_card).pack(fill="x", pady=(8, 2))
        ttk.Separator(left).pack(fill="x", pady=10)
        ttk.Label(left, text="PNG export").pack(anchor="w", pady=(0, 4))
        ttk.Button(left, text="Export Card PNG", command=self.export_current_card_png).pack(fill="x", pady=2)
        ttk.Button(left, text="Export All PNGs", command=self.export_all_cards_png).pack(fill="x", pady=2)

        ttk.Label(right, text="Source Analyzer Editor", font=("TkDefaultFont", 14, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(right, text="Source Type").grid(row=1, column=0, sticky="w", pady=(12, 2))
        ttk.Combobox(right, state="readonly", textvariable=self.source_type_var, values=SOURCE_TYPES).grid(row=1, column=1, sticky="ew", pady=(12, 2))
        ttk.Label(right, text="Confidence").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Combobox(right, state="readonly", textvariable=self.confidence_var, values=CONFIDENCE_LEVELS).grid(row=2, column=1, sticky="ew", pady=2)
        ttk.Label(right, text="Verdict").grid(row=3, column=0, sticky="w", pady=2)
        ttk.Combobox(right, state="readonly", textvariable=self.verdict_var, values=VERDICTS).grid(row=3, column=1, sticky="ew", pady=2)
        ttk.Label(right, text="Source Link (for QR)").grid(row=4, column=0, sticky="w", pady=(6, 2))
        ttk.Entry(right, textvariable=self.source_link_var).grid(row=4, column=1, sticky="ew", pady=(6, 2))
        ttk.Label(right, text="Current Claim").grid(row=7, column=0, columnspan=2, sticky="w", pady=(12, 2))
        self.claim_text = tk.Text(right, height=4, wrap="word", undo=True)
        self.claim_text.grid(row=8, column=0, columnspan=2, sticky="nsew")
        ttk.Label(right, text="Evidence Shown").grid(row=9, column=0, columnspan=2, sticky="w", pady=(12, 2))
        self.evidence_text = tk.Text(right, height=4, wrap="word", undo=True)
        self.evidence_text.grid(row=10, column=0, columnspan=2, sticky="nsew")
        ttk.Label(right, text="Open Question").grid(row=11, column=0, columnspan=2, sticky="w", pady=(12, 2))
        self.open_question_text = tk.Text(right, height=4, wrap="word", undo=True)
        self.open_question_text.grid(row=12, column=0, columnspan=2, sticky="nsew")
        layer_notebook = ttk.Notebook(right)
        layer_notebook.grid(row=13, column=0, columnspan=2, sticky="ew", pady=(12, 0))

        deck_frame = ttk.Frame(layer_notebook, padding=8)
        sticker_frame = ttk.Frame(layer_notebook, padding=8)
        image_frame = ttk.Frame(layer_notebook, padding=8)
        text_layer_frame = ttk.Frame(layer_notebook, padding=8)
        layer_notebook.add(deck_frame, text="Deck Cards")
        output_tools_frame = ttk.Frame(layer_notebook, padding=8)
        hotkeys_frame = ttk.Frame(layer_notebook, padding=8)
        layer_notebook.add(sticker_frame, text="Emoji Stickers")
        layer_notebook.add(image_frame, text="PNG Images")
        layer_notebook.add(text_layer_frame, text="Text Layers")
        layer_notebook.add(output_tools_frame, text="Output Tools")
        layer_notebook.add(hotkeys_frame, text="Hotkeys")

        deck_frame.columnconfigure(0, weight=0, minsize=452)
        deck_frame.columnconfigure(1, weight=1)
        deck_left = ttk.Frame(deck_frame)
        deck_left.grid(row=0, column=0, sticky="nw", padx=(0, 12))
        deck_right = ttk.Frame(deck_frame)
        deck_right.grid(row=0, column=1, sticky="nsew")
        deck_right.columnconfigure(0, weight=1)
        deck_right.rowconfigure(1, weight=1)

        ttk.Label(deck_left, text="Card Label").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(deck_left, textvariable=self.card_label_var, width=26).grid(row=0, column=1, columnspan=2, sticky="ew", pady=2)

        ttk.Button(deck_left, text="Rename Card", command=self.rename_active_card).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(6, 2))

        deck_add_buttons = ttk.Frame(deck_left)
        deck_add_buttons.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(4, 0))
        ttk.Button(deck_add_buttons, text="Add Source", command=self.add_source_card).pack(side="left")
        ttk.Button(deck_add_buttons, text="Add Blank", command=self.add_blank_card).pack(side="left", padx=6)
        ttk.Button(deck_add_buttons, text="Duplicate Card", command=self.duplicate_active_card).pack(side="left", padx=6)
        ttk.Button(deck_add_buttons, text="Delete Card", command=self.delete_active_card).pack(side="left", padx=6)

        deck_file_buttons = ttk.Frame(deck_left)
        deck_file_buttons.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        ttk.Button(deck_file_buttons, text="Save Card", command=self.save_card_deckbutt).pack(side="left")
        ttk.Button(deck_file_buttons, text="Load Card", command=self.load_card_deckbutt).pack(side="left", padx=6)

        deck_export_buttons = ttk.Frame(deck_left)
        deck_export_buttons.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(6, 0))
        ttk.Button(deck_export_buttons, text="Export Card PNG", command=self.export_current_card_png).pack(side="left")
        ttk.Button(deck_export_buttons, text="Export All PNGs", command=self.export_all_cards_png).pack(side="left", padx=6)

        deck_note = ttk.Label(deck_left, text="Deck buttons on the sidebar show the first 6 cards. Extra cards stay in storage.", wraplength=430)
        deck_note.grid(row=5, column=0, columnspan=3, sticky="w", pady=(10, 0))

        ttk.Label(deck_right, text="Deck Card Storage", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, sticky="w")
        deck_storage_frame = ttk.Frame(deck_right)
        deck_storage_frame.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        deck_storage_frame.rowconfigure(0, weight=1)
        deck_storage_frame.columnconfigure(0, weight=1)
        self.deck_storage_listbox = tk.Listbox(deck_storage_frame, height=8, exportselection=False)
        self.deck_storage_listbox.grid(row=0, column=0, sticky="nsew")
        deck_storage_scroll = ttk.Scrollbar(deck_storage_frame, orient="vertical", command=self.deck_storage_listbox.yview)
        deck_storage_scroll.grid(row=0, column=1, sticky="ns")
        self.deck_storage_listbox.configure(yscrollcommand=deck_storage_scroll.set)

        deck_swap_buttons = ttk.Frame(deck_right)
        deck_swap_buttons.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(deck_swap_buttons, text="Swap Active", command=self.swap_storage_with_active).pack(side="left")
        ttk.Button(deck_swap_buttons, text="Swap Click", command=lambda: self.arm_storage_swap(True)).pack(side="left", padx=6)

        deck_silent_swap_buttons = ttk.Frame(deck_right)
        deck_silent_swap_buttons.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(deck_silent_swap_buttons, text="Silent Swap Click", command=lambda: self.arm_storage_swap(False)).pack(side="left")

        sticker_frame.columnconfigure(0, weight=0)
        sticker_frame.columnconfigure(1, weight=1)

        sticker_left = ttk.Frame(sticker_frame)
        sticker_left.grid(row=0, column=0, sticky="nw", padx=(0, 12))
        sticker_right = ttk.Frame(sticker_frame)
        sticker_right.grid(row=0, column=1, sticky="nsew")
        sticker_right.columnconfigure(0, weight=1)
        sticker_right.rowconfigure(1, weight=1)

        ttk.Label(sticker_left, text="Sticker").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        self.sticker_selector = ttk.Combobox(
            sticker_left,
            state="readonly",
            textvariable=self.selected_sticker_label_var,
            values=[],
            width=38,
        )
        self.sticker_selector.grid(row=0, column=1, columnspan=3, sticky="ew", pady=2)
        self.sticker_selector.bind("<<ComboboxSelected>>", self.on_sticker_selected)

        ttk.Label(sticker_left, text="Emoji").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(sticker_left, textvariable=self.sticker_text_var, width=12).grid(row=1, column=1, sticky="w", pady=2)

        ttk.Label(sticker_left, text="X").grid(row=1, column=2, sticky="e", padx=(12, 4), pady=2)
        ttk.Spinbox(sticker_left, from_=0, to=960, textvariable=self.sticker_x_var, width=7, command=self.apply_sticker_editor).grid(row=1, column=3, sticky="w", pady=2)

        ttk.Label(sticker_left, text="Y").grid(row=2, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Spinbox(sticker_left, from_=0, to=500, textvariable=self.sticker_y_var, width=7, command=self.apply_sticker_editor).grid(row=2, column=1, sticky="w", pady=2)

        ttk.Label(sticker_left, text="Size").grid(row=2, column=2, sticky="e", padx=(12, 4), pady=2)
        ttk.Spinbox(sticker_left, from_=8, to=96, textvariable=self.sticker_size_var, width=7, command=self.apply_sticker_editor).grid(row=2, column=3, sticky="w", pady=2)

        ttk.Label(sticker_left, text="Opacity").grid(row=3, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Spinbox(sticker_left, from_=0.1, to=1.0, increment=0.1, textvariable=self.sticker_opacity_var, width=7, command=self.apply_sticker_editor).grid(row=3, column=1, sticky="w", pady=2)

        ttk.Label(sticker_left, text="Name").grid(row=3, column=2, sticky="e", padx=(12, 4), pady=2)
        ttk.Entry(sticker_left, textvariable=self.sticker_name_var, width=21).grid(row=3, column=3, sticky="w", pady=2)

        sticker_buttons = ttk.Frame(sticker_left)
        sticker_buttons.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        ttk.Button(sticker_buttons, text="Add Emoji", command=self.add_emoji_sticker).pack(side="left")
        ttk.Button(sticker_buttons, text="Duplicate", command=self.duplicate_sticker).pack(side="left", padx=4)
        ttk.Button(sticker_buttons, text="Apply Sticker", command=self.apply_sticker_editor).pack(side="left", padx=4)
        ttk.Button(sticker_buttons, text="Delete", command=self.delete_sticker).pack(side="left", padx=4)

        sticker_visibility_buttons = ttk.Frame(sticker_left)
        sticker_visibility_buttons.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        ttk.Button(sticker_visibility_buttons, text="Show", command=self.show_sticker).pack(side="left")
        ttk.Button(sticker_visibility_buttons, text="Hide", command=self.hide_sticker).pack(side="left", padx=4)
        ttk.Button(sticker_visibility_buttons, text="Layer Up", command=self.layer_sticker_up).pack(side="left", padx=(28, 4))
        ttk.Button(sticker_visibility_buttons, text="Layer Down", command=self.layer_sticker_down).pack(side="left", padx=4)

        sticker_nudge_buttons = ttk.Frame(sticker_left)
        sticker_nudge_buttons.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        ttk.Label(sticker_nudge_buttons, text="Nudge").pack(side="left", padx=(0, 4))
        ttk.Button(sticker_nudge_buttons, text="←", width=3, command=lambda: self.nudge_sticker(-1, 0)).pack(side="left")
        ttk.Button(sticker_nudge_buttons, text="↑", width=3, command=lambda: self.nudge_sticker(0, -1)).pack(side="left")
        ttk.Button(sticker_nudge_buttons, text="↓", width=3, command=lambda: self.nudge_sticker(0, 1)).pack(side="left")
        ttk.Button(sticker_nudge_buttons, text="→", width=3, command=lambda: self.nudge_sticker(1, 0)).pack(side="left")
        ttk.Button(sticker_nudge_buttons, text="←10", width=5, command=lambda: self.nudge_sticker(-10, 0)).pack(side="left", padx=(8, 0))
        ttk.Button(sticker_nudge_buttons, text="↑10", width=5, command=lambda: self.nudge_sticker(0, -10)).pack(side="left")
        ttk.Button(sticker_nudge_buttons, text="↓10", width=5, command=lambda: self.nudge_sticker(0, 10)).pack(side="left")
        ttk.Button(sticker_nudge_buttons, text="→10", width=5, command=lambda: self.nudge_sticker(10, 0)).pack(side="left")

        sticker_snap_buttons = ttk.Frame(sticker_left)
        sticker_snap_buttons.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        ttk.Label(sticker_snap_buttons, text="Snap").pack(side="left", padx=(0, 4))
        ttk.Button(sticker_snap_buttons, text="L", width=4, command=lambda: self.snap_sticker("left")).pack(side="left")
        ttk.Button(sticker_snap_buttons, text="CX", width=4, command=lambda: self.snap_sticker("center_x")).pack(side="left")
        ttk.Button(sticker_snap_buttons, text="R", width=4, command=lambda: self.snap_sticker("right")).pack(side="left")
        ttk.Button(sticker_snap_buttons, text="T", width=4, command=lambda: self.snap_sticker("top")).pack(side="left", padx=(8, 0))
        ttk.Button(sticker_snap_buttons, text="CY", width=4, command=lambda: self.snap_sticker("center_y")).pack(side="left")
        ttk.Button(sticker_snap_buttons, text="B", width=4, command=lambda: self.snap_sticker("bottom")).pack(side="left")

        ttk.Label(sticker_right, text="Emoji Presets", font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, sticky="w")
        preset_list_frame = ttk.Frame(sticker_right)
        preset_list_frame.grid(row=1, column=0, sticky="nsew", pady=(4, 0))
        preset_list_frame.rowconfigure(0, weight=1)
        preset_list_frame.columnconfigure(0, weight=1)
        self.emoji_preset_listbox = tk.Listbox(preset_list_frame, height=9, exportselection=False)
        self.emoji_preset_listbox.grid(row=0, column=0, sticky="nsew")
        preset_scroll = ttk.Scrollbar(preset_list_frame, orient="vertical", command=self.emoji_preset_listbox.yview)
        preset_scroll.grid(row=0, column=1, sticky="ns")
        self.emoji_preset_listbox.configure(yscrollcommand=preset_scroll.set)
        self.emoji_preset_listbox.bind("<<ListboxSelect>>", self.on_emoji_preset_selected)
        self.emoji_preset_listbox.bind("<Double-Button-1>", lambda _e: self.use_selected_emoji_preset())

        preset_buttons = ttk.Frame(sticker_right)
        preset_buttons.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(preset_buttons, text="Use Selected", command=self.use_selected_emoji_preset).pack(side="left")
        ttk.Button(preset_buttons, text="Copy Selected", command=self.copy_selected_emoji_preset).pack(side="left", padx=4)
        preset_load_buttons = ttk.Frame(sticker_right)
        preset_load_buttons.grid(row=3, column=0, sticky="ew", pady=(4, 0))
        ttk.Button(preset_load_buttons, text="Load .emoji", command=self.load_custom_emoji_file).pack(side="left")

        self.load_emoji_presets()

        image_frame.columnconfigure(1, weight=1)
        ttk.Label(image_frame, text="Image Layer").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        self.image_selector = ttk.Combobox(
            image_frame,
            state="readonly",
            textvariable=self.selected_image_label_var,
            values=[],
            width=38,
        )
        self.image_selector.grid(row=0, column=1, columnspan=3, sticky="ew", pady=2)
        self.image_selector.bind("<<ComboboxSelected>>", self.on_image_layer_selected)

        ttk.Label(image_frame, text="Name").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(image_frame, textvariable=self.image_name_var, width=22).grid(row=1, column=1, sticky="w", pady=2)

        ttk.Label(image_frame, text="X").grid(row=1, column=2, sticky="e", padx=(12, 4), pady=2)
        ttk.Spinbox(image_frame, from_=0, to=960, textvariable=self.image_x_var, width=7, command=self.apply_image_editor).grid(row=1, column=3, sticky="w", pady=2)

        ttk.Label(image_frame, text="Y").grid(row=2, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Spinbox(image_frame, from_=0, to=500, textvariable=self.image_y_var, width=7, command=self.apply_image_editor).grid(row=2, column=1, sticky="w", pady=2)

        ttk.Label(image_frame, text="Scale %").grid(row=2, column=2, sticky="e", padx=(12, 4), pady=2)
        ttk.Spinbox(image_frame, from_=10, to=400, textvariable=self.image_scale_var, width=7, command=self.apply_image_editor).grid(row=2, column=3, sticky="w", pady=2)

        ttk.Label(image_frame, text="Opacity").grid(row=3, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Spinbox(image_frame, from_=0.1, to=1.0, increment=0.1, textvariable=self.image_opacity_var, width=7, command=self.apply_image_editor).grid(row=3, column=1, sticky="w", pady=2)

        ttk.Label(image_frame, text="Source").grid(row=3, column=2, sticky="e", padx=(12, 4), pady=2)
        ttk.Label(image_frame, textvariable=self.image_path_var).grid(row=3, column=3, sticky="w", pady=2)

        image_buttons = ttk.Frame(image_frame)
        image_buttons.grid(row=4, column=0, columnspan=4, sticky="ew", pady=(6, 0))
        ttk.Button(image_buttons, text="Import PNG", command=self.import_png_layer).pack(side="left")
        ttk.Button(image_buttons, text="Duplicate", command=self.duplicate_image_layer).pack(side="left", padx=4)
        ttk.Button(image_buttons, text="Apply Image", command=self.apply_image_editor).pack(side="left", padx=4)
        ttk.Button(image_buttons, text="Layer Up", command=self.layer_image_up).pack(side="left", padx=4)
        ttk.Button(image_buttons, text="Layer Down", command=self.layer_image_down).pack(side="left", padx=4)
        ttk.Button(image_buttons, text="Delete", command=self.delete_image_layer).pack(side="left", padx=4)
        ttk.Button(image_buttons, text="Show", command=self.show_image_layer).pack(side="left", padx=4)
        ttk.Button(image_buttons, text="Hide", command=self.hide_image_layer).pack(side="left", padx=4)

        image_nudge_buttons = ttk.Frame(image_frame)
        image_nudge_buttons.grid(row=5, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        ttk.Label(image_nudge_buttons, text="Nudge").pack(side="left", padx=(0, 4))
        ttk.Button(image_nudge_buttons, text="←", width=3, command=lambda: self.nudge_image_layer(-1, 0)).pack(side="left")
        ttk.Button(image_nudge_buttons, text="↑", width=3, command=lambda: self.nudge_image_layer(0, -1)).pack(side="left")
        ttk.Button(image_nudge_buttons, text="↓", width=3, command=lambda: self.nudge_image_layer(0, 1)).pack(side="left")
        ttk.Button(image_nudge_buttons, text="→", width=3, command=lambda: self.nudge_image_layer(1, 0)).pack(side="left")
        ttk.Button(image_nudge_buttons, text="←10", width=5, command=lambda: self.nudge_image_layer(-10, 0)).pack(side="left", padx=(8, 0))
        ttk.Button(image_nudge_buttons, text="↑10", width=5, command=lambda: self.nudge_image_layer(0, -10)).pack(side="left")
        ttk.Button(image_nudge_buttons, text="↓10", width=5, command=lambda: self.nudge_image_layer(0, 10)).pack(side="left")
        ttk.Button(image_nudge_buttons, text="→10", width=5, command=lambda: self.nudge_image_layer(10, 0)).pack(side="left")

        image_snap_buttons = ttk.Frame(image_frame)
        image_snap_buttons.grid(row=6, column=0, columnspan=4, sticky="ew", pady=(4, 0))
        ttk.Label(image_snap_buttons, text="Snap").pack(side="left", padx=(0, 4))
        ttk.Button(image_snap_buttons, text="L", width=4, command=lambda: self.snap_image_layer("left")).pack(side="left")
        ttk.Button(image_snap_buttons, text="CX", width=4, command=lambda: self.snap_image_layer("center_x")).pack(side="left")
        ttk.Button(image_snap_buttons, text="R", width=4, command=lambda: self.snap_image_layer("right")).pack(side="left")
        ttk.Button(image_snap_buttons, text="T", width=4, command=lambda: self.snap_image_layer("top")).pack(side="left", padx=(8, 0))
        ttk.Button(image_snap_buttons, text="CY", width=4, command=lambda: self.snap_image_layer("center_y")).pack(side="left")
        ttk.Button(image_snap_buttons, text="B", width=4, command=lambda: self.snap_image_layer("bottom")).pack(side="left")

        text_layer_frame.columnconfigure(1, weight=1)
        ttk.Label(text_layer_frame, text="Text Layer").grid(row=0, column=0, sticky="w", padx=(0, 6), pady=2)
        self.text_layer_selector = ttk.Combobox(
            text_layer_frame,
            state="readonly",
            textvariable=self.selected_text_layer_label_var,
            values=[],
            width=38,
        )
        self.text_layer_selector.grid(row=0, column=1, columnspan=5, sticky="ew", pady=2)
        self.text_layer_selector.bind("<<ComboboxSelected>>", self.on_text_layer_selected)

        ttk.Label(text_layer_frame, text="Name").grid(row=1, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Entry(text_layer_frame, textvariable=self.text_layer_name_var, width=22).grid(row=1, column=1, sticky="w", pady=2)

        ttk.Label(text_layer_frame, text="X").grid(row=1, column=2, sticky="e", padx=(12, 4), pady=2)
        ttk.Spinbox(text_layer_frame, from_=0, to=960, textvariable=self.text_layer_x_var, width=7, command=self.apply_text_layer_editor).grid(row=1, column=3, sticky="w", pady=2)

        ttk.Label(text_layer_frame, text="Y").grid(row=1, column=4, sticky="e", padx=(12, 4), pady=2)
        ttk.Spinbox(text_layer_frame, from_=0, to=500, textvariable=self.text_layer_y_var, width=7, command=self.apply_text_layer_editor).grid(row=1, column=5, sticky="w", pady=2)

        ttk.Label(text_layer_frame, text="Size").grid(row=2, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Spinbox(text_layer_frame, from_=8, to=72, textvariable=self.text_layer_size_var, width=7, command=self.apply_text_layer_editor).grid(row=2, column=1, sticky="w", pady=2)

        ttk.Label(text_layer_frame, text="Opacity").grid(row=2, column=2, sticky="e", padx=(12, 4), pady=2)
        ttk.Spinbox(text_layer_frame, from_=0.1, to=1.0, increment=0.1, textvariable=self.text_layer_opacity_var, width=7, command=self.apply_text_layer_editor).grid(row=2, column=3, sticky="w", pady=2)

        ttk.Label(text_layer_frame, text="Color").grid(row=2, column=4, sticky="e", padx=(12, 4), pady=2)
        ttk.Entry(text_layer_frame, textvariable=self.text_layer_color_var, width=10).grid(row=2, column=5, sticky="w", pady=2)

        ttk.Label(text_layer_frame, text="Wrap px").grid(row=3, column=0, sticky="w", padx=(0, 6), pady=2)
        ttk.Spinbox(text_layer_frame, from_=80, to=900, textvariable=self.text_layer_wrap_var, width=8, command=self.apply_text_layer_editor).grid(row=3, column=1, sticky="w", pady=2)

        ttk.Label(text_layer_frame, text="Text").grid(row=4, column=0, sticky="nw", padx=(0, 6), pady=2)
        self.text_layer_text = tk.Text(text_layer_frame, height=4, width=58, wrap="word")
        self.text_layer_text.grid(row=4, column=1, columnspan=5, sticky="ew", pady=2)

        text_layer_buttons = ttk.Frame(text_layer_frame)
        text_layer_buttons.grid(row=5, column=0, columnspan=6, sticky="ew", pady=(6, 0))
        ttk.Button(text_layer_buttons, text="Add Text", command=self.add_text_layer).pack(side="left")
        ttk.Button(text_layer_buttons, text="Duplicate", command=self.duplicate_text_layer).pack(side="left", padx=4)
        ttk.Button(text_layer_buttons, text="Apply Text", command=self.apply_text_layer_editor).pack(side="left", padx=4)
        ttk.Button(text_layer_buttons, text="Layer Up", command=self.layer_text_up).pack(side="left", padx=4)
        ttk.Button(text_layer_buttons, text="Layer Down", command=self.layer_text_down).pack(side="left", padx=4)
        ttk.Button(text_layer_buttons, text="Delete", command=self.delete_text_layer).pack(side="left", padx=4)
        ttk.Button(text_layer_buttons, text="Show", command=self.show_text_layer).pack(side="left", padx=4)
        ttk.Button(text_layer_buttons, text="Hide", command=self.hide_text_layer).pack(side="left", padx=4)

        text_nudge_buttons = ttk.Frame(text_layer_frame)
        text_nudge_buttons.grid(row=6, column=0, columnspan=6, sticky="ew", pady=(4, 0))
        ttk.Label(text_nudge_buttons, text="Nudge").pack(side="left", padx=(0, 4))
        ttk.Button(text_nudge_buttons, text="←", width=3, command=lambda: self.nudge_text_layer(-1, 0)).pack(side="left")
        ttk.Button(text_nudge_buttons, text="↑", width=3, command=lambda: self.nudge_text_layer(0, -1)).pack(side="left")
        ttk.Button(text_nudge_buttons, text="↓", width=3, command=lambda: self.nudge_text_layer(0, 1)).pack(side="left")
        ttk.Button(text_nudge_buttons, text="→", width=3, command=lambda: self.nudge_text_layer(1, 0)).pack(side="left")
        ttk.Button(text_nudge_buttons, text="←10", width=5, command=lambda: self.nudge_text_layer(-10, 0)).pack(side="left", padx=(8, 0))
        ttk.Button(text_nudge_buttons, text="↑10", width=5, command=lambda: self.nudge_text_layer(0, -10)).pack(side="left")
        ttk.Button(text_nudge_buttons, text="↓10", width=5, command=lambda: self.nudge_text_layer(0, 10)).pack(side="left")
        ttk.Button(text_nudge_buttons, text="→10", width=5, command=lambda: self.nudge_text_layer(10, 0)).pack(side="left")

        text_snap_buttons = ttk.Frame(text_layer_frame)
        text_snap_buttons.grid(row=7, column=0, columnspan=6, sticky="ew", pady=(4, 0))
        ttk.Label(text_snap_buttons, text="Snap").pack(side="left", padx=(0, 4))
        ttk.Button(text_snap_buttons, text="L", width=4, command=lambda: self.snap_text_layer("left")).pack(side="left")
        ttk.Button(text_snap_buttons, text="CX", width=4, command=lambda: self.snap_text_layer("center_x")).pack(side="left")
        ttk.Button(text_snap_buttons, text="R", width=4, command=lambda: self.snap_text_layer("right")).pack(side="left")
        ttk.Button(text_snap_buttons, text="T", width=4, command=lambda: self.snap_text_layer("top")).pack(side="left", padx=(8, 0))
        ttk.Button(text_snap_buttons, text="CY", width=4, command=lambda: self.snap_text_layer("center_y")).pack(side="left")
        ttk.Button(text_snap_buttons, text="B", width=4, command=lambda: self.snap_text_layer("bottom")).pack(side="left")

        output_tools_frame.columnconfigure(0, weight=1)
        ttk.Label(output_tools_frame, text="OBS Output Tools", font=("TkDefaultFont", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Label(output_tools_frame, text="Stable OBS capture title: 3DCP Perspective Console - Output").grid(row=1, column=0, sticky="w", pady=(0, 8))

        output_checks = ttk.Frame(output_tools_frame)
        output_checks.grid(row=2, column=0, sticky="w", pady=(0, 8))
        ttk.Checkbutton(output_checks, text="Always on top", variable=self.output_topmost_var, command=self.apply_output_window_style).pack(side="left")
        ttk.Checkbutton(output_checks, text="Borderless OBS mode", variable=self.output_borderless_var, command=self.apply_output_window_style).pack(side="left", padx=14)

        output_buttons_row1 = ttk.Frame(output_tools_frame)
        output_buttons_row1.grid(row=3, column=0, sticky="w", pady=(4, 0))
        ttk.Button(output_buttons_row1, text="Apply OBS Mode", command=self.enable_obs_output_mode).pack(side="left")
        ttk.Button(output_buttons_row1, text="Normal Output", command=self.disable_obs_output_mode).pack(side="left", padx=6)
        ttk.Button(output_buttons_row1, text="Bring Output Front", command=self.bring_output_front).pack(side="left", padx=6)

        output_buttons_row2 = ttk.Frame(output_tools_frame)
        output_buttons_row2.grid(row=4, column=0, sticky="w", pady=(6, 0))
        ttk.Button(output_buttons_row2, text="Rescue Output Window", command=self.rescue_output_window).pack(side="left")
        ttk.Button(output_buttons_row2, text="Reset Output Window", command=self.reset_output_window_position).pack(side="left", padx=6)
        ttk.Button(output_buttons_row2, text="Show Output", command=self.show_output).pack(side="left", padx=6)
        ttk.Button(output_buttons_row2, text="Hide Output", command=self.hide_output).pack(side="left", padx=6)
        ttk.Button(output_buttons_row2, text="Save Output Settings", command=self.save_output_settings).pack(side="left", padx=6)

        output_notes = tk.Text(output_tools_frame, height=8, width=78, wrap="word")
        output_notes.grid(row=5, column=0, sticky="ew", pady=(10, 0))
        output_notes.insert("1.0",
            "OBS Output Notes\n"
            "- The output window title is now stable between app versions.\n"
            "- Borderless OBS mode removes the window frame for cleaner capture.\n"
            "- Always on top is useful while arranging OBS/window capture.\n"
            "- Normal Output restores the frame so you can move the window normally.\n"
            "- Rescue Output Window forces normal framed mode at 960x500+80+80.\n"
            "- Reset Output Window places the OBS output at 960x500+80+80."
        )
        output_notes.configure(state="disabled")

        hotkeys_frame.columnconfigure(0, weight=1)
        ttk.Label(hotkeys_frame, text="Controller Hotkeys", font=("TkDefaultFont", 11, "bold")).grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Checkbutton(hotkeys_frame, text="Enable controller hotkeys", variable=self.hotkeys_enabled_var).grid(row=1, column=0, sticky="w", pady=(0, 8))

        hotkey_text = (
            "Deck/Card\n"
            "  Ctrl+1 ... Ctrl+6    Select sidebar deck card 1-6\n"
            "  Ctrl+B               Blank / Hide\n"
            "  Ctrl+D               Duplicate active card\n"
            "  Ctrl+Shift+D         Delete active card\n"
            "\nOutput / Stream\n"
            "  Ctrl+O               Show output\n"
            "  Ctrl+Shift+O         Hide output\n"
            "  Ctrl+R               Scan Once / reset scan instantly\n"
            "  Ctrl+L               Toggle Scan Loop\n"
            "\nSave / Load / Export\n"
            "  Ctrl+S               Save + Apply\n"
            "  Ctrl+Shift+S         Save As .buttstore\n"
            "  Ctrl+Shift+L         Load .buttstore\n"
            "  Ctrl+E               Export Card PNG\n"
            "  Ctrl+Shift+E         Export All PNGs\n"
            "  Ctrl+Shift+R         Reset Output Window\n"
            "  Ctrl+Alt+R           Rescue Output Window\n"
            "  Ctrl+Alt+O           Toggle OBS output mode\n"
            "\nNotes\n"
            "  Hotkeys work while the controller window has focus.\n"
            "  Text boxes keep normal typing behavior; hotkeys are ignored while typing in text fields."
        )
        hotkey_box = tk.Text(hotkeys_frame, height=20, width=76, wrap="word")
        hotkey_box.grid(row=2, column=0, sticky="nsew")
        hotkey_box.insert("1.0", hotkey_text)
        hotkey_box.configure(state="disabled")

        controls = ttk.Frame(right)
        controls.grid(row=14, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Button(controls, text="Apply to Output", command=self.apply_editor_to_card).pack(side="left")
        ttk.Button(controls, text="Save + Apply", command=self.save_now).pack(side="left", padx=6)
        ttk.Label(controls, textvariable=self.status_var).pack(side="left", padx=10)
        tk.Button(controls, text="Wipe 2 Default", command=self.to_default_wipe, bg="#650000", fg="white", activebackground="#8b0000", activeforeground="white").pack(side="right", padx=(8, 0))
        ttk.Button(controls, text="Load .buttstore", command=self.load_buttstore).pack(side="right", padx=4)
        ttk.Button(controls, text="Save As .buttstore", command=self.save_as).pack(side="right", padx=4)

        for widget in [self.claim_text, self.evidence_text, self.open_question_text]:
            widget.bind("<FocusOut>", self.on_editor_focus_out)
            widget.bind("<<Modified>>", self.on_text_modified)

        self.text_layer_text.bind("<FocusOut>", self.on_text_layer_focus_out)
        self.text_layer_text.bind("<<Modified>>", self.on_text_layer_modified)

        for var in [self.source_type_var, self.confidence_var, self.verdict_var, self.source_link_var, self.scanner_color_var]:
            var.trace_add("write", lambda *_: self.schedule_autosave_stage_only())

        for var in [self.sticker_text_var, self.sticker_name_var, self.sticker_x_var, self.sticker_y_var, self.sticker_size_var, self.sticker_opacity_var]:
            var.trace_add("write", lambda *_: self.schedule_sticker_stage_only())

        for var in [self.image_name_var, self.image_x_var, self.image_y_var, self.image_scale_var, self.image_opacity_var]:
            var.trace_add("write", lambda *_: self.schedule_image_stage_only())

        for var in [self.text_layer_name_var, self.text_layer_x_var, self.text_layer_y_var, self.text_layer_size_var, self.text_layer_opacity_var, self.text_layer_color_var, self.text_layer_wrap_var]:
            var.trace_add("write", lambda *_: self.schedule_text_layer_stage_only())

    def refresh_deck_buttons(self) -> None:
        if self.deck_button_frame is None:
            return
        for child in self.deck_button_frame.winfo_children():
            child.destroy()
        self.card_buttons = {}
        active_id = self.store.data["header"].get("active_card_id", "")
        for card in self.store.cards()[:self.max_deck_buttons]:
            cid = card.get("id", "")
            label = card.get("label", cid or "Card")
            text = ("▶ " if cid == active_id else "  ") + label
            btn = ttk.Button(self.deck_button_frame, text=text, command=lambda selected=cid: self.on_deck_button_clicked(selected), width=24)
            btn.pack(fill="x", pady=3)
            self.card_buttons[cid] = btn
        self.refresh_deck_storage()

    def refresh_deck_storage(self) -> None:
        if self.deck_storage_listbox is None:
            return
        self.deck_storage_listbox.delete(0, "end")
        self.deck_storage_ids = []
        for idx, card in enumerate(self.store.cards()[self.max_deck_buttons:], start=self.max_deck_buttons):
            cid = card.get("id", "")
            label = card.get("label", cid or "Card")
            active_mark = "▶ " if cid == self.store.data["header"].get("active_card_id", "") else "  "
            self.deck_storage_ids.append(cid)
            self.deck_storage_listbox.insert("end", f"{active_mark}{idx + 1}. {label}")

    def selected_storage_card_id(self) -> str | None:
        if self.deck_storage_listbox is None:
            return None
        selection = self.deck_storage_listbox.curselection()
        if not selection:
            return None
        idx = selection[0]
        if idx < 0 or idx >= len(self.deck_storage_ids):
            return None
        return self.deck_storage_ids[idx]

    def card_index_by_id(self, card_id: str) -> int | None:
        for idx, card in enumerate(self.store.cards()):
            if card.get("id") == card_id:
                return idx
        return None

    def swap_card_positions(self, first_id: str, second_id: str) -> bool:
        first_idx = self.card_index_by_id(first_id)
        second_idx = self.card_index_by_id(second_id)
        if first_idx is None or second_idx is None or first_idx == second_idx:
            return False
        cards = self.store.cards()
        cards[first_idx], cards[second_idx] = cards[second_idx], cards[first_idx]
        return True

    def swap_storage_with_active(self) -> None:
        storage_id = self.selected_storage_card_id()
        if not storage_id:
            self.status_var.set("Select a storage card first")
            return
        active_id = self.store.data["header"].get("active_card_id", "")
        if self.swap_card_positions(storage_id, active_id):
            self.store.set_active_card(storage_id)
            self.refresh_after_deck_change("deck-storage-swapped-with-active")
            self.status_var.set("Swapped storage card with active card")

    def arm_storage_swap(self, activate_after_swap: bool) -> None:
        storage_id = self.selected_storage_card_id()
        if not storage_id:
            self.status_var.set("Select a storage card first")
            return
        self.pending_deck_swap = {"storage_id": storage_id, "activate": bool(activate_after_swap)}
        mode = "Swap Click" if activate_after_swap else "Silent Swap Click"
        self.status_var.set(f"{mode}: click a sidebar deck button")

    def on_deck_button_clicked(self, card_id: str) -> None:
        if self.pending_deck_swap:
            storage_id = self.pending_deck_swap.get("storage_id", "")
            activate = bool(self.pending_deck_swap.get("activate", True))
            previous_active = self.store.data["header"].get("active_card_id", "")
            self.pending_deck_swap = None
            if storage_id and self.swap_card_positions(storage_id, card_id):
                if activate:
                    self.store.set_active_card(storage_id)
                    self.load_active_card_into_editor()
                    self.redraw_output()
                else:
                    self.store.set_active_card(previous_active)
                self.refresh_deck_buttons()
                self.store.mark_dirty("deck-storage-swap-click")
                self.schedule_autosave()
                self.status_var.set("Deck storage swap complete")
                return
        self.select_card(card_id)

    def unique_card_id(self, prefix: str) -> str:
        existing = {card.get("id") for card in self.store.cards()}
        candidate = prefix
        if candidate not in existing:
            return candidate
        n = 2
        while True:
            candidate = f"{prefix}-{n}"
            if candidate not in existing:
                return candidate
            n += 1

    def unique_card_label(self, base: str) -> str:
        existing = {str(card.get("label", "")) for card in self.store.cards()}
        if base not in existing:
            return base
        n = 2
        while True:
            candidate = f"{base} {n}"
            if candidate not in existing:
                return candidate
            n += 1

    def refresh_after_deck_change(self, event: str) -> None:
        self.store.mark_dirty(event)
        self.refresh_deck_buttons()
        self.load_active_card_into_editor()
        self.redraw_output()
        self.schedule_autosave()

    def rename_active_card(self) -> None:
        card = self.store.active_card()
        label = (self.card_label_var.get() or "Card").strip()[:32] or "Card"
        card["label"] = label
        self.refresh_after_deck_change("card-renamed")
        self.status_var.set(f"Renamed card: {label}")

    def card_to_deckbutt_payload(self, card: dict) -> dict:
        return {
            "deckbutt_format": "3DCP-DECKBUTT",
            "version": APP_VERSION,
            "created_at": utc_now(),
            "source_app": APP_NAME,
            "card": copy.deepcopy(card),
        }

    def normalize_loaded_deckbutt_card(self, card: dict) -> dict:
        card = copy.deepcopy(card)
        base_label = str(card.get("label", "Loaded Card"))[:32] or "Loaded Card"
        card["label"] = self.unique_card_label(base_label)
        base_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(card.get("id", "loaded-card")).lower()).strip("-") or "loaded-card"
        card["id"] = self.unique_card_id(base_id)
        card.setdefault("fields", {})
        card.setdefault("layers", [])
        self.reassign_layer_ids_for_card_copy(card)
        return card

    def save_card_deckbutt(self) -> None:
        DECKBUTT_DIR.mkdir(parents=True, exist_ok=True)
        card = self.store.active_card()
        safe_label = re.sub(r"[^A-Za-z0-9._-]+", "_", str(card.get("label", "card"))).strip("_") or "card"
        path = filedialog.asksaveasfilename(
            title="Save deck card as .deckbutt",
            defaultextension=".deckbutt",
            filetypes=[("3DCP Deck Button", "*.deckbutt"), ("JSON", "*.json"), ("All files", "*.*")],
            initialdir=str(DECKBUTT_DIR),
            initialfile=f"{safe_label}.deckbutt",
        )
        if not path:
            return
        self.apply_sticker_editor()
        self.apply_image_editor()
        self.apply_text_layer_editor()
        self.apply_editor_to_card_without_reschedule()
        payload = self.card_to_deckbutt_payload(self.store.active_card())
        safe_write_json(Path(path), payload)
        self.status_var.set(f"Saved deck card: {Path(path).name}")

    def load_card_deckbutt(self) -> None:
        DECKBUTT_DIR.mkdir(parents=True, exist_ok=True)
        path = filedialog.askopenfilename(
            title="Load .deckbutt card",
            filetypes=[("3DCP Deck Button", "*.deckbutt"), ("JSON", "*.json"), ("All files", "*.*")],
            initialdir=str(DECKBUTT_DIR),
        )
        if not path:
            return
        try:
            payload = safe_read_json(Path(path))
            if payload.get("deckbutt_format") != "3DCP-DECKBUTT":
                raise ValueError("This is not a 3DCP .deckbutt file.")
            card = payload.get("card")
            if not isinstance(card, dict):
                raise ValueError("The .deckbutt file does not contain a valid card.")
            card = self.normalize_loaded_deckbutt_card(card)
        except Exception as exc:
            messagebox.showerror("Could not load .deckbutt", str(exc))
            return

        self.store.cards().append(card)
        if self.card_index_by_id(card["id"]) is not None and self.card_index_by_id(card["id"]) < self.max_deck_buttons:
            self.store.set_active_card(card["id"])
        self.refresh_after_deck_change("deckbutt-card-loaded")
        self.status_var.set(f"Loaded deck card: {card.get('label', 'Card')}")

    def add_source_card(self) -> None:
        card = new_card("source_analyzer", self.unique_card_label("Source Analyzer"))
        card["id"] = self.unique_card_id("source-analyzer")
        # Keep built-in layer ids unique enough for future selection history.
        for layer in card.get("layers", []):
            if layer.get("type") == "emoji":
                layer["id"] = f"emoji-{uuid.uuid4().hex[:8]}"
        self.store.cards().append(card)
        if self.card_index_by_id(card["id"]) is not None and self.card_index_by_id(card["id"]) < self.max_deck_buttons:
            self.store.set_active_card(card["id"])
            self.status_var.set("Added Source Analyzer card")
        else:
            self.status_var.set("Added Source Analyzer card to storage")
        self.refresh_after_deck_change("source-card-added")

    def add_blank_card(self) -> None:
        card = new_card("blank", self.unique_card_label("Blank / Hide"))
        card["id"] = self.unique_card_id("blank-hide")
        self.store.cards().append(card)
        if self.card_index_by_id(card["id"]) is not None and self.card_index_by_id(card["id"]) < self.max_deck_buttons:
            self.store.set_active_card(card["id"])
            self.status_var.set("Added Blank / Hide card")
        else:
            self.status_var.set("Added Blank / Hide card to storage")
        self.refresh_after_deck_change("blank-card-added")

    def reassign_layer_ids_for_card_copy(self, card: dict) -> None:
        for layer in card.get("layers", []):
            layer_type = layer.get("type", "layer")
            if layer_type == "emoji":
                layer["id"] = f"emoji-{uuid.uuid4().hex[:8]}"
            elif layer_type == "image":
                layer["id"] = f"image-{uuid.uuid4().hex[:8]}"
            elif layer_type == "text":
                layer["id"] = f"text-{uuid.uuid4().hex[:8]}"
            else:
                layer["id"] = f"layer-{uuid.uuid4().hex[:8]}"

    def duplicate_active_card(self) -> None:
        source = self.store.active_card()
        duplicate = copy.deepcopy(source)
        base_label = str(source.get("label", "Card"))
        duplicate["id"] = self.unique_card_id(str(source.get("id", "card")) + "-copy")
        duplicate["label"] = self.unique_card_label(("Copy of " + base_label)[:32])
        self.reassign_layer_ids_for_card_copy(duplicate)
        self.store.cards().append(duplicate)
        if self.card_index_by_id(duplicate["id"]) is not None and self.card_index_by_id(duplicate["id"]) < self.max_deck_buttons:
            self.store.set_active_card(duplicate["id"])
            self.status_var.set(f"Duplicated card: {duplicate['label']}")
        else:
            self.status_var.set(f"Duplicated card to storage: {duplicate['label']}")
        self.refresh_after_deck_change("card-duplicated")

    def delete_active_card(self) -> None:
        cards = self.store.cards()
        if len(cards) <= 1:
            self.status_var.set("Cannot delete the only card")
            return
        active_id = self.store.data["header"].get("active_card_id")
        remaining = [card for card in cards if card.get("id") != active_id]
        if len(remaining) == len(cards):
            self.status_var.set("No active card deleted")
            return
        self.store.data["body"]["cards"] = remaining
        self.store.data["header"]["active_card_id"] = remaining[0].get("id")
        self.refresh_after_deck_change("card-deleted")
        self.status_var.set("Deleted active card")

    def select_card(self, card_id: str) -> None:
        self.apply_editor_to_card()
        self.store.set_active_card(card_id)
        self.load_active_card_into_editor()
        self.redraw_output()
        self.schedule_autosave()

    def load_active_card_into_editor(self) -> None:
        card = self.store.active_card()
        self.card_label_var.set(card.get("label", card.get("id", "Card")))
        fields = card.get("fields", {})
        self.source_type_var.set(fields.get("sourceType", "Unknown"))
        self.confidence_var.set(fields.get("confidence", "Still Checking"))
        self.verdict_var.set(fields.get("verdict", "Still Checking"))
        self.source_link_var.set(fields.get("sourceLink", ""))
        for text_widget, value in [
            (self.claim_text, fields.get("claim", "")),
            (self.evidence_text, fields.get("evidence", "")),
            (self.open_question_text, fields.get("openQuestion", "")),
        ]:
            text_widget.delete("1.0", "end")
            text_widget.insert("1.0", value)
            text_widget.edit_modified(False)
        active_id = card.get("id")
        for cid, btn in self.card_buttons.items():
            label = self.store.get_card(cid).get("label", cid)
            btn.configure(text=("▶ " if cid == active_id else "  ") + label)

        self.refresh_sticker_selector()
        self.refresh_image_selector()
        self.refresh_text_layer_selector()

    def emoji_layers(self) -> list[dict]:
        card = self.store.active_card()
        return [layer for layer in card.get("layers", []) if layer.get("type") == "emoji"]

    def clean_sticker_name(self, value: str, fallback: str = "Emoji") -> str:
        cleaned = (value or "").strip()[:19]
        return cleaned or fallback[:19]

    def next_sticker_auto_name(self) -> str:
        existing = {self.clean_sticker_name(layer.get("name", ""), "") for layer in self.emoji_layers()}
        n = 1
        while True:
            candidate = f"Emoji {n}"
            if candidate not in existing:
                return candidate
            n += 1

    def selected_sticker(self) -> dict | None:
        selected_id = self.selected_sticker_id_var.get()
        for layer in self.emoji_layers():
            if layer.get("id") == selected_id:
                return layer
        return None

    def sticker_display_label(self, layer: dict) -> str:
        name = self.clean_sticker_name(layer.get("name", ""), layer.get("id", "Emoji"))
        emoji = layer.get("text", "🔍")
        hidden = "" if layer.get("visible", True) else "  [hidden]"
        return f"{name}  {emoji}{hidden}"

    def refresh_sticker_selector(self) -> None:
        if self.sticker_selector is None:
            return

        layers = self.emoji_layers()
        label_to_id = {}
        values = []
        for layer in layers:
            label = self.sticker_display_label(layer)
            base = label
            counter = 2
            while label in label_to_id:
                label = f"{base} ({counter})"
                counter += 1
            label_to_id[label] = layer.get("id", "")
            values.append(label)
        self.sticker_label_to_id = label_to_id
        self.sticker_selector.configure(values=values)

        current_id = self.selected_sticker_id_var.get()
        current_label = ""
        for label, layer_id in label_to_id.items():
            if layer_id == current_id:
                current_label = label
                break
        if not current_label and values:
            current_label = values[0]
            self.selected_sticker_id_var.set(label_to_id[current_label])
        self.selected_sticker_label_var.set(current_label)
        self.load_selected_sticker_into_controls()

    def load_selected_sticker_into_controls(self) -> None:
        layer = self.selected_sticker()
        if not layer:
            self.sticker_name_var.set(self.next_sticker_auto_name())
            return
        self.sticker_text_var.set(layer.get("text", "🔍"))
        self.sticker_name_var.set(self.clean_sticker_name(layer.get("name", ""), "Emoji"))
        self.sticker_x_var.set(int(layer.get("x", 820)))
        self.sticker_y_var.set(int(layer.get("y", 340)))
        self.sticker_size_var.set(int(layer.get("size", 28)))
        self.sticker_opacity_var.set(float(layer.get("opacity", 1.0)))

    def on_sticker_selected(self, _event=None) -> None:
        selected_label = self.selected_sticker_label_var.get()
        selected_id = self.sticker_label_to_id.get(selected_label, "")
        self.selected_sticker_id_var.set(selected_id)
        self.load_selected_sticker_into_controls()

    def schedule_sticker_stage_only(self) -> None:
        if self.selected_sticker_id_var.get():
            self.store.data["stage"]["save_body_pending"] = True
            self.store.mark_dirty("sticker-stage-updated")
            self.schedule_autosave()

    def load_emoji_presets(self, path: Path | None = None) -> None:
        if path is None:
            user_current = USER_DATA_DIR / "current.emoji"
            path = user_current if user_current.exists() else DEFAULT_EMOJI_PRESET_PATH
        items = []
        try:
            if path.exists():
                items = load_emoji_presets_from_file(path)
        except Exception:
            items = []
        if not items:
            items = list(FALLBACK_EMOJI_PRESETS)
        self.emoji_preset_items = items
        self.refresh_emoji_preset_listbox()

    def refresh_emoji_preset_listbox(self) -> None:
        if self.emoji_preset_listbox is None:
            return
        self.emoji_preset_listbox.delete(0, "end")
        for item in self.emoji_preset_items:
            label = f"{item.get('emoji', '')}  {item.get('name', 'Emoji')}  [{item.get('category', 'General')}]"
            self.emoji_preset_listbox.insert("end", label)

    def on_emoji_preset_selected(self, _event=None) -> None:
        selection = self.emoji_preset_listbox.curselection() if self.emoji_preset_listbox else ()
        if not selection:
            return
        item = self.emoji_preset_items[selection[0]]
        self.status_var.set(f"Preset selected: {item.get('name', 'Emoji')}")

    def selected_emoji_preset(self) -> dict | None:
        if self.emoji_preset_listbox is None:
            return None
        selection = self.emoji_preset_listbox.curselection()
        if not selection:
            return None
        idx = selection[0]
        if idx < 0 or idx >= len(self.emoji_preset_items):
            return None
        return self.emoji_preset_items[idx]

    def use_selected_emoji_preset(self) -> None:
        item = self.selected_emoji_preset()
        if not item:
            return
        self.sticker_text_var.set(item.get("emoji", "🧪"))
        if not self.selected_sticker_id_var.get():
            suggested_name = self.clean_sticker_name(item.get("name", "Emoji"), self.next_sticker_auto_name())
            self.sticker_name_var.set(suggested_name)
        self.status_var.set(f"Preset loaded: {item.get('name', 'Emoji')}")
        if self.selected_sticker_id_var.get():
            self.apply_sticker_editor()

    def copy_selected_emoji_preset(self) -> None:
        item = self.selected_emoji_preset()
        if not item:
            return
        emoji = item.get("emoji", "")
        self.root.clipboard_clear()
        self.root.clipboard_append(emoji)
        self.status_var.set(f"Copied emoji: {item.get('name', 'Emoji')}")

    def load_custom_emoji_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Load .emoji preset file",
            filetypes=[("Emoji preset", "*.emoji"), ("Text files", "*.txt"), ("All files", "*.*")],
            initialdir=str(EMOJI_PRESET_DIR),
        )
        if not path:
            return
        try:
            self.load_emoji_presets(Path(path))
            self.status_var.set(f"Loaded emoji preset file: {Path(path).name}")
        except Exception as exc:
            messagebox.showerror("Could not load .emoji file", str(exc))

    def add_emoji_sticker(self) -> None:
        card = self.store.active_card()
        if card.get("type") == "blank":
            return

        layers = card.setdefault("layers", [])
        existing_z = [int(layer.get("z", 0)) for layer in layers]
        z = (max(existing_z) + 1) if existing_z else 1
        layer_id = f"emoji-{uuid.uuid4().hex[:8]}"

        try:
            x = int(self.sticker_x_var.get())
            y = int(self.sticker_y_var.get())
            size = int(self.sticker_size_var.get())
            opacity = float(self.sticker_opacity_var.get())
        except (tk.TclError, ValueError):
            x, y, size, opacity = 820, 340, 28, 1.0

        fallback_name = self.next_sticker_auto_name()
        layer = {
            "id": layer_id,
            "type": "emoji",
            "name": self.clean_sticker_name(self.sticker_name_var.get(), fallback_name),
            "text": self.sticker_text_var.get().strip() or "🧪",
            "x": max(0, min(OUTPUT_WIDTH, x)),
            "y": max(0, min(OUTPUT_HEIGHT, y)),
            "size": max(8, min(96, size)),
            "opacity": max(0.1, min(1.0, opacity)),
            "z": z,
            "visible": True,
        }
        layers.append(layer)
        self.selected_sticker_id_var.set(layer_id)
        self.store.mark_dirty("emoji-sticker-added")
        self.refresh_sticker_selector()
        self.redraw_output()
        self.schedule_autosave()

    def apply_sticker_editor(self) -> None:
        layer = self.selected_sticker()
        if not layer:
            return

        try:
            x = max(0, min(OUTPUT_WIDTH, int(self.sticker_x_var.get())))
            y = max(0, min(OUTPUT_HEIGHT, int(self.sticker_y_var.get())))
            size = max(8, min(96, int(self.sticker_size_var.get())))
            opacity = max(0.1, min(1.0, float(self.sticker_opacity_var.get())))
        except (tk.TclError, ValueError):
            return

        layer["name"] = self.clean_sticker_name(self.sticker_name_var.get(), self.next_sticker_auto_name())
        layer["text"] = self.sticker_text_var.get().strip() or "🧪"
        layer["x"] = x
        layer["y"] = y
        layer["size"] = size
        layer["opacity"] = opacity
        self.store.mark_dirty("emoji-sticker-updated")
        self.refresh_sticker_selector()
        self.redraw_output()
        self.schedule_autosave()

    def layer_sticker_up(self) -> None:
        layer = self.selected_sticker()
        if not layer:
            return
        max_z = max([int(item.get("z", 0)) for item in self.store.active_card().get("layers", [])] or [0])
        layer["z"] = min(max_z + 1, int(layer.get("z", 0)) + 1)
        self.store.mark_dirty("emoji-sticker-layer-up")
        self.refresh_sticker_selector()
        self.redraw_output()
        self.schedule_autosave()

    def layer_sticker_down(self) -> None:
        layer = self.selected_sticker()
        if not layer:
            return
        layer["z"] = max(0, int(layer.get("z", 0)) - 1)
        self.store.mark_dirty("emoji-sticker-layer-down")
        self.refresh_sticker_selector()
        self.redraw_output()
        self.schedule_autosave()

    def delete_sticker(self) -> None:
        card = self.store.active_card()
        selected_id = self.selected_sticker_id_var.get()
        if not selected_id:
            return

        layers = card.get("layers", [])
        card["layers"] = [layer for layer in layers if layer.get("id") != selected_id]
        self.selected_sticker_id_var.set("")
        self.selected_sticker_label_var.set("")
        self.store.mark_dirty("emoji-sticker-deleted")
        self.refresh_sticker_selector()
        self.redraw_output()
        self.schedule_autosave()

    def image_layers(self) -> list[dict]:
        card = self.store.active_card()
        return [layer for layer in card.get("layers", []) if layer.get("type") == "image"]

    def clean_image_name(self, value: str, fallback: str = "Image") -> str:
        cleaned = (value or "").strip()[:19]
        return cleaned or fallback[:19]

    def next_image_auto_name(self) -> str:
        existing = {self.clean_image_name(layer.get("name", ""), "") for layer in self.image_layers()}
        n = 1
        while True:
            candidate = f"Image {n}"
            if candidate not in existing:
                return candidate
            n += 1

    def selected_image_layer(self) -> dict | None:
        selected_id = self.selected_image_id_var.get()
        for layer in self.image_layers():
            if layer.get("id") == selected_id:
                return layer
        return None

    def image_display_label(self, layer: dict) -> str:
        name = self.clean_image_name(layer.get("name", ""), layer.get("id", "Image"))
        hidden = "" if layer.get("visible", True) else "  [hidden]"
        return f"{name}  🖼️{hidden}"

    def refresh_image_selector(self) -> None:
        if self.image_selector is None:
            return
        layers = self.image_layers()
        label_to_id = {}
        values = []
        for layer in layers:
            label = self.image_display_label(layer)
            base = label
            counter = 2
            while label in label_to_id:
                label = f"{base} ({counter})"
                counter += 1
            label_to_id[label] = layer.get("id", "")
            values.append(label)
        self.image_label_to_id = label_to_id
        self.image_selector.configure(values=values)

        current_id = self.selected_image_id_var.get()
        current_label = ""
        for label, layer_id in label_to_id.items():
            if layer_id == current_id:
                current_label = label
                break
        if not current_label and values:
            current_label = values[0]
            self.selected_image_id_var.set(label_to_id[current_label])
        self.selected_image_label_var.set(current_label)
        self.load_selected_image_into_controls()

    def load_selected_image_into_controls(self) -> None:
        layer = self.selected_image_layer()
        if not layer:
            self.image_name_var.set(self.next_image_auto_name())
            self.image_path_var.set("")
            return
        self.image_name_var.set(self.clean_image_name(layer.get("name", ""), "Image"))
        self.image_x_var.set(int(layer.get("x", 760)))
        self.image_y_var.set(int(layer.get("y", 245)))
        self.image_scale_var.set(int(layer.get("scale", 100)))
        self.image_opacity_var.set(float(layer.get("opacity", 1.0)))
        path = layer.get("source_path", "")
        self.image_path_var.set(Path(path).name if path else "")

    def on_image_layer_selected(self, _event=None) -> None:
        selected_label = self.selected_image_label_var.get()
        selected_id = self.image_label_to_id.get(selected_label, "")
        self.selected_image_id_var.set(selected_id)
        self.load_selected_image_into_controls()

    def schedule_image_stage_only(self) -> None:
        if self.selected_image_id_var.get():
            self.store.data["stage"]["save_body_pending"] = True
            self.store.mark_dirty("image-stage-updated")
            self.schedule_autosave()

    def import_png_layer(self) -> None:
        IMPORTED_PNG_DIR.mkdir(parents=True, exist_ok=True)
        path = filedialog.askopenfilename(
            title="Import PNG layer",
            filetypes=[("PNG image", "*.png"), ("Image files", "*.png;*.jpg;*.jpeg;*.webp"), ("All files", "*.*")],
            initialdir=str(IMPORTED_PNG_DIR if IMPORTED_PNG_DIR.exists() else USER_DATA_DIR),
        )
        if not path:
            return

        src = Path(path)
        dest = IMPORTED_PNG_DIR / src.name
        if dest.exists():
            stem = src.stem
            suffix = src.suffix
            n = 1
            while True:
                candidate = IMPORTED_PNG_DIR / f"{stem}_{n}{suffix}"
                if not candidate.exists():
                    dest = candidate
                    break
                n += 1
        shutil.copy2(src, dest)

        card = self.store.active_card()
        if card.get("type") == "blank":
            return
        layers = card.setdefault("layers", [])
        existing_z = [int(layer.get("z", 0)) for layer in layers]
        z = (max(existing_z) + 1) if existing_z else 1
        layer_id = f"image-{uuid.uuid4().hex[:8]}"
        fallback_name = self.next_image_auto_name()
        name_guess = self.clean_image_name(dest.stem.replace('_', ' '), fallback_name)
        layer = {
            "id": layer_id,
            "type": "image",
            "name": name_guess,
            "source_path": str(dest),
            "x": max(0, min(OUTPUT_WIDTH, int(self.image_x_var.get()))),
            "y": max(0, min(OUTPUT_HEIGHT, int(self.image_y_var.get()))),
            "scale": max(10, min(400, int(self.image_scale_var.get()))),
            "opacity": max(0.1, min(1.0, float(self.image_opacity_var.get()))),
            "z": z,
            "visible": True,
        }
        layers.append(layer)
        self.selected_image_id_var.set(layer_id)
        self.image_path_var.set(dest.name)
        self.store.mark_dirty("png-image-imported")
        self.refresh_image_selector()
        self.redraw_output()
        self.schedule_autosave()

    def apply_image_editor(self) -> None:
        layer = self.selected_image_layer()
        if not layer:
            return
        try:
            x = max(0, min(OUTPUT_WIDTH, int(self.image_x_var.get())))
            y = max(0, min(OUTPUT_HEIGHT, int(self.image_y_var.get())))
            scale = max(10, min(400, int(self.image_scale_var.get())))
            opacity = max(0.1, min(1.0, float(self.image_opacity_var.get())))
        except (tk.TclError, ValueError):
            return
        layer["name"] = self.clean_image_name(self.image_name_var.get(), self.next_image_auto_name())
        layer["x"] = x
        layer["y"] = y
        layer["scale"] = scale
        layer["opacity"] = opacity
        self.store.mark_dirty("png-image-updated")
        self.refresh_image_selector()
        self.redraw_output()
        self.schedule_autosave()

    def layer_image_up(self) -> None:
        layer = self.selected_image_layer()
        if not layer:
            return
        max_z = max([int(item.get("z", 0)) for item in self.store.active_card().get("layers", [])] or [0])
        layer["z"] = min(max_z + 1, int(layer.get("z", 0)) + 1)
        self.store.mark_dirty("png-image-layer-up")
        self.refresh_image_selector()
        self.redraw_output()
        self.schedule_autosave()

    def layer_image_down(self) -> None:
        layer = self.selected_image_layer()
        if not layer:
            return
        layer["z"] = max(0, int(layer.get("z", 0)) - 1)
        self.store.mark_dirty("png-image-layer-down")
        self.refresh_image_selector()
        self.redraw_output()
        self.schedule_autosave()

    def delete_image_layer(self) -> None:
        card = self.store.active_card()
        selected_id = self.selected_image_id_var.get()
        if not selected_id:
            return
        layers = card.get("layers", [])
        card["layers"] = [layer for layer in layers if layer.get("id") != selected_id]
        self.selected_image_id_var.set("")
        self.selected_image_label_var.set("")
        self.store.mark_dirty("png-image-deleted")
        self.refresh_image_selector()
        self.redraw_output()
        self.schedule_autosave()

    def text_layers(self) -> list[dict]:
        card = self.store.active_card()
        return [layer for layer in card.get("layers", []) if layer.get("type") == "text"]

    def clean_text_layer_name(self, value: str, fallback: str = "Text") -> str:
        cleaned = (value or "").strip()[:19]
        return cleaned or fallback[:19]

    def next_text_layer_auto_name(self) -> str:
        existing = {self.clean_text_layer_name(layer.get("name", ""), "") for layer in self.text_layers()}
        n = 1
        while True:
            candidate = f"Text {n}"
            if candidate not in existing:
                return candidate
            n += 1

    def selected_text_layer(self) -> dict | None:
        selected_id = self.selected_text_layer_id_var.get()
        for layer in self.text_layers():
            if layer.get("id") == selected_id:
                return layer
        return None

    def text_layer_display_label(self, layer: dict) -> str:
        name = self.clean_text_layer_name(layer.get("name", ""), layer.get("id", "Text"))
        hidden = "" if layer.get("visible", True) else "  [hidden]"
        return f"{name}  T{hidden}"

    def refresh_text_layer_selector(self) -> None:
        if self.text_layer_selector is None:
            return
        layers = self.text_layers()
        label_to_id = {}
        values = []
        for layer in layers:
            label = self.text_layer_display_label(layer)
            base = label
            counter = 2
            while label in label_to_id:
                label = f"{base} ({counter})"
                counter += 1
            label_to_id[label] = layer.get("id", "")
            values.append(label)
        self.text_layer_label_to_id = label_to_id
        self.text_layer_selector.configure(values=values)

        current_id = self.selected_text_layer_id_var.get()
        current_label = ""
        for label, layer_id in label_to_id.items():
            if layer_id == current_id:
                current_label = label
                break
        if not current_label and values:
            current_label = values[0]
            self.selected_text_layer_id_var.set(label_to_id[current_label])
        self.selected_text_layer_label_var.set(current_label)
        self.load_selected_text_layer_into_controls()

    def load_selected_text_layer_into_controls(self) -> None:
        layer = self.selected_text_layer()
        if not layer:
            self.text_layer_name_var.set(self.next_text_layer_auto_name())
            self.text_layer_color_var.set("#e8fff5")
            self.text_layer_wrap_var.set(260)
            if self.text_layer_text is not None:
                self.text_layer_text.delete("1.0", "end")
                self.text_layer_text.insert("1.0", "New text layer")
                self.text_layer_text.edit_modified(False)
            return
        self.text_layer_name_var.set(self.clean_text_layer_name(layer.get("name", ""), "Text"))
        self.text_layer_x_var.set(int(layer.get("x", 740)))
        self.text_layer_y_var.set(int(layer.get("y", 185)))
        self.text_layer_size_var.set(int(layer.get("size", 22)))
        self.text_layer_opacity_var.set(float(layer.get("opacity", 1.0)))
        self.text_layer_color_var.set(normalize_hex_color(layer.get("color", "#e8fff5")))
        self.text_layer_wrap_var.set(int(layer.get("wrap_width", 260)))
        if self.text_layer_text is not None:
            self.text_layer_text.delete("1.0", "end")
            self.text_layer_text.insert("1.0", layer.get("text", ""))
            self.text_layer_text.edit_modified(False)

    def on_text_layer_selected(self, _event=None) -> None:
        selected_label = self.selected_text_layer_label_var.get()
        selected_id = self.text_layer_label_to_id.get(selected_label, "")
        self.selected_text_layer_id_var.set(selected_id)
        self.load_selected_text_layer_into_controls()

    def text_layer_content_value(self) -> str:
        if self.text_layer_text is None:
            return ""
        return self.text_layer_text.get("1.0", "end").rstrip()

    def schedule_text_layer_stage_only(self) -> None:
        if self.selected_text_layer_id_var.get():
            self.store.data["stage"]["save_body_pending"] = True
            self.store.mark_dirty("text-layer-stage-updated")
            self.schedule_autosave()

    def on_text_layer_focus_out(self, _event=None) -> None:
        self.apply_text_layer_editor()

    def on_text_layer_modified(self, _event=None) -> None:
        if self.text_layer_text is None:
            return
        if self.text_layer_text.edit_modified():
            self.schedule_text_layer_stage_only()
            self.text_layer_text.edit_modified(False)

    def add_text_layer(self) -> None:
        card = self.store.active_card()
        if card.get("type") == "blank":
            return
        layers = card.setdefault("layers", [])
        existing_z = [int(layer.get("z", 0)) for layer in layers]
        z = (max(existing_z) + 1) if existing_z else 1
        layer_id = f"text-{uuid.uuid4().hex[:8]}"
        fallback_name = self.next_text_layer_auto_name()
        try:
            x = max(0, min(OUTPUT_WIDTH, int(self.text_layer_x_var.get())))
            y = max(0, min(OUTPUT_HEIGHT, int(self.text_layer_y_var.get())))
            size = max(8, min(72, int(self.text_layer_size_var.get())))
            opacity = max(0.1, min(1.0, float(self.text_layer_opacity_var.get())))
            wrap_width = max(80, min(900, int(self.text_layer_wrap_var.get())))
        except (tk.TclError, ValueError):
            x, y, size, opacity, wrap_width = 740, 185, 22, 1.0, 260
        layer = {
            "id": layer_id,
            "type": "text",
            "name": self.clean_text_layer_name(self.text_layer_name_var.get(), fallback_name),
            "text": self.text_layer_content_value() or "New text layer",
            "x": x,
            "y": y,
            "size": size,
            "opacity": opacity,
            "color": normalize_hex_color(self.text_layer_color_var.get()),
            "wrap_width": wrap_width,
            "z": z,
            "visible": True,
        }
        layers.append(layer)
        self.selected_text_layer_id_var.set(layer_id)
        self.store.mark_dirty("text-layer-added")
        self.refresh_text_layer_selector()
        self.redraw_output()
        self.schedule_autosave()

    def apply_text_layer_editor(self) -> None:
        layer = self.selected_text_layer()
        if not layer:
            return
        try:
            x = max(0, min(OUTPUT_WIDTH, int(self.text_layer_x_var.get())))
            y = max(0, min(OUTPUT_HEIGHT, int(self.text_layer_y_var.get())))
            size = max(8, min(72, int(self.text_layer_size_var.get())))
            opacity = max(0.1, min(1.0, float(self.text_layer_opacity_var.get())))
            wrap_width = max(80, min(900, int(self.text_layer_wrap_var.get())))
        except (tk.TclError, ValueError):
            return
        layer["name"] = self.clean_text_layer_name(self.text_layer_name_var.get(), self.next_text_layer_auto_name())
        layer["text"] = self.text_layer_content_value() or "New text layer"
        layer["x"] = x
        layer["y"] = y
        layer["size"] = size
        layer["opacity"] = opacity
        layer["color"] = normalize_hex_color(self.text_layer_color_var.get())
        layer["wrap_width"] = wrap_width
        self.store.mark_dirty("text-layer-updated")
        self.refresh_text_layer_selector()
        self.redraw_output()
        self.schedule_autosave()

    def layer_text_up(self) -> None:
        layer = self.selected_text_layer()
        if not layer:
            return
        max_z = max([int(item.get("z", 0)) for item in self.store.active_card().get("layers", [])] or [0])
        layer["z"] = min(max_z + 1, int(layer.get("z", 0)) + 1)
        self.store.mark_dirty("text-layer-up")
        self.refresh_text_layer_selector()
        self.redraw_output()
        self.schedule_autosave()

    def layer_text_down(self) -> None:
        layer = self.selected_text_layer()
        if not layer:
            return
        layer["z"] = max(0, int(layer.get("z", 0)) - 1)
        self.store.mark_dirty("text-layer-down")
        self.refresh_text_layer_selector()
        self.redraw_output()
        self.schedule_autosave()

    def delete_text_layer(self) -> None:
        card = self.store.active_card()
        selected_id = self.selected_text_layer_id_var.get()
        if not selected_id:
            return
        layers = card.get("layers", [])
        card["layers"] = [layer for layer in layers if layer.get("id") != selected_id]
        self.selected_text_layer_id_var.set("")
        self.selected_text_layer_label_var.set("")
        self.store.mark_dirty("text-layer-deleted")
        self.refresh_text_layer_selector()
        self.redraw_output()
        self.schedule_autosave()

    def max_layer_z(self) -> int:
        return max([int(layer.get("z", 0)) for layer in self.store.active_card().get("layers", [])] or [0])

    def duplicate_layer_common(self, layer: dict | None, layer_type: str) -> dict | None:
        if not layer:
            return None
        duplicate = copy.deepcopy(layer)
        duplicate["x"] = max(0, min(OUTPUT_WIDTH, int(duplicate.get("x", 0)) + 20))
        duplicate["y"] = max(0, min(OUTPUT_HEIGHT, int(duplicate.get("y", 0)) + 20))
        duplicate["z"] = self.max_layer_z() + 1
        duplicate["visible"] = True
        if layer_type == "emoji":
            duplicate["id"] = f"emoji-{uuid.uuid4().hex[:8]}"
            duplicate["name"] = self.clean_sticker_name("Copy " + str(layer.get("name", "Emoji")), self.next_sticker_auto_name())
        elif layer_type == "image":
            duplicate["id"] = f"image-{uuid.uuid4().hex[:8]}"
            duplicate["name"] = self.clean_image_name("Copy " + str(layer.get("name", "Image")), self.next_image_auto_name())
        elif layer_type == "text":
            duplicate["id"] = f"text-{uuid.uuid4().hex[:8]}"
            duplicate["name"] = self.clean_text_layer_name("Copy " + str(layer.get("name", "Text")), self.next_text_layer_auto_name())
        self.store.active_card().setdefault("layers", []).append(duplicate)
        return duplicate

    def duplicate_sticker(self) -> None:
        duplicate = self.duplicate_layer_common(self.selected_sticker(), "emoji")
        if not duplicate:
            return
        self.selected_sticker_id_var.set(duplicate["id"])
        self.store.mark_dirty("emoji-sticker-duplicated")
        self.refresh_sticker_selector()
        self.redraw_output()
        self.schedule_autosave()

    def duplicate_image_layer(self) -> None:
        duplicate = self.duplicate_layer_common(self.selected_image_layer(), "image")
        if not duplicate:
            return
        self.selected_image_id_var.set(duplicate["id"])
        self.store.mark_dirty("png-image-duplicated")
        self.refresh_image_selector()
        self.redraw_output()
        self.schedule_autosave()

    def duplicate_text_layer(self) -> None:
        duplicate = self.duplicate_layer_common(self.selected_text_layer(), "text")
        if not duplicate:
            return
        self.selected_text_layer_id_var.set(duplicate["id"])
        self.store.mark_dirty("text-layer-duplicated")
        self.refresh_text_layer_selector()
        self.redraw_output()
        self.schedule_autosave()

    def set_layer_visibility(self, layer: dict | None, visible: bool, reason: str) -> None:
        if not layer:
            return
        layer["visible"] = bool(visible)
        self.store.mark_dirty(reason)
        self.refresh_sticker_selector()
        self.refresh_image_selector()
        self.refresh_text_layer_selector()
        self.redraw_output()
        self.schedule_autosave()

    def show_sticker(self) -> None:
        self.set_layer_visibility(self.selected_sticker(), True, "emoji-sticker-shown")

    def hide_sticker(self) -> None:
        self.set_layer_visibility(self.selected_sticker(), False, "emoji-sticker-hidden")

    def show_image_layer(self) -> None:
        self.set_layer_visibility(self.selected_image_layer(), True, "png-image-shown")

    def hide_image_layer(self) -> None:
        self.set_layer_visibility(self.selected_image_layer(), False, "png-image-hidden")

    def show_text_layer(self) -> None:
        self.set_layer_visibility(self.selected_text_layer(), True, "text-layer-shown")

    def hide_text_layer(self) -> None:
        self.set_layer_visibility(self.selected_text_layer(), False, "text-layer-hidden")

    def layer_size_for_alignment(self, layer: dict | None) -> tuple[int, int]:
        if not layer:
            return (0, 0)
        layer_type = layer.get("type")
        if layer_type == "emoji":
            size = max(8, min(96, int(layer.get("size", 26))))
            return (size, size)
        if layer_type == "image":
            source_path = Path(layer.get("source_path", ""))
            scale = max(10, min(400, int(layer.get("scale", 100))))
            if source_path.exists() and Image is not None:
                try:
                    base = self.base_image_cache.get(str(source_path))
                    if base is None:
                        base = Image.open(source_path).convert("RGBA")
                        self.base_image_cache[str(source_path)] = base
                    return (max(4, int(base.width * scale / 100)), max(4, int(base.height * scale / 100)))
                except Exception:
                    pass
            return (100, 100)
        if layer_type == "text":
            width = max(80, min(900, int(layer.get("wrap_width", 260))))
            txt = str(layer.get("text", ""))
            size = max(8, min(72, int(layer.get("size", 22))))
            approx_lines = max(1, min(10, (len(txt) // max(12, width // max(size, 1))) + 1))
            return (width, max(size + 4, approx_lines * (size + 4)))
        return (0, 0)

    def set_layer_position(self, layer: dict | None, x: int, y: int, reason: str) -> None:
        if not layer:
            return
        w, h = self.layer_size_for_alignment(layer)
        x = max(0, min(OUTPUT_WIDTH - min(w, OUTPUT_WIDTH), int(x)))
        y = max(0, min(OUTPUT_HEIGHT - min(h, OUTPUT_HEIGHT), int(y)))
        layer["x"] = x
        layer["y"] = y
        if layer.get("type") == "emoji":
            self.sticker_x_var.set(x)
            self.sticker_y_var.set(y)
            self.refresh_sticker_selector()
        elif layer.get("type") == "image":
            self.image_x_var.set(x)
            self.image_y_var.set(y)
            self.refresh_image_selector()
        elif layer.get("type") == "text":
            self.text_layer_x_var.set(x)
            self.text_layer_y_var.set(y)
            self.refresh_text_layer_selector()
        self.store.mark_dirty(reason)
        self.redraw_output()
        self.schedule_autosave()

    def nudge_layer(self, layer: dict | None, dx: int, dy: int, reason: str) -> None:
        if not layer:
            return
        self.set_layer_position(layer, int(layer.get("x", 0)) + dx, int(layer.get("y", 0)) + dy, reason)

    def snap_layer(self, layer: dict | None, target: str, reason: str) -> None:
        if not layer:
            return
        safe_x1, safe_y1 = 52, 72
        safe_x2, safe_y2 = OUTPUT_WIDTH - 52, OUTPUT_HEIGHT - 40
        w, h = self.layer_size_for_alignment(layer)
        x = int(layer.get("x", 0))
        y = int(layer.get("y", 0))
        if target == "left":
            x = safe_x1
        elif target == "center_x":
            x = safe_x1 + ((safe_x2 - safe_x1 - w) // 2)
        elif target == "right":
            x = safe_x2 - w
        elif target == "top":
            y = safe_y1
        elif target == "center_y":
            y = safe_y1 + ((safe_y2 - safe_y1 - h) // 2)
        elif target == "bottom":
            y = safe_y2 - h
        self.set_layer_position(layer, x, y, reason)

    def nudge_sticker(self, dx: int, dy: int) -> None:
        self.nudge_layer(self.selected_sticker(), dx, dy, "emoji-sticker-nudged")

    def snap_sticker(self, target: str) -> None:
        self.snap_layer(self.selected_sticker(), target, "emoji-sticker-snapped")

    def nudge_image_layer(self, dx: int, dy: int) -> None:
        self.nudge_layer(self.selected_image_layer(), dx, dy, "png-image-nudged")

    def snap_image_layer(self, target: str) -> None:
        self.snap_layer(self.selected_image_layer(), target, "png-image-snapped")

    def nudge_text_layer(self, dx: int, dy: int) -> None:
        self.nudge_layer(self.selected_text_layer(), dx, dy, "text-layer-nudged")

    def snap_text_layer(self, target: str) -> None:
        self.snap_layer(self.selected_text_layer(), target, "text-layer-snapped")

    def editor_values(self) -> dict:
        return {
            "sourceType": self.source_type_var.get().strip() or "Unknown",
            "confidence": self.confidence_var.get().strip() or "Still Checking",
            "sourceLink": self.source_link_var.get().strip(),
            "claim": self.claim_text.get("1.0", "end-1c").strip(),
            "evidence": self.evidence_text.get("1.0", "end-1c").strip(),
            "openQuestion": self.open_question_text.get("1.0", "end-1c").strip(),
            "verdict": self.verdict_var.get().strip() or "Still Checking",
        }

    def apply_editor_to_card(self) -> None:
        card = self.store.active_card()
        card["label"] = (self.card_label_var.get() or card.get("label", "Card")).strip()[:32] or "Card"
        if card.get("type") == "source_analyzer":
            card["fields"] = self.editor_values()
        self.store.data["under_header"]["scan_loop"] = bool(self.scan_loop_var.get())
        self.store.data["under_header"]["scan_speed_ms"] = int(self.scan_speed_var.get())
        self.store.data["under_header"]["scanner_color"] = self.scanner_color_var.get().strip() or "#00ff99"
        self.store.data["under_header"]["output_visible"] = bool(self.output_visible_var.get())
        self.store.data["header"]["resource_profile"] = self.resource_profile_var.get()
        self.store.mark_dirty("editor-applied")
        self.refresh_deck_buttons()
        self.redraw_output()
        self.status_var.set("Applied")
        self.schedule_autosave()

    def on_text_modified(self, event: tk.Event) -> None:
        widget = event.widget
        if widget.edit_modified():
            widget.edit_modified(False)
            self.schedule_autosave_stage_only()

    def on_editor_focus_out(self, _event: tk.Event) -> None:
        self.apply_editor_to_card()

    def schedule_autosave_stage_only(self) -> None:
        self.store.data["stage"]["draft_cards"][self.store.active_card().get("id")] = self.editor_values()
        self.store.data["stage"]["save_body_pending"] = True
        self.store.mark_dirty("stage-draft-updated")
        self.schedule_autosave()

    def schedule_autosave(self) -> None:
        if self.autosave_after_id:
            try:
                self.root.after_cancel(self.autosave_after_id)
            except tk.TclError:
                pass
        profile = self.resource_profile_var.get()
        delay = RESOURCE_PROFILES.get(profile, RESOURCE_PROFILES["low"])["autosave_delay_ms"]
        self.autosave_after_id = self.root.after(delay, self.autosave_tick)

    def autosave_tick(self) -> None:
        self.autosave_after_id = None
        self.apply_editor_to_card_without_reschedule()
        self.store.save("autosave")
        self.status_var.set("Autosaved")

    def apply_editor_to_card_without_reschedule(self) -> None:
        card = self.store.active_card()
        card["label"] = (self.card_label_var.get() or card.get("label", "Card")).strip()[:32] or "Card"
        if card.get("type") == "source_analyzer":
            card["fields"] = self.editor_values()
        self.store.data["under_header"]["scan_loop"] = bool(self.scan_loop_var.get())
        self.store.data["under_header"]["scan_speed_ms"] = int(self.scan_speed_var.get())
        self.store.data["under_header"]["scanner_color"] = self.scanner_color_var.get().strip() or "#00ff99"
        self.store.data["under_header"]["output_visible"] = bool(self.output_visible_var.get())
        self.store.data["header"]["resource_profile"] = self.resource_profile_var.get()
        self.store.mark_dirty("editor-applied")

    def redraw_output(self) -> None:
        self.output_canvas.delete("all")
        self.render_image_refs = []
        card = self.store.active_card()
        if card.get("type") == "blank":
            self.draw_blank_panel()
            return
        self.draw_source_analyzer(card)

    def draw_blank_panel(self) -> None:
        c = self.output_canvas
        c.configure(bg="#07090c")
        c.create_rectangle(0, 0, OUTPUT_WIDTH, OUTPUT_HEIGHT, fill="#07090c", outline="")
        c.create_text(OUTPUT_WIDTH // 2, OUTPUT_HEIGHT // 2, text="", fill="#07090c", font=("TkDefaultFont", 1))

    def draw_source_analyzer(self, card: dict) -> None:
        c = self.output_canvas
        bg = self.store.data["header"]["output"].get("background", "#121418")
        accent = self.scanner_color_var.get().strip() or "#00ff99"
        c.configure(bg=bg)
        c.create_rectangle(0, 0, OUTPUT_WIDTH, OUTPUT_HEIGHT, fill=bg, outline="")
        c.create_rectangle(14, 14, OUTPUT_WIDTH - 14, OUTPUT_HEIGHT - 14, fill="#10151b", outline="#26333a", width=2)
        c.create_line(24, 54, OUTPUT_WIDTH - 24, 54, fill="#26333a")

        bracket = 28
        for x1, y1, sx, sy in [(20, 20, 1, 1), (OUTPUT_WIDTH - 20, 20, -1, 1), (20, OUTPUT_HEIGHT - 20, 1, -1), (OUTPUT_WIDTH - 20, OUTPUT_HEIGHT - 20, -1, -1)]:
            c.create_line(x1, y1, x1 + bracket * sx, y1, fill=accent, width=2)
            c.create_line(x1, y1, x1, y1 + bracket * sy, fill=accent, width=2)

        c.create_text(34, 38, anchor="w", text="3DCP SOURCE ANALYZER", fill="#e8fff5", font=("TkDefaultFont", 19, "bold"))
        c.create_text(OUTPUT_WIDTH - 38, 38, anchor="e", text="STATUS: LIVE", fill=accent, font=("TkDefaultFont", 12, "bold"))

        block_x1, block_y1, block_x2, block_y2 = 40, 72, OUTPUT_WIDTH - 40, 188
        c.create_rectangle(block_x1, block_y1, block_x2, block_y2, fill="#0c1116", outline="#18242b")

        fields = card.get("fields", {})
        link_text = fields.get("sourceLink", "").strip()
        has_link = bool(link_text)

        # Far-right aligned third column; QR column only when link exists.
        right_col_x2 = block_x2 - 18
        right_col_width = 250
        right_col_x1 = right_col_x2 - right_col_width

        if has_link:
            qr_size = 92
            qr_gap = 18
            qr_x2 = right_col_x1 - qr_gap
            qr_x1 = qr_x2 - qr_size
            left_x2 = qr_x1 - qr_gap
        else:
            qr_size = 0
            qr_x1 = qr_x2 = None
            left_x2 = right_col_x1 - 18

        left_x1 = 52

        # Column separators
        c.create_line(left_x2, block_y1 + 12, left_x2, block_y2 - 12, fill="#203037")
        if has_link:
            c.create_line(right_col_x1 - 9, block_y1 + 12, right_col_x1 - 9, block_y2 - 12, fill="#203037")

        self.draw_row(c, left_x1, 96, "SOURCE TYPE:", fields.get("sourceType", "Unknown"), accent, value_x=200, line_end=left_x2 - 10)
        self.draw_row(c, left_x1, 128, "CONFIDENCE:", fields.get("confidence", "Still Checking"), accent, value_x=200, line_end=left_x2 - 10)
        self.draw_row(c, left_x1, 160, "VERDICT:", fields.get("verdict", "Still Checking"), accent, value_x=200, line_end=left_x2 - 10)

        if has_link:
            c.create_text(qr_x1 + qr_size / 2, 84, text="SOURCE QR", fill="#8aa39b", font=("TkDefaultFont", 10, "bold"))
            c.create_rectangle(qr_x1, 92, qr_x2, 92 + qr_size, fill="#ffffff", outline="#d8e2de")
            self.draw_qr(c, qr_x1, 92, qr_size, link_text)

        # Third column right aligned to free space for first column.
        right_text_x = right_col_x2 - 4
        c.create_text(right_text_x, 106, anchor="e", text="THE PERSPECTIVE LAB", fill="#668078", font=("TkDefaultFont", 10, "bold"))
        c.create_text(right_text_x, 126, anchor="e", text="PROOF ANALYSIS CONSOLE", fill="#445953", font=("TkDefaultFont", 10))
        if has_link:
            host = urlparse(link_text).netloc or "link ready"
            activity = "ACTIVITY: LINK READY"
            host_label = f"HOST: {host}"
        else:
            activity = ""
            host_label = ""
        if activity:
            c.create_text(right_text_x, 154, anchor="e", text=activity, fill=accent, font=("TkDefaultFont", 10, "bold"))
        if host_label:
            c.create_text(right_text_x, 172, anchor="e", text=host_label, fill="#8aa39b", font=("TkDefaultFont", 9))

        self.draw_boxed_text(c, 52, 232, "CURRENT CLAIM:", fields.get("claim", ""), width=856, height=62, accent=accent, max_lines=2)
        self.draw_boxed_text(c, 52, 322, "EVIDENCE SHOWN:", fields.get("evidence", ""), width=856, height=62, accent=accent, max_lines=2)
        self.draw_boxed_text(c, 52, 412, "OPEN QUESTION:", fields.get("openQuestion", ""), width=856, height=58, accent=accent, max_lines=2)

        for layer in sorted(card.get("layers", []), key=lambda item: item.get("z", 0)):
            if layer.get("visible", True) is False:
                continue
            if layer.get("type") == "image":
                self.draw_image_layer(c, layer)
            elif layer.get("type") == "text":
                self.draw_text_layer(c, layer)
            elif layer.get("type") == "emoji":
                lx = int(layer.get("x", 900))
                ly = int(layer.get("y", 210))
                # Legacy v0.1-v0.2.3 default magnifier sat over STATUS at y≈28.
                # Move only that built-in sticker down; future user-edited stickers keep their saved coordinates.
                if layer.get("id") == "emoji-default-scan" and ly <= 45:
                    ly = 210
                opacity = max(0.1, min(1.0, float(layer.get("opacity", 1.0))))
                fill = "#e8fff5" if opacity >= 0.75 else "#9fb8af" if opacity >= 0.45 else "#60736d"
                c.create_text(lx, ly, text=layer.get("text", "🔍"), fill=fill, font=("TkDefaultFont", int(layer.get("size", 26))))

    def draw_text_layer(self, canvas: tk.Canvas, layer: dict) -> None:
        txt = str(layer.get("text", ""))
        if not txt.strip():
            return
        x = int(layer.get("x", 740))
        y = int(layer.get("y", 185))
        size = max(8, min(72, int(layer.get("size", 22))))
        wrap_width = max(80, min(900, int(layer.get("wrap_width", 260))))
        opacity = max(0.1, min(1.0, float(layer.get("opacity", 1.0))))
        color = blend_hex_colors(layer.get("color", "#e8fff5"), "#121418", opacity)
        canvas.create_text(x, y, anchor="nw", text=txt, fill=color, width=wrap_width, font=("TkDefaultFont", size))

    def draw_image_layer(self, canvas: tk.Canvas, layer: dict) -> None:
        source_path = Path(layer.get("source_path", ""))
        if not source_path.exists() or Image is None or ImageTk is None:
            return

        try:
            base = self.base_image_cache.get(str(source_path))
            if base is None:
                base = Image.open(source_path).convert("RGBA")
                self.base_image_cache[str(source_path)] = base

            scale = max(10, min(400, int(layer.get("scale", 100))))
            opacity = max(0.1, min(1.0, float(layer.get("opacity", 1.0))))
            width = max(4, int(base.width * scale / 100))
            height = max(4, int(base.height * scale / 100))
            cache_key = (str(source_path), width, height, round(opacity, 2))
            photo = self.rendered_image_cache.get(cache_key)
            if photo is None:
                resized = base.resize((width, height), Image.LANCZOS)
                if opacity < 0.999:
                    alpha = resized.getchannel("A")
                    alpha = alpha.point(lambda a: int(a * opacity))
                    resized.putalpha(alpha)
                photo = ImageTk.PhotoImage(resized)
                self.rendered_image_cache[cache_key] = photo

            x = int(layer.get("x", 760))
            y = int(layer.get("y", 245))
            self.render_image_refs.append(photo)
            canvas.create_image(x, y, anchor="nw", image=photo)
        except Exception:
            return

    def draw_qr(self, canvas: tk.Canvas, x: int, y: int, size: int, link: str) -> None:
        link = (link or "").strip()
        if not link or not QR_AVAILABLE:
            return
        inner_pad = 6
        if self.qr_cache_link != link:
            qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
            qr.add_data(link)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            img = img.resize((size - inner_pad * 2, size - inner_pad * 2))
            self.qr_photo = ImageTk.PhotoImage(img)
            self.qr_cache_link = link
        canvas.create_image(x + inner_pad, y + inner_pad, anchor="nw", image=self.qr_photo)

    def draw_row(self, canvas: tk.Canvas, x: int, y: int, label: str, value: str, accent: str, value_x: int, line_end: int) -> None:
        canvas.create_text(x, y, anchor="w", text=label, fill="#8aa39b", font=("TkDefaultFont", 12, "bold"))
        canvas.create_text(value_x, y, anchor="w", text=value, fill="#f0fff8", font=("TkDefaultFont", 15, "bold"))
        canvas.create_line(value_x, y + 15, max(value_x + 10, line_end), y + 15, fill="#1b2f2b")
        canvas.create_rectangle(value_x - 8, y - 14, value_x - 4, y + 17, fill=accent, outline="")

    def draw_boxed_text(self, canvas: tk.Canvas, x: int, y: int, label: str, value: str, width: int, height: int, accent: str, max_lines: int = 2) -> None:
        canvas.create_text(x, y - 16, anchor="w", text=label, fill="#8aa39b", font=("TkDefaultFont", 11, "bold"))
        canvas.create_rectangle(x, y, x + width, y + height, fill="#111920", outline="#203037")
        canvas.create_rectangle(x, y, x + 4, y + height, fill=accent, outline="")
        wrapped = self.wrap_text_pixels(value, ("TkDefaultFont", 12), max_width=width - 26, max_lines=max_lines)
        canvas.create_text(x + 14, y + 11, anchor="nw", text=wrapped, fill="#f1fff9", font=("TkDefaultFont", 12))

    def wrap_text_pixels(self, text: str, font_spec, max_width: int, max_lines: int = 2) -> str:
        text = (text or "").replace("\n", " ").strip()
        if not text:
            return ""
        font = tkfont.Font(root=self.root, font=font_spec)
        words = text.split()
        lines = []
        current = ""

        def fit_with_ellipsis(s: str) -> str:
            if font.measure(s) <= max_width:
                return s
            ell = "..."
            while s and font.measure(s + ell) > max_width:
                s = s[:-1]
            return (s.rstrip() + ell) if s else ell

        i = 0
        while i < len(words):
            word = words[i]
            candidate = word if not current else current + " " + word
            if font.measure(candidate) <= max_width:
                current = candidate
                i += 1
                continue
            if not current:
                fragment = word
                while fragment and font.measure(fragment) > max_width:
                    fragment = fragment[:-1]
                if not fragment:
                    fragment = word[:1]
                current = fragment
                words[i] = word[len(fragment):] if len(fragment) < len(word) else ""
                if not words[i]:
                    i += 1
            lines.append(current)
            current = ""
            if len(lines) == max_lines:
                break
        if len(lines) < max_lines and current:
            lines.append(current)
        remaining_text = " ".join(words[i:]).strip()
        if len(lines) == max_lines and remaining_text:
            lines[-1] = fit_with_ellipsis(lines[-1] + " " + remaining_text if lines[-1] else remaining_text)
        return "\n".join(lines[:max_lines])

    def scan_once(self) -> None:
        if self.store.active_card().get("type") == "blank":
            return
        # Reset any in-flight scan immediately. Older scheduled frames exit when
        # their token no longer matches self.scan_token.
        self.scan_token += 1
        token = self.scan_token
        self.scan_active = True
        self.scan_y = 74
        self.redraw_output()
        self.run_scan_frame(loop=False, token=token)

    def toggle_scan_loop(self) -> None:
        self.scan_token += 1
        token = self.scan_token
        self.store.data["under_header"]["scan_loop"] = bool(self.scan_loop_var.get())
        self.store.mark_dirty("scan-loop-toggled")
        if self.scan_loop_var.get():
            self.scan_active = True
            self.scan_y = 74
            self.run_scan_frame(loop=True, token=token)
        else:
            self.scan_active = False
            self.redraw_output()
        self.schedule_autosave()

    def run_scan_frame(self, loop: bool, token: int | None = None) -> None:
        if token is None:
            token = self.scan_token
        if token != self.scan_token:
            return
        if not self.scan_active:
            return
        if self.store.active_card().get("type") == "blank":
            self.scan_active = False
            return
        self.redraw_output()
        c = self.output_canvas
        accent = self.scanner_color_var.get().strip() or "#00ff99"
        c.create_rectangle(42, self.scan_y, OUTPUT_WIDTH - 42, self.scan_y + 3, fill=accent, outline="")
        c.create_rectangle(42, self.scan_y + 4, OUTPUT_WIDTH - 42, self.scan_y + 15, fill="#17362b", outline="", stipple="gray50")
        c.create_text(OUTPUT_WIDTH - 125, 210, text="ANALYZING...", fill=accent, font=("TkDefaultFont", 10, "bold"))
        self.scan_y += 8
        if self.scan_y > OUTPUT_HEIGHT - 34:
            if loop or self.scan_loop_var.get():
                self.scan_y = 74
            else:
                self.scan_active = False
                self.redraw_output()
                return
        delay = max(20, int(self.scan_speed_var.get()))
        self.root.after(delay, lambda: self.run_scan_frame(loop=loop, token=token))

    def on_scan_speed_drag(self, value: str) -> None:
        ms = int(float(value))
        self.scan_speed_var.set(ms)
        # Tk can fire the Scale callback during widget construction before speed_label exists.
        # Guarding here prevents a startup traceback and keeps launch stable.
        if hasattr(self, "speed_label"):
            self.speed_label.configure(text=f"{ms} ms")
        if hasattr(self, "store"):
            self.store.data["under_header"]["scan_speed_ms"] = ms
            self.store.mark_dirty("scan-speed-changed")

    def on_resource_profile_changed(self, _event=None) -> None:
        profile = self.resource_profile_var.get()
        profile_data = RESOURCE_PROFILES.get(profile, RESOURCE_PROFILES["low"])
        self.scan_speed_var.set(profile_data["scan_ms"])
        self.speed_scale.set(profile_data["scan_ms"])
        self.speed_label.configure(text=f"{profile_data['scan_ms']} ms")
        self.store.data["header"]["resource_profile"] = profile
        self.store.data["under_header"]["scan_speed_ms"] = profile_data["scan_ms"]
        self.store.mark_dirty("resource-profile-changed")
        self.schedule_autosave()

    def on_setting_changed(self) -> None:
        self.store.data["under_header"]["output_visible"] = bool(self.output_visible_var.get())
        self.store.mark_dirty("setting-changed")
        self.schedule_autosave()

    def recover_output_window_on_launch(self) -> None:
        """Map the OBS output window safely on KWin/X11/Wayland.

        Borderless windows can fail to visibly map if overrideredirect is applied
        too early. Startup always uses normal framed mode; the user can enable
        borderless later with Apply OBS Mode.
        """
        try:
            self.output.overrideredirect(False)
        except tk.TclError:
            pass
        try:
            self.output.attributes("-topmost", False)
        except tk.TclError:
            pass

        geo = self.store.data["under_header"].get("output_geometry") or DEFAULT_OUTPUT_GEOMETRY
        if not is_safe_geometry(geo, OUTPUT_WIDTH, OUTPUT_HEIGHT):
            geo = DEFAULT_OUTPUT_GEOMETRY
        try:
            self.output.geometry(geo)
        except tk.TclError:
            self.output.geometry(DEFAULT_OUTPUT_GEOMETRY)

        self.output.title(OUTPUT_TITLE)
        self.output.resizable(False, False)
        if self.output_visible_var.get():
            self.output.deiconify()
            self.output.lift()
            self.output.update_idletasks()
            # A second lift shortly after launch helps on KDE/KWin where a Toplevel
            # can exist but not paint until after the mainloop cycles once.
            self.root.after(250, self.bring_output_front)

        self.store.data["under_header"]["output_borderless"] = False
        self.store.data["under_header"]["output_topmost"] = False
        self.store.data["under_header"]["output_geometry"] = geo
        self.store.mark_dirty("output-launch-recovery")
        self.schedule_autosave()

    def rescue_output_window(self) -> None:
        """Emergency recovery button for OBS output visibility."""
        self.output_borderless_var.set(False)
        self.output_topmost_var.set(False)
        try:
            self.output.overrideredirect(False)
        except tk.TclError:
            pass
        try:
            self.output.attributes("-topmost", False)
        except tk.TclError:
            pass
        try:
            self.output.geometry(DEFAULT_OUTPUT_GEOMETRY)
        except tk.TclError:
            pass
        self.output.deiconify()
        self.output.lift()
        self.output.update_idletasks()
        try:
            self.output.focus_force()
        except tk.TclError:
            pass
        self.output_visible_var.set(True)
        self.store.data["under_header"]["output_visible"] = True
        self.store.data["under_header"]["output_borderless"] = False
        self.store.data["under_header"]["output_topmost"] = False
        self.store.data["under_header"]["output_geometry"] = DEFAULT_OUTPUT_GEOMETRY
        self.store.mark_dirty("output-window-rescued")
        self.schedule_autosave()
        self.status_var.set("Output window rescued")

    def apply_output_window_style(self, save: bool = True) -> None:
        """Apply OBS output window behavior after the window is visible."""
        try:
            current_geo = self.output.geometry()
        except tk.TclError:
            current_geo = DEFAULT_OUTPUT_GEOMETRY
        if not is_safe_geometry(current_geo, OUTPUT_WIDTH, OUTPUT_HEIGHT):
            current_geo = DEFAULT_OUTPUT_GEOMETRY

        # Always map and paint the window before toggling borderless.
        self.output.deiconify()
        self.output.title(OUTPUT_TITLE)
        self.output.geometry(current_geo)
        self.output.resizable(False, False)
        self.output.update_idletasks()

        try:
            self.output.overrideredirect(bool(self.output_borderless_var.get()))
            self.output.geometry(current_geo)
            self.output.update_idletasks()
        except tk.TclError:
            pass

        try:
            self.output.attributes("-topmost", bool(self.output_topmost_var.get()))
        except tk.TclError:
            pass

        if save:
            self.store.data["under_header"]["output_topmost"] = bool(self.output_topmost_var.get())
            self.store.data["under_header"]["output_borderless"] = bool(self.output_borderless_var.get())
            self.store.data["under_header"]["output_geometry"] = current_geo
            self.store.mark_dirty("output-style-changed")
            self.schedule_autosave()

    def enable_obs_output_mode(self) -> None:
        self.show_output()
        self.output.update_idletasks()
        self.output_topmost_var.set(True)
        self.output_borderless_var.set(True)
        self.apply_output_window_style(save=True)
        self.bring_output_front()
        self.status_var.set("OBS output mode enabled")

    def disable_obs_output_mode(self) -> None:
        self.output_borderless_var.set(False)
        self.output_topmost_var.set(False)
        self.apply_output_window_style(save=True)
        self.bring_output_front()
        self.status_var.set("Normal output mode enabled")

    def bring_output_front(self) -> None:
        self.output.deiconify()
        self.output.lift()
        try:
            self.output.focus_force()
        except tk.TclError:
            pass
        self.output_visible_var.set(True)
        self.on_setting_changed()
        self.status_var.set("Output brought to front")

    def reset_output_window_position(self) -> None:
        try:
            was_borderless = bool(self.output_borderless_var.get())
            # Temporarily restore frame for predictable geometry reset.
            if was_borderless:
                self.output.overrideredirect(False)
            self.output.geometry(DEFAULT_OUTPUT_GEOMETRY)
            if was_borderless:
                self.output.update_idletasks()
                self.output.overrideredirect(True)
                self.output.geometry(DEFAULT_OUTPUT_GEOMETRY)
        except tk.TclError:
            pass
        self.store.data["under_header"]["output_geometry"] = DEFAULT_OUTPUT_GEOMETRY
        self.store.mark_dirty("output-window-reset")
        self.schedule_autosave()
        self.status_var.set("Output window reset")

    def save_output_settings(self) -> None:
        self.store.data["under_header"]["output_visible"] = bool(self.output_visible_var.get())
        self.store.data["under_header"]["output_topmost"] = bool(self.output_topmost_var.get())
        self.store.data["under_header"]["output_borderless"] = bool(self.output_borderless_var.get())
        try:
            self.store.data["under_header"]["output_geometry"] = self.output.geometry()
        except tk.TclError:
            self.store.data["under_header"]["output_geometry"] = DEFAULT_OUTPUT_GEOMETRY
        self.store.save("output-settings-save")
        self.status_var.set("Output settings saved")

    def show_output(self) -> None:
        self.output.deiconify()
        self.output.title(OUTPUT_TITLE)
        self.output.geometry(self.store.data["under_header"].get("output_geometry", DEFAULT_OUTPUT_GEOMETRY))
        self.output.update_idletasks()
        self.output.lift()
        self.output_visible_var.set(True)
        self.on_setting_changed()

    def hide_output(self) -> None:
        self.output.withdraw()
        self.output_visible_var.set(False)
        self.on_setting_changed()

    def save_now(self) -> None:
        self.apply_sticker_editor()
        self.apply_image_editor()
        self.apply_text_layer_editor()
        self.apply_editor_to_card_without_reschedule()
        self.remember_window_geometry()
        self.store.save("manual-save")
        self.redraw_output()
        self.status_var.set(f"Saved: {self.store.path.name}")

    def save_as(self) -> None:
        path = filedialog.asksaveasfilename(title="Save .buttstore episode", defaultextension=".buttstore", filetypes=[("3DCP ButtStore", "*.buttstore"), ("JSON", "*.json"), ("All files", "*.*")], initialdir=str(BUTTSTORE_DIR))
        if not path:
            return
        self.apply_editor_to_card_without_reschedule()
        self.remember_window_geometry()
        self.store.save_as(Path(path))
        self.status_var.set(f"Saved As: {Path(path).name}")

    def load_buttstore(self) -> None:
        path = filedialog.askopenfilename(title="Load .buttstore episode", filetypes=[("3DCP ButtStore", "*.buttstore"), ("JSON", "*.json"), ("All files", "*.*")], initialdir=str(BUTTSTORE_DIR))
        if not path:
            return
        try:
            self.store = ButtStore.load_or_create(Path(path))
        except Exception as exc:
            messagebox.showerror("Could not load .buttstore", str(exc))
            return
        self.scan_loop_var.set(bool(self.store.data["under_header"].get("scan_loop", False)))
        self.output_visible_var.set(bool(self.store.data["under_header"].get("output_visible", True)))
        self.resource_profile_var.set(self.store.data["header"].get("resource_profile", "low"))
        self.scan_speed_var.set(int(self.store.data["under_header"].get("scan_speed_ms", 67)))
        self.scanner_color_var.set(self.store.data["under_header"].get("scanner_color", "#00ff99"))
        self.speed_scale.set(self.scan_speed_var.get())
        self.speed_label.configure(text=f"{self.scan_speed_var.get()} ms")
        self.qr_cache_link = None
        self.qr_photo = None
        self.base_image_cache = {}
        self.rendered_image_cache = {}
        self.refresh_deck_buttons()
        self.load_active_card_into_editor()
        self.redraw_output()
        self.status_var.set(f"Loaded: {Path(path).name}")

    def to_default_wipe(self) -> None:
        approved = messagebox.askyesno("To-default wipe", "Reset editable card content to public-clean defaults?\n\nFooter serial values will move forward, not backward.")
        if not approved:
            return
        self.store.wipe_to_default()
        self.scan_loop_var.set(False)
        self.output_visible_var.set(True)
        self.resource_profile_var.set("low")
        self.scan_speed_var.set(RESOURCE_PROFILES["low"]["scan_ms"])
        self.scanner_color_var.set("#00ff99")
        self.qr_cache_link = None
        self.qr_photo = None
        self.base_image_cache = {}
        self.rendered_image_cache = {}
        self.speed_scale.set(self.scan_speed_var.get())
        self.speed_label.configure(text=f"{self.scan_speed_var.get()} ms")
        self.refresh_deck_buttons()
        self.load_active_card_into_editor()
        self.redraw_output()
        self.status_var.set("To-default wipe complete")

    def remember_window_geometry(self) -> None:
        try:
            self.store.data["under_header"]["controller_geometry"] = self.root.geometry()
            self.store.data["under_header"]["output_geometry"] = self.output.geometry()
        except tk.TclError:
            pass

    def duplicate_buttstore_candidates(self) -> list[Path]:
        candidates: list[Path] = []
        if not BUTTSTORE_DIR.exists():
            return candidates
        patterns = [
            "*_migrated_*.buttstore",
            "*_legacy_*.buttstore",
            "default_episode_template.buttstore",
        ]
        seen = set()
        for pattern in patterns:
            for path in BUTTSTORE_DIR.glob(pattern):
                if path.is_file() and path not in seen:
                    candidates.append(path)
                    seen.add(path)
        return candidates

    def archive_duplicate_buttstores_after_load(self) -> None:
        """Move duplicate-looking buttstores aside after the UI is fully available.

        The archive is intentionally temporary: it stays available for review during
        the session and is removed on clean shutdown.
        """
        try:
            candidates = self.duplicate_buttstore_candidates()
            if not candidates:
                return
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            archive_dir = DUPLICATE_ARCHIVE_ROOT / stamp
            archive_dir.mkdir(parents=True, exist_ok=True)

            moved = 0
            for src in candidates:
                dest = archive_dir / src.name
                if dest.exists():
                    n = 1
                    while True:
                        candidate = archive_dir / f"{src.stem}_{n}{src.suffix}"
                        if not candidate.exists():
                            dest = candidate
                            break
                        n += 1
                shutil.move(str(src), str(dest))
                moved += 1

            if moved:
                self.store.data["under_header"]["last_duplicate_archive"] = str(archive_dir)
                self.store.mark_dirty("duplicate-buttstores-archived")
                self.store.save("duplicate-archive-after-load")
                self.status_var.set(f"Archived duplicate buttstores: {moved}")
        except Exception as exc:
            self.status_var.set(f"Duplicate archive skipped: {exc}")

    def cleanup_archived_duplicate_buttstores_on_shutdown(self) -> None:
        """Remove the temporary duplicate archive folder at clean shutdown."""
        try:
            if DUPLICATE_ARCHIVE_ROOT.exists():
                shutil.rmtree(DUPLICATE_ARCHIVE_ROOT)
                self.store.data["under_header"]["last_duplicate_archive_removed_at"] = utc_now()
                self.store.mark_dirty("duplicate-archive-cleaned-on-shutdown")
        except Exception as exc:
            try:
                self.store.data["under_header"]["duplicate_archive_cleanup_error"] = str(exc)
                self.store.mark_dirty("duplicate-archive-cleanup-error")
            except Exception:
                pass

    def export_current_card_png(self) -> None:
        if Image is None:
            messagebox.showerror("Export PNG unavailable", "Pillow is required for PNG export.")
            return

        self.apply_sticker_editor()
        self.apply_image_editor()
        self.apply_text_layer_editor()
        self.apply_editor_to_card_without_reschedule()
        self.remember_window_geometry()
        self.store.save("export-current-card")

        export_day = datetime.now().strftime("%Y%m%d")
        export_dir = EXPORT_ROOT_DIR / export_day
        export_dir.mkdir(parents=True, exist_ok=True)
        card = self.store.active_card()
        safe_label = re.sub(r"[^A-Za-z0-9._-]+", "_", str(card.get("label", card.get("id", "card")))).strip("_") or "card"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = export_dir / f"{safe_label}_{timestamp}.png"
        self.output_canvas.update_idletasks()

        try:
            # Tk Canvas can export PostScript without needing a redraw loop.
            ps = self.output_canvas.postscript(colormode="color")
            from io import BytesIO
            img = Image.open(BytesIO(ps.encode("utf-8")))
            img.save(path, "PNG")
            self.status_var.set(f"Exported PNG: {path.name}")
            messagebox.showinfo("Export complete", f"Saved PNG:\n{path}")
        except Exception as exc:
            messagebox.showerror("Export failed", f"Could not export current card as PNG:\n{exc}")

    def export_all_cards_png(self) -> None:
        if Image is None:
            messagebox.showerror("Export PNG unavailable", "Pillow is required for PNG export.")
            return

        self.apply_sticker_editor()
        self.apply_image_editor()
        self.apply_text_layer_editor()
        self.apply_editor_to_card_without_reschedule()
        self.remember_window_geometry()
        self.store.save("export-all-cards")

        export_day = datetime.now().strftime("%Y%m%d")
        export_dir = EXPORT_ROOT_DIR / f"{export_day}_backup"
        export_dir.mkdir(parents=True, exist_ok=True)
        original_id = self.store.data["header"].get("active_card_id")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        exported = 0
        errors = []

        try:
            from io import BytesIO
            for index, card in enumerate(self.store.cards(), start=1):
                self.store.data["header"]["active_card_id"] = card.get("id")
                self.load_active_card_into_editor()
                self.redraw_output()
                self.output_canvas.update_idletasks()

                safe_label = re.sub(r"[^A-Za-z0-9._-]+", "_", str(card.get("label", card.get("id", "card")))).strip("_") or "card"
                path = export_dir / f"{index:02d}_{safe_label}_{timestamp}.png"
                try:
                    ps = self.output_canvas.postscript(colormode="color")
                    img = Image.open(BytesIO(ps.encode("utf-8")))
                    img.save(path, "PNG")
                    exported += 1
                except Exception as exc:
                    errors.append(f"{card.get('label', card.get('id'))}: {exc}")

            if original_id:
                self.store.data["header"]["active_card_id"] = original_id
                self.load_active_card_into_editor()
                self.redraw_output()

            if errors:
                messagebox.showwarning("Export completed with warnings", f"Exported {exported} cards.\n\nWarnings:\n" + "\n".join(errors[:5]))
            else:
                messagebox.showinfo("Export complete", f"Exported {exported} cards to:\n{export_dir}")
            self.status_var.set(f"Exported {exported} PNG card(s)")
        except Exception as exc:
            if original_id:
                self.store.data["header"]["active_card_id"] = original_id
                self.load_active_card_into_editor()
                self.redraw_output()
            messagebox.showerror("Export failed", f"Could not export all cards:\n{exc}")

    def on_close(self) -> None:
        self.scan_active = False
        self.scan_token += 1
        self.apply_sticker_editor()
        self.apply_image_editor()
        self.apply_text_layer_editor()
        self.apply_editor_to_card_without_reschedule()
        self.remember_window_geometry()
        # Clear temporary duplicate archive before the windows close.
        # The archive exists during the session for review, then gets removed on clean shutdown.
        self.cleanup_archived_duplicate_buttstores_on_shutdown()
        self.store.save("clean-shutdown")
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()

def main() -> int:
    try:
        app = PerspectiveConsoleApp()
        app.run()
        return 0
    except Exception as exc:
        print(f"{APP_NAME} failed: {exc}")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
