from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .parser import ScriptDoc
from .outline import outline_path_for

SUPPORTED_SAVE_EXTS = {"script", "md", "txt"}


@dataclass(frozen=True)
class SaveChoice:
    label: str
    extension: str | None
    needs_dialog: bool = False


SAVE_CHOICES: dict[str, SaveChoice] = {
    "save_now": SaveChoice("SAVE NOW", None, False),
    "save_as": SaveChoice("SAVE AS", None, True),
    "save_script": SaveChoice("SAVE SCRIPT", "script", False),
    "save_marked": SaveChoice("SAVE MARKED", "md", False),
    "save_text": SaveChoice("SAVE TEXT", "txt", False),
}


def short_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(max(0, size))
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def auto_save_path(extension: str = "script", directory: str | Path = ".") -> Path:
    ext = extension.lstrip(".") or "script"
    if ext not in SUPPORTED_SAVE_EXTS:
        ext = "script"
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return Path(directory) / f"SWAR_autosave_{stamp}.{ext}"


def with_extension(path: str | Path, extension: str | None) -> Path:
    p = Path(path)
    if not extension:
        if p.suffix:
            return p
        return p.with_suffix(".script")
    return p.with_suffix("." + extension.lstrip("."))


def resolve_save_path(
    current_path: str | Path | None,
    requested_extension: str | None,
    fallback_directory: str | Path = ".",
) -> Path:
    """Resolve a non-dialog save path.

    Save Now reuses the current file path if present. Typed save actions reuse the current
    stem but force the requested extension. Untitled/cancel fallback becomes a timestamped
    SWAR_autosave file.
    """
    if current_path:
        return with_extension(current_path, requested_extension)
    ext = requested_extension or "script"
    return auto_save_path(ext, fallback_directory)


def section_for_scroll(doc: ScriptDoc | None, percent: int) -> str:
    if not doc or not doc.blocks:
        return "none"
    real_blocks = [b for b in doc.blocks if b.kind != "blank"]
    if not real_blocks:
        return doc.header_first_line[:64]
    idx = min(len(real_blocks) - 1, max(0, int((percent / 100) * len(real_blocks))))
    current = real_blocks[idx]
    section = doc.header_first_line
    for b in real_blocks[: idx + 1]:
        if b.kind in {"header", "divider", "legacy_label", "arrow_title", "arrow_descriptor", "arrow_major_explainer"}:
            section = b.text or b.attrs.get("center_text", "section") or "section"
    if current.kind == "source":
        section = "Source"
    return section[:72]


def outline_default_path(source_path: str | Path | None) -> Path:
    if source_path:
        return outline_path_for(source_path)
    return auto_save_path("txt").with_name("untitled_outline.txt")
