from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import json


@dataclass(frozen=True)
class EmojiEntry:
    symbol: str
    label: str
    category: str = "General"
    tags: str = ""

    @property
    def search_text(self) -> str:
        return f"{self.symbol} {self.label} {self.category} {self.tags}".lower()

    @property
    def display_text(self) -> str:
        return f"{self.symbol}  {self.label}  [{self.category}]"


def default_emoji_candidates(extra_dirs: list[str | Path] | None = None) -> list[Path]:
    """Return search locations for the user-customizable current.emoji file.

    SWAR ships with a starter current.emoji beside swar.py, but the user may keep
    their active list at ~/SWAR/current.emoji so it can persist across versioned
    SWAR folders.  The first existing file wins.
    """
    here = Path(__file__).resolve()
    app_root = here.parents[1]
    candidates: list[Path] = []
    if extra_dirs:
        candidates.extend(Path(d) / "current.emoji" for d in extra_dirs)
    candidates.extend(
        [
            Path.cwd() / "current.emoji",
            app_root / "current.emoji",
            app_root.parent / "current.emoji",
            Path.home() / "SWAR" / "current.emoji",
        ]
    )
    # Keep order stable while removing duplicates.
    seen: set[Path] = set()
    out: list[Path] = []
    for path in candidates:
        try:
            key = path.resolve()
        except OSError:
            key = path
        if key not in seen:
            seen.add(key)
            out.append(path)
    return out


def load_current_emoji(extra_dirs: list[str | Path] | None = None) -> tuple[list[EmojiEntry], Path | None]:
    for path in default_emoji_candidates(extra_dirs):
        if path.exists():
            return parse_emoji_text(path.read_text(encoding="utf-8", errors="replace")), path
    return [], None


def parse_emoji_text(text: str) -> list[EmojiEntry]:
    stripped = text.strip()
    if not stripped:
        return []
    # Future-proof: accept JSON lists/dicts if a later current.emoji file becomes strict JSON.
    if stripped.startswith(("[", "{")):
        try:
            return _parse_json_emoji(json.loads(stripped))
        except Exception:
            pass
    return _parse_pipe_emoji(text)


def _parse_pipe_emoji(text: str) -> list[EmojiEntry]:
    entries: list[EmojiEntry] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        # Current starter format: ✅|Check|Status /,
        line = line.rstrip(",").strip()
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            continue
        symbol = parts[0]
        label = parts[1] or symbol
        category = parts[2] if len(parts) >= 3 else "General"
        category = category.replace("/", " ").strip() or "General"
        tags = " ".join(parts[3:]).replace("/", " ").strip() if len(parts) > 3 else ""
        if symbol:
            entries.append(EmojiEntry(symbol=symbol, label=label, category=category, tags=tags))
    return entries


def _parse_json_emoji(data) -> list[EmojiEntry]:
    entries: list[EmojiEntry] = []
    if isinstance(data, dict):
        # Accept {"Status": [{"emoji":"✅", "name":"Check"}]} or
        # {"emojis": [...]}.
        if isinstance(data.get("emojis"), list):
            return _parse_json_emoji(data["emojis"])
        for category, items in data.items():
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        symbol = str(item.get("emoji") or item.get("symbol") or "")
                        label = str(item.get("name") or item.get("label") or symbol)
                        tags = item.get("tags", "")
                        if isinstance(tags, list):
                            tags = " ".join(map(str, tags))
                        entries.append(EmojiEntry(symbol=symbol, label=label, category=str(category), tags=str(tags)))
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                symbol = str(item.get("emoji") or item.get("symbol") or "")
                label = str(item.get("name") or item.get("label") or symbol)
                category = str(item.get("category") or "General")
                tags = item.get("tags", "")
                if isinstance(tags, list):
                    tags = " ".join(map(str, tags))
                if symbol:
                    entries.append(EmojiEntry(symbol=symbol, label=label, category=category, tags=str(tags)))
            elif isinstance(item, str):
                entries.append(EmojiEntry(symbol=item, label=item, category="General"))
    return [entry for entry in entries if entry.symbol]
