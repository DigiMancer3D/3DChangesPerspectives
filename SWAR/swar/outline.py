from __future__ import annotations

from pathlib import Path
from .parser import ScriptDoc


def outline_text(doc: ScriptDoc) -> str:
    # Exact requested shape: double newline, header first line, double newline, links one per line, double newline.
    links = list(doc.source_links)
    body = "\n".join(links)
    return f"\n\n{doc.header_first_line}\n\n{body}\n\n"


def outline_path_for(path: str | Path) -> Path:
    p = Path(path)
    if not p.name:
        return Path("untitled_outline.txt")
    stem = p.stem
    lower = stem.lower()
    replacements = [
        ("_shownotes", "_outline"),
        ("shownotes", "outline"),
        ("-notes", "-outline"),
        ("-note", "-outline"),
        ("-show", "-outline"),
    ]
    for suffix, replacement in replacements:
        if lower.endswith(suffix):
            return p.with_name(stem[: -len(suffix)] + replacement + ".txt")
    return p.with_name(f"{stem}_outline.txt")


def export_outline(doc: ScriptDoc, source_path: str | Path, output_path: str | Path | None = None) -> Path:
    out = Path(output_path) if output_path else outline_path_for(source_path)
    out.write_text(outline_text(doc), encoding="utf-8")
    return out
