#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

APP_DIR="$(pwd)"
INSTALL_ROOT="$(dirname "$APP_DIR")"
DEFAULT_USER_DATA_DIR="$INSTALL_ROOT/user_data"
LEGACY_USER_DATA_DIR="$INSTALL_ROOT/_3dcp_console_user_data"
USER_DATA_DIR="${DCP3_CONSOLE_USER_DATA:-$DEFAULT_USER_DATA_DIR}"

mkdir -p "$USER_DATA_DIR/buttstores" "$USER_DATA_DIR/runtime" "$USER_DATA_DIR/deckbutts" "$USER_DATA_DIR/exports" "$USER_DATA_DIR/imported_pngs"

python3 - "$INSTALL_ROOT" "$APP_DIR" "$USER_DATA_DIR" "$LEGACY_USER_DATA_DIR" <<'PY'
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

install_root = Path(sys.argv[1])
app_dir = Path(sys.argv[2])
user_data = Path(sys.argv[3])
legacy_user_data = Path(sys.argv[4])
dest_dir = user_data / "buttstores"
runtime_dir = user_data / "runtime"
ledger_path = runtime_dir / "migration_ledger.json"
runtime_dir.mkdir(parents=True, exist_ok=True)
dest_dir.mkdir(parents=True, exist_ok=True)

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def is_valid_buttstore(path: Path) -> bool:
    try:
        return load_json(path).get("buttstore_format") == "3DCP-BUTTSTORE"
    except Exception:
        return False

if ledger_path.exists():
    try:
        ledger = load_json(ledger_path)
    except Exception:
        ledger = {}
else:
    ledger = {}

ledger.setdefault("copied_sha256", [])
ledger.setdefault("entries", [])

seen_hashes = set(ledger.get("copied_sha256", []))
for existing_path in dest_dir.glob("*.buttstore"):
    try:
        seen_hashes.add(sha256_file(existing_path))
    except Exception:
        pass

copied = 0
already = 0
skipped = 0

# Merge only the old shared user-data folder. Do NOT scan all old version folders
# by default; that was the source of repeated default_episode_migrated_N files.
if legacy_user_data.exists() and legacy_user_data.is_dir() and legacy_user_data.resolve() != user_data.resolve():
    legacy_butts = legacy_user_data / "buttstores"
    if legacy_butts.exists():
        for src in sorted(legacy_butts.glob("*.buttstore")):
            if not is_valid_buttstore(src):
                skipped += 1
                continue
            digest = sha256_file(src)
            if digest in seen_hashes:
                already += 1
                continue
            dest = dest_dir / src.name
            if dest.exists():
                n = 1
                while True:
                    candidate = dest_dir / f"{src.stem}_legacy_{n}{src.suffix}"
                    if not candidate.exists():
                        dest = candidate
                        break
                    n += 1
            shutil.copy2(src, dest)
            copied += 1
            seen_hashes.add(digest)
            ledger["copied_sha256"].append(digest)
            ledger["entries"].append({
                "sha256": digest,
                "src": str(src),
                "dest": str(dest),
                "copied_at_unix": int(time.time()),
                "mode": "legacy-user-data-merge",
            })
else:
    skipped += 1

# Optional manual recovery mode. This is intentionally off by default.
# Use only if you need to import .buttstore files from old version folders.
if os.environ.get("DCP3_IMPORT_OLD_VERSION_BUTTSTORES") == "1":
    template_parts = {"templates"}
    for src in sorted(install_root.glob("**/*.buttstore")):
        if user_data in src.parents:
            continue
        if legacy_user_data.exists() and legacy_user_data in src.parents:
            continue
        lowered = {part.lower() for part in src.parts}
        if lowered & template_parts or "template" in src.name.lower():
            skipped += 1
            continue
        if not is_valid_buttstore(src):
            skipped += 1
            continue
        digest = sha256_file(src)
        if digest in seen_hashes:
            already += 1
            continue
        dest = dest_dir / src.name
        if dest.exists():
            n = 1
            while True:
                candidate = dest_dir / f"{src.stem}_manual_{n}{src.suffix}"
                if not candidate.exists():
                    dest = candidate
                    break
                n += 1
        shutil.copy2(src, dest)
        copied += 1
        seen_hashes.add(digest)
        ledger["copied_sha256"].append(digest)
        ledger["entries"].append({
            "sha256": digest,
            "src": str(src),
            "dest": str(dest),
            "copied_at_unix": int(time.time()),
            "mode": "manual-old-version-import",
        })

ledger["updated_at_unix"] = int(time.time())
ledger_path.write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")

print(f"PASS: migration complete, copied={copied}, already_copied={already}, skipped={skipped}")
print("INFO: old version-folder imports are disabled by default")
print("INFO: to manually import old version folders, run with DCP3_IMPORT_OLD_VERSION_BUTTSTORES=1")
print(f"Shared user data: {user_data}")
PY
