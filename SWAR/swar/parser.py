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
        table_buffer: list[tuple[int, str]] = []
        pending_empty_source_index: int | None = None
        pending_down_arrow_count: int | None = None
        percent_buffer: list[tuple[int, str, int, str, int]] = []

        def flush_table() -> None:
            nonlocal table_buffer
            if table_buffer:
                start = table_buffer[0][0]
                end = table_buffer[-1][0]
                raw = "\n".join(t[1] for t in table_buffer)
                doc.blocks.append(Block("markdown_table", raw, start, end, raw=raw, indent=0, level=0))
                table_buffer = []

        def flush_percent_list() -> None:
            nonlocal percent_buffer
            if percent_buffer:
                start = percent_buffer[0][0]
                end = percent_buffer[-1][0]
                raw = "\n".join(t[1] for t in percent_buffer)
                items = [{"percent": t[2], "text": t[3]} for t in percent_buffer]
                indent0 = percent_buffer[0][4]
                doc.blocks.append(Block("markdown_percent_list", raw, start, end, raw=raw, indent=indent0, level=_level_from_indent(indent0), attrs={"items": items}))
                percent_buffer = []

        def clear_pending_if_real_block(kind: str) -> None:
            nonlocal pending_empty_source_index
            if kind not in {"blank"}:
                pending_empty_source_index = None

        def append_block(block: Block) -> None:
            doc.blocks.append(block)
            clear_pending_if_real_block(block.kind)

        def flush_pending_down_arrow(before_line: int | None = None) -> None:
            nonlocal pending_down_arrow_count
            if pending_down_arrow_count is not None:
                ln = before_line if before_line is not None else 0
                doc.blocks.append(Block(
                    "down_arrows", "⬇ " * pending_down_arrow_count, ln, ln,
                    raw="|| \\/", indent=0, level=0, attrs={"count": pending_down_arrow_count}
                ))
                pending_down_arrow_count = None

        def absorb_pending_source(source_attrs: dict[str, Any], idx: int, raw: str, indent: int) -> bool:
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
            prev.attrs = source_attrs | {"split_dash_source": True, "dash_line": prev.line_start, "target_line": idx}
            pending_empty_source_index = None
            return True

        for idx, line in enumerate(lines, start=1):
            raw = line.rstrip("\n")
            stripped = raw.strip()
            indent = len(raw) - len(raw.lstrip(" \t"))

            if in_important is None:
                if DOWN_ARROW_BODY_RE.match(stripped):
                    pending_down_arrow_count = max(2, stripped.count("||"))
                    continue
                if DOWN_ARROW_HEAD_RE.match(stripped):
                    count = max(pending_down_arrow_count or 0, stripped.count("\\/"))
                    if count <= 0:
                        count = 2
                    append_block(Block("down_arrows", "⬇ " * count, idx, idx, raw=raw, indent=indent, level=_level_from_indent(indent), attrs={"count": count}))
                    pending_down_arrow_count = None
                    continue
                elif pending_down_arrow_count is not None and stripped:
                    flush_pending_down_arrow(idx)

            if in_important is not None:
                if IMPORTANT_END_RE.match(stripped):
                    start_arrows = in_important.get("arrows", ">>")
                    body = "\n".join(in_important["lines"])
                    append_block(Block(
                        kind="important",
                        text=body,
                        line_start=in_important["start_line"],
                        line_end=idx,
                        raw="\n".join(in_important["raw"] + [raw]),
                        indent=in_important["indent"],
                        level=_level_from_indent(in_important["indent"]),
                        attrs={"arrow_count": len(start_arrows), "end_arrows": "<" * len(start_arrows)},
                    ))
                    in_important = None
                else:
                    in_important["lines"].append(raw)
                    in_important["raw"].append(raw)
                continue

            # Percent list items are buffered so the reader can color best/worst items as a group.
            pct_match = MD_CHECK_RE.match(raw)
            if pct_match and pct_match.group(1).startswith("%"):
                flush_table()
                pct_value = int(pct_match.group(1)[1:])
                percent_buffer.append((idx, raw, pct_value, pct_match.group(2).strip(), indent))
                continue
            else:
                flush_percent_list()

            if _maybe_table_line(stripped):
                flush_percent_list()
                table_buffer.append((idx, raw))
                continue
            else:
                flush_table()

            if not stripped:
                doc.blocks.append(Block("blank", "", idx, idx, raw=raw, indent=indent, level=_level_from_indent(indent)))
                continue

            # A previous '-' empty source marker can be completed by a URL/path on the next nonblank line.
            private_url_match = PRIVATE_URL_RE.match(raw)
            if private_url_match:
                source_attrs = _source_attrs_from_target(private_url_match.group(1), private=True)
                if absorb_pending_source(source_attrs, idx, raw, indent):
                    continue
                append_block(Block("source", source_attrs["display"], idx, idx, raw=raw, indent=indent, level=_level_from_indent(indent), attrs=source_attrs))
                continue

            if pending_empty_source_index is not None and BARE_URL_RE.match(raw):
                source_attrs = _source_attrs_from_target(stripped)
                if absorb_pending_source(source_attrs, idx, raw, indent):
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
                    "raw": [raw],
                }
                after = stripped.replace(arrow_text, "", 1).replace("!!", "", 1).strip()
                if after:
                    in_important["lines"].append(after)
                pending_empty_source_index = None
                continue

            div = _parse_divider(stripped)
            if div is not None:
                append_block(Block("divider", div, idx, idx, raw=raw, indent=indent, level=0, attrs={"center_text": div}))
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
                append_block(Block(kind, item_text, idx, idx, raw=raw, indent=indent, level=_level_from_indent(indent), attrs={"marker": marker}))
                continue

            plus_bullet = MD_PLUS_BULLET_RE.match(raw)
            if plus_bullet:
                append_block(Block("markdown_bullet_item", plus_bullet.group(1).strip(), idx, idx, raw=raw, indent=indent, level=_level_from_indent(indent)))
                continue

            source = _parse_source(raw)
            if source:
                block = Block("source", source["display"], idx, idx, raw=raw, indent=indent, level=_level_from_indent(indent), attrs=source)
                doc.blocks.append(block)
                if source.get("is_empty"):
                    pending_empty_source_index = len(doc.blocks) - 1
                else:
                    pending_empty_source_index = None
                continue

            # A bare URL without '-' is still a source when it appears as its own line.
            if BARE_URL_RE.match(raw):
                source_attrs = _source_attrs_from_target(stripped)
                append_block(Block("source", source_attrs["display"], idx, idx, raw=raw, indent=indent, level=_level_from_indent(indent), attrs=source_attrs | {"bare_source": True}))
                continue

            # A pending '-' followed by a plausible local path should become a split local source.
            if pending_empty_source_index is not None and _looks_like_local_path(stripped):
                source_attrs = _source_attrs_from_target(stripped)
                if absorb_pending_source(source_attrs, idx, raw, indent):
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
        if in_important is not None:
            doc.warnings.append(f"Important block opened at line {in_important['start_line']} did not have a closing !!<< line.")
            body = "\n".join(in_important["lines"])
            doc.blocks.append(Block(
                "important", body, in_important["start_line"], len(lines), raw="\n".join(in_important["raw"]),
                indent=in_important["indent"], level=_level_from_indent(in_important["indent"]),
                attrs={"arrow_count": len(in_important.get("arrows", ">>")), "unclosed": True},
            ))
        return doc


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
    m = DASH_SOURCE_RE.match(raw)
    if not m:
        return None
    target = m.group(1).strip()
    if not target:
        return {"target": "", "display": "empty source slot", "is_url": False, "is_empty": True}
    return _source_attrs_from_target(target)


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
    # All arrow text is capitalized unless a single ! wraps a non-cap piece.
    # Phase 1A keeps the typed case inside !...! and uppercases the rest.
    if not text:
        return text
    pieces = re.split(r"(![^!]+!)", text)
    out = []
    for p in pieces:
        if len(p) >= 2 and p.startswith("!") and p.endswith("!"):
            out.append(p[1:-1])
        else:
            out.append(p.upper())
    return "".join(out).strip()


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
    # table row or separator; keep loose for GitHub-ish markdown.
    return text.count("|") >= 2 or bool(MD_TABLE_SEP_RE.match(text))


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


def _looks_like_local_path(text: str) -> bool:
    if not text or text.startswith(('"', "'", ">", "<")):
        return False
    if any(sep in text for sep in ("/", "\\")):
        return True
    return bool(re.search(r"\.[A-Za-z0-9]{1,8}$", text))
