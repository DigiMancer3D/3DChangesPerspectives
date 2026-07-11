from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import re
from urllib.parse import urlparse, unquote, parse_qs

SECRET_KEYS = {"URL", "KEY", "CHAT TOKEN", "META", "META DATA"}
URL_RE = re.compile(r"^(?:(?:https?|ftp)://|www\.)", re.IGNORECASE)
BARE_URL_RE = re.compile(r"^\s*(?:(?:https?|ftp)://|www\.)\S+\s*$", re.IGNORECASE)
PRIVATE_URL_RE = re.compile(r"^\s*!+\s*((?:(?:https?|ftp)://|www\.)\S+)\s*!+\s*$", re.IGNORECASE)
DASH_SOURCE_RE = re.compile(r"^\s*-\s*(.*)$")
ARROW_RE = re.compile(r"^\s*(>{2,})(!!)?\s*(.*?)\s*(!!)?(<{2,})\s*$")
ARROW_START_RE = re.compile(r"^\s*(>{2,})(!!)?\s*(.*)$")
IMPORTANT_END_RE = re.compile(r"^\s*(?:!!\s*)+(!+)?(<{2,})\s*$")
BANG_NOTICE_RE = re.compile(r"^\s*!{2,}\s*(.*?)\s*!{2,}\s*$")
QUOTE_LINE_RE = re.compile(r'^\s*"(.*)"\s*$')
LEGACY_LABEL_RE = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 _/-]{1,40})\s*:\s*$")
MD_HEADING_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.+?)\s*$")
MD_TABLE_SEP_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")
DOWN_ARROW_BODY_RE = re.compile(r"^\s*(?:\|\|\s*){2,}$")
DOWN_ARROW_HEAD_RE = re.compile(r"^\s*(?:\\/\s*){2,}$")
MD_BLOCKQUOTE_RE = re.compile(r"^\s{0,3}(>{1,3})\s+(.+?)\s*$")
MD_CHECK_RE = re.compile(r"^\s*-\s*\[([ xX#\$€£¥¢]|%\d{1,3})\]\s+(.+?)\s*$")
MD_PLUS_BULLET_RE = re.compile(r"^\s*\+\s+(.+?)\s*$")
MD_DASH_LIST_RE = re.compile(r"^(?P<indent>[ \t]*)-\s+(?P<text>.+?)\s*$")
MD_NUMBERED_TAB_RE = re.compile(r"^(?P<indent>[ \t]*)-#\s+(?P<body>.+?)\s*$")
MD_ORDERED_RE = re.compile(r"^(?P<indent>[ \t]*)(?P<number>\d{1,6})[.)]\s+(?P<text>.+?)\s*$")
MD_HR_RE = re.compile(r"^\s*\*{3,}\s*$")
FENCE_OPEN_RE = re.compile(r"^\s*(?P<fence>`{3,})(?P<info>[A-Za-z0-9_.+#-]*)\s*$")
FENCE_CLOSE_RE = re.compile(r"^\s*`{3,}\s*$")
FENCE_LABEL_RE = re.compile(r"^\s*\[([^]\n]{1,48})\]\s*$")
COLOR_ESCAPE_MARKER = r"\`!"
TRAILING_HEX_COLOR_RE = re.compile(r"^(?P<body>.*?)(?P<token>\[(?P<color>#[0-9A-Fa-f]{3,8})\])\s*$")
TRAILING_RGB_COLOR_RE = re.compile(r"^(?P<body>.*?)(?P<token>\((?P<color>rgba?\([^()\n]*\))\))\s*$", re.IGNORECASE)
ESCAPED_TRAILING_COLOR_RE = re.compile(
    r"^(?P<body>.*?)\\`!\s*(?P<token>\[(?P<hex>#[0-9A-Fa-f]{3,8})\]|\((?P<rgb>rgba?\([^()\n]*\))\))\s*$",
    re.IGNORECASE,
)


def _trim_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return (f"{value:.4f}").rstrip("0").rstrip(".")


def _normalize_rgb_function(value: str) -> str | None:
    match = re.fullmatch(r"(?i)(rgb|rgba)\(\s*(.*?)\s*\)", value or "")
    if not match:
        return None
    name = match.group(1).lower()
    body = match.group(2).strip()
    if not body:
        return None
    if "," in body:
        parts = [part.strip() for part in body.split(",")]
    else:
        parts = [part for part in body.replace("/", " ").split() if part]
    if name == "rgb" and len(parts) not in {3, 4}:
        return None
    if name == "rgba" and len(parts) != 4:
        return None

    channels: list[str] = []
    for raw_channel in parts[:3]:
        try:
            if raw_channel.endswith("%"):
                amount = float(raw_channel[:-1])
                if not 0 <= amount <= 100:
                    return None
                channels.append(_trim_number(amount) + "%")
            else:
                amount = float(raw_channel)
                if not 0 <= amount <= 255:
                    return None
                channels.append(_trim_number(amount))
        except ValueError:
            return None

    if len(parts) == 4:
        raw_alpha = parts[3]
        try:
            if raw_alpha.endswith("%"):
                alpha = float(raw_alpha[:-1])
                if not 0 <= alpha <= 100:
                    return None
                alpha_text = _trim_number(alpha) + "%"
            else:
                alpha = float(raw_alpha)
                if not 0 <= alpha <= 1:
                    return None
                alpha_text = _trim_number(alpha)
        except ValueError:
            return None
        return f"rgba({', '.join(channels)}, {alpha_text})"
    return f"rgb({', '.join(channels)})"


def _normalize_color_profile(value: str) -> str | None:
    value = str(value or "").strip()
    if value.startswith("#"):
        digits = value[1:]
        if len(digits) in {3, 4, 6, 8} and re.fullmatch(r"[0-9A-Fa-f]+", digits):
            return "#" + digits.lower()
        return None
    return _normalize_rgb_function(value)


def _extract_trailing_color_profile(raw: str) -> tuple[str, str | None, bool]:
    """Extract an optional trailing color without changing ordinary lines.

    Active suffixes are removed and returned as a normalized profile. The
    ``\\`!`` escape removes only itself and leaves the valid color-looking token
    visible as literal reader text.
    """
    escaped = ESCAPED_TRAILING_COLOR_RE.match(raw)
    if escaped:
        candidate = escaped.group("hex") or escaped.group("rgb") or ""
        if _normalize_color_profile(candidate):
            return escaped.group("body") + escaped.group("token"), None, True

    for pattern in (TRAILING_HEX_COLOR_RE, TRAILING_RGB_COLOR_RE):
        match = pattern.match(raw)
        if not match:
            continue
        body = match.group("body")
        color = _normalize_color_profile(match.group("color"))
        if color and body.strip():
            return body.rstrip(), color, False
    return raw, None, False


def _put_color(attrs: dict[str, Any], color: str | None) -> dict[str, Any]:
    if color:
        attrs["color_profile"] = color
    return attrs


@dataclass
class Block:
    kind: str
    text: str
    line_start: int
    line_end: int
    raw: str = ""
    indent: int = 0
    level: int = 0
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScriptDoc:
    path: str = ""
    blocks: list[Block] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def header_first_line(self) -> str:
        for b in self.blocks:
            if b.kind == "header":
                return b.text.strip()
        for b in self.blocks:
            if b.text.strip():
                return b.text.strip()
        return "Untitled SWAR Script"

    @property
    def source_links(self) -> list[str]:
        links: list[str] = []
        for b in self.blocks:
            if b.kind == "source" and b.attrs.get("is_url") and not b.attrs.get("private"):
                url = normalize_url(b.attrs.get("url", b.text.strip()))
                scheme = urlparse(url).scheme
                if scheme in {"http", "https"}:
                    links.append(url)
        return links

    @property
    def section_count(self) -> int:
        return sum(1 for b in self.blocks if b.kind in {"divider", "arrow_title", "legacy_label", "arrow_major_explainer"})


class SwarParser:
    """Forgiving parser for 3DCP SWAR Script Markup, Markdown, and legacy TXT scripts."""

    def parse_file(self, path: str | Path) -> ScriptDoc:
        path = Path(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        return self.parse(text, path=str(path))

    def parse(self, text: str, path: str = "") -> ScriptDoc:
        doc = ScriptDoc(path=path)
        lines = text.splitlines()
        found_header = False
        in_important: dict[str, Any] | None = None
        in_fence: dict[str, Any] | None = None
        numbered_counters: dict[int, int] = {}
        table_buffer: list[tuple[int, str, str, str | None]] = []
        pending_empty_source_index: int | None = None
        pending_down_arrow_count: int | None = None
        pending_down_arrow_color: str | None = None
        percent_buffer: list[tuple[int, str, str, int, str, int, str | None]] = []
        active_line_color: str | None = None

        def flush_table() -> None:
            nonlocal table_buffer
            if table_buffer:
                start = table_buffer[0][0]
                end = table_buffer[-1][0]
                display_raw = "\n".join(t[1] for t in table_buffer)
                original_raw = "\n".join(t[2] for t in table_buffer)
                row_colors = [t[3] for t in table_buffer]
                attrs: dict[str, Any] = {}
                if any(row_colors):
                    attrs["row_colors"] = row_colors
                    # A profile on the final table line acts as the trailing
                    # profile for the complete table object.
                    if row_colors[-1]:
                        attrs["color_profile"] = row_colors[-1]
                doc.blocks.append(Block("markdown_table", display_raw, start, end, raw=original_raw, indent=0, level=0, attrs=attrs))
                table_buffer = []

        def flush_percent_list() -> None:
            nonlocal percent_buffer
            if percent_buffer:
                start = percent_buffer[0][0]
                end = percent_buffer[-1][0]
                display_raw = "\n".join(t[1] for t in percent_buffer)
                original_raw = "\n".join(t[2] for t in percent_buffer)
                items = []
                for item in percent_buffer:
                    entry = {"percent": item[3], "text": item[4]}
                    if item[6]:
                        entry["color_profile"] = item[6]
                    items.append(entry)
                indent0 = percent_buffer[0][5]
                attrs: dict[str, Any] = {"items": items}
                if percent_buffer[-1][6]:
                    attrs["color_profile"] = percent_buffer[-1][6]
                doc.blocks.append(Block("markdown_percent_list", display_raw, start, end, raw=original_raw, indent=indent0, level=_level_from_indent(indent0), attrs=attrs))
                percent_buffer = []

        def clear_pending_if_real_block(kind: str) -> None:
            nonlocal pending_empty_source_index
            if kind not in {"blank"}:
                pending_empty_source_index = None

        def append_block(block: Block, color_profile: str | None | object = ...) -> None:
            profile = active_line_color if color_profile is ... else color_profile
            if isinstance(profile, str) and profile:
                block.attrs["color_profile"] = profile
            doc.blocks.append(block)
            clear_pending_if_real_block(block.kind)

        def flush_pending_down_arrow(before_line: int | None = None) -> None:
            nonlocal pending_down_arrow_count, pending_down_arrow_color
            if pending_down_arrow_count is not None:
                ln = before_line if before_line is not None else 0
                attrs = {"count": pending_down_arrow_count}
                _put_color(attrs, pending_down_arrow_color)
                doc.blocks.append(Block(
                    "down_arrows", "⬇ " * pending_down_arrow_count, ln, ln,
                    raw="|| \\/", indent=0, level=0, attrs=attrs
                ))
                pending_down_arrow_count = None
                pending_down_arrow_color = None

        def absorb_pending_source(source_attrs: dict[str, Any], idx: int, raw: str, indent: int, color_profile: str | None = None) -> bool:
            nonlocal pending_empty_source_index
            if pending_empty_source_index is None:
                return False
            if pending_empty_source_index < 0 or pending_empty_source_index >= len(doc.blocks):
                pending_empty_source_index = None
                return False
            prev = doc.blocks[pending_empty_source_index]
            if prev.kind != "source" or not prev.attrs.get("is_empty"):
                pending_empty_source_index = None
                return False
            prev.text = source_attrs["display"]
            prev.line_end = idx
            prev.raw = (prev.raw + "\n" + raw).strip("\n")
            prev.indent = min(prev.indent, indent)
            prev.level = _level_from_indent(prev.indent)
            old_color = prev.attrs.get("color_profile")
            prev.attrs = source_attrs | {"split_dash_source": True, "dash_line": prev.line_start, "target_line": idx}
            _put_color(prev.attrs, color_profile or old_color)
            pending_empty_source_index = None
            return True

        def finish_fence(
            end_line: int,
            closing_raw: str | None = None,
            *,
            closing_color: str | None = None,
            unclosed: bool = False,
        ) -> None:
            nonlocal in_fence
            if in_fence is None:
                return
            display_lines = list(in_fence["lines"])
            line_colors = list(in_fence.get("line_colors", []))
            box_label = ""
            for pos, value in enumerate(display_lines):
                if not value.strip():
                    continue
                label_match = FENCE_LABEL_RE.match(value)
                if label_match:
                    box_label = label_match.group(1).strip()
                    del display_lines[pos]
                    if pos < len(line_colors):
                        del line_colors[pos]
                break
            raw_lines = list(in_fence["raw"])
            if closing_raw is not None:
                raw_lines.append(closing_raw)
            attrs = {
                "fence_info": str(in_fence.get("info") or "CODE"),
                "fence_marker": str(in_fence.get("marker") or "```"),
                "box_label": box_label,
                "unclosed": bool(unclosed),
            }
            object_color = closing_color or in_fence.get("color_profile")
            _put_color(attrs, object_color)
            if any(line_colors):
                attrs["line_colors"] = line_colors
            append_block(Block(
                "markdown_fenced_box",
                "\n".join(display_lines),
                in_fence["start_line"],
                end_line,
                raw="\n".join(raw_lines),
                indent=in_fence["indent"],
                level=_level_from_indent(in_fence["indent"]),
                attrs=attrs,
            ), color_profile=None)
            in_fence = None

        def clear_numbered_counters() -> None:
            numbered_counters.clear()

        def next_numbered_marker(level: int, body: str) -> tuple[int, str]:
            explicit = re.match(r"^(\d{1,6})(?:[.)])?\s+(.+)$", body)
            if explicit:
                value = max(0, min(999999, int(explicit.group(1))))
                text_value = explicit.group(2).strip()
            else:
                value = numbered_counters.get(level, 0)
                text_value = body.strip()
            numbered_counters[level] = min(1000000, value + 1)
            for key in list(numbered_counters):
                if key > level:
                    numbered_counters.pop(key, None)
            return value, text_value

        for idx, line in enumerate(lines, start=1):
            original_raw = line.rstrip("\n")
            raw, active_line_color, _color_escaped = _extract_trailing_color_profile(original_raw)
            stripped = raw.strip()
            indent = len(raw) - len(raw.lstrip(" \t"))

            if in_fence is not None:
                if FENCE_CLOSE_RE.match(raw):
                    finish_fence(idx, original_raw, closing_color=active_line_color)
                else:
                    in_fence["lines"].append(raw)
                    in_fence["line_colors"].append(active_line_color)
                    in_fence["raw"].append(original_raw)
                continue

            fence_match = FENCE_OPEN_RE.match(raw)
            if fence_match:
                flush_percent_list()
                flush_table()
                flush_pending_down_arrow(idx)
                in_fence = {
                    "start_line": idx,
                    "indent": indent,
                    "marker": fence_match.group("fence"),
                    "info": fence_match.group("info") or "CODE",
                    "lines": [],
                    "line_colors": [],
                    "color_profile": active_line_color,
                    "raw": [original_raw],
                }
                pending_empty_source_index = None
                clear_numbered_counters()
                continue

            if in_important is None:
                if DOWN_ARROW_BODY_RE.match(stripped):
                    pending_down_arrow_count = max(2, stripped.count("||"))
                    pending_down_arrow_color = active_line_color
                    continue
                if DOWN_ARROW_HEAD_RE.match(stripped):
                    count = max(pending_down_arrow_count or 0, stripped.count("\\/"))
                    if count <= 0:
                        count = 2
                    arrow_color = active_line_color or pending_down_arrow_color
                    append_block(Block("down_arrows", "⬇ " * count, idx, idx, raw=original_raw, indent=indent, level=_level_from_indent(indent), attrs={"count": count}), color_profile=arrow_color)
                    pending_down_arrow_count = None
                    pending_down_arrow_color = None
                    continue
                elif pending_down_arrow_count is not None and stripped:
                    flush_pending_down_arrow(idx)

            if in_important is not None:
                if IMPORTANT_END_RE.match(stripped):
                    start_arrows = in_important.get("arrows", ">>")
                    body = "\n".join(in_important["lines"])
                    attrs = {"arrow_count": len(start_arrows), "end_arrows": "<" * len(start_arrows)}
                    _put_color(attrs, active_line_color or in_important.get("color_profile"))
                    line_colors = list(in_important.get("line_colors", []))
                    if any(line_colors):
                        attrs["line_colors"] = line_colors
                    append_block(Block(
                        kind="important",
                        text=body,
                        line_start=in_important["start_line"],
                        line_end=idx,
                        raw="\n".join(in_important["raw"] + [original_raw]),
                        indent=in_important["indent"],
                        level=_level_from_indent(in_important["indent"]),
                        attrs=attrs,
                    ), color_profile=None)
                    in_important = None
                else:
                    in_important["lines"].append(raw)
                    in_important["line_colors"].append(active_line_color)
                    in_important["raw"].append(original_raw)
                continue

            # Percent list items are buffered so the reader can color best/worst items as a group.
            pct_match = MD_CHECK_RE.match(raw)
            if pct_match and pct_match.group(1).startswith("%"):
                flush_table()
                pct_value = int(pct_match.group(1)[1:])
                percent_buffer.append((idx, raw, original_raw, pct_value, pct_match.group(2).strip(), indent, active_line_color))
                continue
            else:
                flush_percent_list()

            if _maybe_table_line(stripped):
                flush_percent_list()
                table_buffer.append((idx, raw, original_raw, active_line_color))
                continue
            else:
                flush_table()

            if not stripped:
                clear_numbered_counters()
                doc.blocks.append(Block("blank", "", idx, idx, raw=original_raw, indent=indent, level=_level_from_indent(indent)))
                continue

            # A previous '-' empty source marker can be completed by a URL/path on the next nonblank line.
            private_url_match = PRIVATE_URL_RE.match(raw)
            if private_url_match:
                source_attrs = _source_attrs_from_target(private_url_match.group(1), private=True)
                if absorb_pending_source(source_attrs, idx, original_raw, indent, active_line_color):
                    continue
                append_block(Block("source", source_attrs["display"], idx, idx, raw=raw, indent=indent, level=_level_from_indent(indent), attrs=source_attrs))
                continue

            if pending_empty_source_index is not None and BARE_URL_RE.match(raw):
                source_attrs = _source_attrs_from_target(stripped)
                if absorb_pending_source(source_attrs, idx, original_raw, indent, active_line_color):
                    continue

            secret = _parse_secret(stripped)
            if secret:
                key, value = secret
                append_block(Block("meta_secret", value, idx, idx, raw=raw, indent=indent, level=0, attrs={"key": key, "masked": True}))
                continue

            if not found_header and _looks_like_header(stripped):
                found_header = True
                append_block(Block("header", stripped, idx, idx, raw=raw, indent=indent, level=0))
                continue

            if stripped.startswith(">>") and "!!" in stripped and not re.search(r"<{2,}\s*$", stripped):
                start_match = ARROW_START_RE.match(stripped)
                arrow_text = start_match.group(1) if start_match else ">>"
                in_important = {
                    "start_line": idx,
                    "indent": indent,
                    "arrows": arrow_text,
                    "lines": [],
                    "line_colors": [],
                    "color_profile": active_line_color,
                    "raw": [original_raw],
                }
                after = stripped.replace(arrow_text, "", 1).replace("!!", "", 1).strip()
                if after:
                    in_important["lines"].append(after)
                pending_empty_source_index = None
                continue

            div = _parse_divider(stripped)
            if div is not None:
                clear_numbered_counters()
                append_block(Block("divider", div, idx, idx, raw=raw, indent=indent, level=0, attrs={"center_text": div}))
                continue

            if MD_HR_RE.match(raw):
                clear_numbered_counters()
                append_block(Block("markdown_hr", "", idx, idx, raw=raw, indent=indent, level=_level_from_indent(indent)))
                continue

            bang = BANG_NOTICE_RE.match(stripped)
            if bang:
                append_block(Block("bang_notice", bang.group(1).strip(), idx, idx, raw=raw, indent=indent, level=_level_from_indent(indent)))
                continue

            md_quote = MD_BLOCKQUOTE_RE.match(raw)
            if md_quote and "<<" not in stripped:
                quote_level = len(md_quote.group(1))
                append_block(Block("markdown_blockquote", md_quote.group(2).strip(), idx, idx, raw=raw, indent=indent, level=_level_from_indent(indent) + quote_level, attrs={"quote_level": quote_level}))
                continue

            numbered_tab = MD_NUMBERED_TAB_RE.match(raw)
            if numbered_tab:
                level = _level_from_indent(indent)
                marker_value, item_text = next_numbered_marker(level, numbered_tab.group("body"))
                append_block(Block(
                    "markdown_numbered_tab", item_text, idx, idx, raw=raw, indent=indent, level=level,
                    attrs={"marker": marker_value, "list_level": level},
                ))
                continue

            md_check = MD_CHECK_RE.match(raw)
            if md_check:
                marker = md_check.group(1)
                item_text = md_check.group(2).strip()
                if marker.lower() in {" ", "x"}:
                    kind = "markdown_check_item"
                elif marker == "#":
                    kind = "markdown_num_item"
                elif marker in {"$", "€", "£", "¥", "¢"}:
                    kind = "markdown_money_item"
                else:
                    kind = "markdown_check_item"
                append_block(Block(
                    kind, item_text, idx, idx, raw=raw, indent=indent, level=_level_from_indent(indent),
                    attrs={"marker": marker, "checked": marker.lower() == "x"},
                ))
                continue

            ordered_item = MD_ORDERED_RE.match(raw)
            if ordered_item:
                level = _level_from_indent(indent)
                append_block(Block(
                    "markdown_ordered_item", ordered_item.group("text").strip(), idx, idx,
                    raw=raw, indent=indent, level=level,
                    attrs={"marker": int(ordered_item.group("number")), "list_level": level},
                ))
                continue

            plus_bullet = MD_PLUS_BULLET_RE.match(raw)
            if plus_bullet:
                append_block(Block("markdown_bullet_item", plus_bullet.group(1).strip(), idx, idx, raw=raw, indent=indent, level=_level_from_indent(indent)))
                continue

            source = _parse_source(raw)
            if source:
                block = Block("source", source["display"], idx, idx, raw=original_raw, indent=indent, level=_level_from_indent(indent), attrs=source)
                append_block(block)
                if source.get("is_empty"):
                    pending_empty_source_index = len(doc.blocks) - 1
                else:
                    pending_empty_source_index = None
                continue

            dash_item = MD_DASH_LIST_RE.match(raw)
            if dash_item:
                append_block(Block(
                    "markdown_dash_item", dash_item.group("text").strip(), idx, idx,
                    raw=raw, indent=indent, level=_level_from_indent(indent),
                    attrs={"list_level": _level_from_indent(indent)},
                ))
                continue

            # A bare URL without '-' is still a source when it appears as its own line.
            if BARE_URL_RE.match(raw):
                source_attrs = _source_attrs_from_target(stripped)
                append_block(Block("source", source_attrs["display"], idx, idx, raw=raw, indent=indent, level=_level_from_indent(indent), attrs=source_attrs | {"bare_source": True}))
                continue

            # A pending '-' followed by a plausible local path should become a split local source.
            if pending_empty_source_index is not None and _looks_like_local_path(stripped):
                source_attrs = _source_attrs_from_target(stripped)
                if absorb_pending_source(source_attrs, idx, original_raw, indent, active_line_color):
                    continue

            arrow = _parse_arrow(stripped)
            if arrow:
                kind = arrow["kind"]
                append_block(Block(kind, arrow["text"], idx, idx, raw=raw, indent=indent, level=_arrow_level(indent, arrow["arrow_count"]), attrs=arrow))
                continue

            md_heading = MD_HEADING_RE.match(raw)
            if md_heading:
                append_block(Block("markdown_heading", md_heading.group(2).strip(), idx, idx, raw=raw, indent=indent, level=len(md_heading.group(1)), attrs={"heading_level": len(md_heading.group(1))}))
                continue

            quote = QUOTE_LINE_RE.match(raw)
            if quote:
                append_block(Block("spoken", quote.group(1), idx, idx, raw=raw, indent=indent, level=_level_from_indent(indent)))
                continue

            legacy = LEGACY_LABEL_RE.match(raw)
            if legacy and legacy.group(1).strip().lower() not in {"url", "key"}:
                append_block(Block("legacy_label", legacy.group(1).strip(), idx, idx, raw=raw, indent=indent, level=_level_from_indent(indent)))
                continue

            append_block(Block("plain", raw, idx, idx, raw=raw, indent=indent, level=_level_from_indent(indent)))

        flush_percent_list()
        flush_table()
        flush_pending_down_arrow(len(lines))
        if in_fence is not None:
            doc.warnings.append(f"Fenced box opened at line {in_fence['start_line']} did not have a closing ``` line.")
            finish_fence(len(lines), unclosed=True)
        if in_important is not None:
            doc.warnings.append(f"Important block opened at line {in_important['start_line']} did not have a closing !!<< line.")
            body = "\n".join(in_important["lines"])
            attrs = {"arrow_count": len(in_important.get("arrows", ">>")), "unclosed": True}
            _put_color(attrs, in_important.get("color_profile"))
            line_colors = list(in_important.get("line_colors", []))
            if any(line_colors):
                attrs["line_colors"] = line_colors
            doc.blocks.append(Block(
                "important", body, in_important["start_line"], len(lines), raw="\n".join(in_important["raw"]),
                indent=in_important["indent"], level=_level_from_indent(in_important["indent"]),
                attrs=attrs,
            ))
        doc.blocks = _collapse_extended_blank_runs(doc.blocks)
        return doc


def _collapse_extended_blank_runs(blocks: list[Block]) -> list[Block]:
    """Collapse 3+ blank rows into one semantic paragraph separator.

    One or two blank rows retain legacy spacing. Longer runs become a single
    lightweight block, reducing generated HTML while making deliberate large
    paragraph breaks visible in Reader mode.
    """
    out: list[Block] = []
    index = 0
    while index < len(blocks):
        block = blocks[index]
        if block.kind != "blank":
            out.append(block)
            index += 1
            continue

        end = index + 1
        while end < len(blocks) and blocks[end].kind == "blank":
            end += 1
        run = blocks[index:end]
        if len(run) >= 3:
            out.append(Block(
                "markdown_paragraph_gap",
                "",
                run[0].line_start,
                run[-1].line_end,
                raw="\n".join(item.raw for item in run),
                indent=run[0].indent,
                level=run[0].level,
                attrs={"blank_count": len(run)},
            ))
        else:
            out.extend(run)
        index = end
    return out


def _looks_like_header(text: str) -> bool:
    return "::" in text and len(text) < 240


def _parse_secret(text: str) -> tuple[str, str] | None:
    if ":" not in text:
        return None
    key, value = text.split(":", 1)
    key_norm = key.strip().upper()
    if key_norm in SECRET_KEYS:
        return key_norm, value.strip()
    return None


def _parse_divider(text: str) -> str | None:
    if re.fullmatch(r"-{3,}", text):
        return ""
    m = re.match(r"^-{3,}\s*(.*?)\s*-{3,}$", text)
    if m:
        return m.group(1).strip()
    return None


def _parse_source(raw: str) -> dict[str, Any] | None:
    """Parse only real URL/path sources; ordinary '- text' remains a Markdown list item."""
    m = DASH_SOURCE_RE.match(raw)
    if not m:
        return None
    target = m.group(1).strip()
    if not target:
        return {"target": "", "display": "empty source slot", "is_url": False, "is_empty": True}
    attrs = _source_attrs_from_target(target)
    if attrs.get("is_url") or _looks_like_dash_source_target(target):
        return attrs
    return None


def _source_attrs_from_target(target: str, private: bool = False) -> dict[str, Any]:
    target = target.strip()
    normalized = normalize_url(target)
    parsed = urlparse(normalized)
    is_url = bool(parsed.scheme and parsed.netloc) or URL_RE.match(target) is not None
    if is_url:
        meta = describe_url(target)
        meta.update({
            "target": target,
            "url": normalized,
            "display": target,
            "is_url": True,
            "is_local": False,
            "private": private,
        })
        if private:
            meta["display"] = "PRIVATE LINK: ******"
        return meta
    return {"target": target, "display": local_display(target), "is_url": False, "is_local": True, "private": private}


def _parse_arrow(text: str) -> dict[str, Any] | None:
    m = ARROW_RE.match(text)
    if not m:
        return None
    opens, open_important, content, close_important, closes = m.groups()
    arrow_count = len(opens)
    close_count = len(closes)
    kind = arrow_kind(arrow_count)
    display_text = content.strip()
    important = bool(open_important or close_important or display_text.startswith("!") or display_text.endswith("!"))
    display_text = _arrow_caps(display_text)
    return {
        "kind": kind,
        "text": display_text,
        "arrow_count": arrow_count,
        "close_count": close_count,
        "balanced": arrow_count == close_count,
        "important": important,
        "center": arrow_count in {4, 5} or arrow_count >= 7,
    }


def _arrow_caps(text: str) -> str:
    # Arrow prose remains uppercase, but inline-code spans and full Markdown links
    # retain their typed case so URLs and literal examples are never corrupted.
    if not text:
        return text
    protected: list[str] = []

    def hold(match: re.Match[str]) -> str:
        protected.append(match.group(0))
        return f"@@SWAR_PROTECTED_{len(protected) - 1}@@"

    staged = re.sub(r"`[^`\n]*`|\[[^]\n]+\]\([^\n)]+\)", hold, text)
    pieces = re.split(r"(![^!]+!)", staged)
    out = []
    for piece in pieces:
        if len(piece) >= 2 and piece.startswith("!") and piece.endswith("!"):
            out.append(piece[1:-1])
        else:
            out.append(piece.upper())
    result = "".join(out).strip()
    for index, value in enumerate(protected):
        result = result.replace(f"@@SWAR_PROTECTED_{index}@@", value)
    return result


def arrow_kind(count: int) -> str:
    if count == 2:
        return "arrow_data"
    if count == 3:
        return "arrow_verbatim"
    if count == 4:
        return "arrow_title"
    if count == 5:
        return "arrow_descriptor"
    if count == 6:
        return "arrow_explainer"
    return "arrow_major_explainer"


def _level_from_indent(indent: int) -> int:
    return max(0, indent // 2)


def _arrow_level(indent: int, arrow_count: int) -> int:
    base = _level_from_indent(indent)
    if arrow_count in {4, 5} or arrow_count >= 7:
        return max(0, base - 1)
    if arrow_count in {2, 3}:
        return base + 1
    if arrow_count == 6:
        return base + 2
    return base


def _maybe_table_line(text: str) -> bool:
    if not text:
        return False
    if "|" not in text:
        return False
    # Count only unescaped pipes. A line containing \| should pass the pipe
    # through as literal text rather than becoming or splitting a table.
    visible_pipes = len(re.findall(r"(?<!\\)\|", text))
    return visible_pipes >= 2 or bool(MD_TABLE_SEP_RE.match(text))


def normalize_url(url: str) -> str:
    if url.lower().startswith("www."):
        return "https://" + url
    return url


def describe_url(url: str) -> dict[str, str]:
    parsed = urlparse(normalize_url(url))
    host = parsed.netloc or "unknown-host"
    host_no_port = host.split(":", 1)[0]
    bits = [b for b in host_no_port.split(".") if b]
    tld = bits[-1] if len(bits) >= 2 else ""
    # The reader already shows TLD separately, so HOST deliberately drops the final TLD.
    host_display = ".".join(bits[:-1]) if len(bits) >= 2 else host_no_port
    page = ""
    query = parse_qs(parsed.query)
    if "q" in query and query["q"]:
        page = query["q"][0]
    elif parsed.path and parsed.path != "/":
        page = Path(unquote(parsed.path.rstrip("/"))).name or parsed.path.strip("/")
    else:
        page = host_display or host_no_port
    return {"tld": tld, "host": host_display or host_no_port, "page": page}


def local_display(path_text: str) -> str:
    clean = path_text.strip().rstrip()
    if not clean:
        return "../"
    p = clean.replace("\\", "/")
    if p.endswith("/"):
        parts = [x for x in p.split("/") if x]
        return f"../{parts[-1]}/" if parts else "../"
    return f"../{Path(p).name}"


def _looks_like_dash_source_target(text: str) -> bool:
    """Conservative dash-source test so prose ending in a filename stays a list."""
    value = (text or "").strip()
    if not value or value.startswith(('"', "'", ">", "<")):
        return False
    if value.startswith(("./", "../", "/", "~/", "file://")):
        return True
    if re.match(r"^[A-Za-z]:[\\/]", value):
        return True
    if "/" in value or "\\" in value:
        return True
    if not re.search(r"\s", value) and re.search(r"\.[A-Za-z0-9]{1,8}$", value):
        return True
    return False


def _looks_like_local_path(text: str) -> bool:
    if not text or text.startswith(('"', "'", ">", "<")):
        return False
    if any(sep in text for sep in ("/", "\\")):
        return True
    return bool(re.search(r"\.[A-Za-z0-9]{1,8}$", text))
