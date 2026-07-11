from __future__ import annotations

from html import escape, unescape
import re
from urllib.parse import quote

from .parser import ScriptDoc, Block, _normalize_color_profile
from .themes import Theme, get_theme


RED_ARROW = "#ff4040"
GREEN_ARROW = "#42e66b"


def render_doc_html(doc: ScriptDoc, theme_name: str = "Dark Mode", allow_online_links: bool = False) -> str:
    theme = get_theme(theme_name)
    parts = [_html_head(theme, doc.header_first_line)]
    source_child_counts = _source_child_counts(doc.blocks)
    last_real_kind = ""
    last_top_source_index: int | None = None

    for i, block in enumerate(doc.blocks):
        # Extra air before source cards keeps link-heavy scripts readable on phone-width monitors.
        # If the previous top-level source had one visible child, the next source gets a larger
        # separation so repeated source/script/source/script sections do not visually run together.
        if block.kind == "source" and block.level <= 1:
            if last_top_source_index is not None and source_child_counts.get(last_top_source_index, 0) <= 1:
                parts.append('<div class="source-next-gap"></div>')
            elif last_real_kind not in {"", "header", "meta_secret", "blank", "source"}:
                parts.append('<div class="source-pre-gap"></div>')

        fancy_variant = 1 if block.kind == "markdown_fenced_box" and last_real_kind in {"markdown_fenced_box", "arrow_title"} else 0
        html = render_block(block, theme, allow_online_links=allow_online_links, fancy_variant=fancy_variant)
        if html:
            parts.append(_apply_color_profile(html, block.attrs.get("color_profile"), theme))

        if block.kind != "blank":
            last_real_kind = block.kind
            if block.kind == "source" and block.level <= 1:
                last_top_source_index = i

    if doc.warnings:
        parts.append('<div class="warnings"><b>Parser warnings:</b><br>')
        parts.extend(escape(w) + "<br>" for w in doc.warnings)
        parts.append("</div>")
    parts.append("</body></html>")
    return "\n".join(parts)


def _source_child_counts(blocks: list[Block]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for i, block in enumerate(blocks):
        if block.kind != "source" or block.level > 1:
            continue
        count = 0
        base_level = block.level
        j = i + 1
        while j < len(blocks):
            nxt = blocks[j]
            if nxt.kind != "blank" and nxt.level <= base_level:
                break
            if nxt.kind not in {"blank", "down_arrows"}:
                count += 1
            j += 1
        counts[i] = count
    return counts

_COLORABLE_TAG_RE = re.compile(
    r"<(?P<tag>section|div|p|span|a|code|blockquote|h[1-6]|table|td|th)(?P<attrs>\s[^<>]*?)?>",
    re.IGNORECASE,
)
_STYLE_ATTR_RE = re.compile(r"\sstyle=(?P<quote>['\"])(?P<value>.*?)(?P=quote)", re.IGNORECASE)


def _hex_rgb(value: str, fallback: tuple[int, int, int] = (0, 0, 0)) -> tuple[int, int, int]:
    text = str(value or "").strip().lstrip("#")
    try:
        if len(text) == 3:
            return tuple(int(ch * 2, 16) for ch in text)  # type: ignore[return-value]
        if len(text) >= 6:
            return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)
    except ValueError:
        pass
    return fallback


def _channel_to_byte(value: str) -> int:
    value = value.strip()
    if value.endswith("%"):
        return max(0, min(255, round(float(value[:-1]) * 2.55)))
    return max(0, min(255, round(float(value))))


def _alpha_to_unit(value: str) -> float:
    value = value.strip()
    if value.endswith("%"):
        return max(0.0, min(1.0, float(value[:-1]) / 100.0))
    return max(0.0, min(1.0, float(value)))


def _qt_safe_profile_color(color: str | None, theme: Theme) -> tuple[str, str] | None:
    """Return canonical input plus a solid QTextBrowser-safe hex color.

    Qt rich text reliably supports direct hex colors but not browser CSS custom
    properties. Alpha is composited against the active theme background.
    """
    canonical = _normalize_color_profile(str(color or "").strip())
    if not canonical:
        return None
    bg = _hex_rgb(theme.bg)
    alpha = 1.0
    if canonical.startswith("#"):
        digits = canonical[1:]
        if len(digits) in {3, 4}:
            rgb = tuple(int(ch * 2, 16) for ch in digits[:3])
            if len(digits) == 4:
                alpha = int(digits[3] * 2, 16) / 255.0
        else:
            rgb = (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))
            if len(digits) == 8:
                alpha = int(digits[6:8], 16) / 255.0
    else:
        match = re.fullmatch(r"(?i)rgba?\((.*?)\)", canonical)
        if not match:
            return None
        parts = [part.strip() for part in match.group(1).split(",")]
        if len(parts) not in {3, 4}:
            return None
        rgb = tuple(_channel_to_byte(part) for part in parts[:3])
        if len(parts) == 4:
            alpha = _alpha_to_unit(parts[3])
    blended = tuple(round(channel * alpha + bg_part * (1.0 - alpha)) for channel, bg_part in zip(rgb, bg))
    return canonical, "#" + "".join(f"{value:02x}" for value in blended)


def _apply_color_profile(html: str, color: str | None, theme: Theme, *, local: bool = False) -> str:
    """Color existing HTML tags directly without wrapper nodes.

    Important and fancy boxes keep their original table structure. Local line
    and row profiles are marked so whole-object coloring cannot overwrite them.
    """
    resolved = _qt_safe_profile_color(color, theme)
    if not resolved or not html:
        return html
    canonical, css_color = resolved
    declarations = (
        f"color:{css_color} !important;"
        f"border-color:{css_color} !important;"
        f"text-decoration-color:{css_color} !important;"
    )
    safe_canonical = escape(canonical, quote=True)

    def replace(match: re.Match[str]) -> str:
        tag = match.group("tag")
        attrs = match.group("attrs") or ""
        if not local and "data-swar-local-color=" in attrs:
            return match.group(0)
        style_match = _STYLE_ATTR_RE.search(attrs)
        if style_match:
            old_style = style_match.group("value").rstrip()
            if old_style and not old_style.endswith(";"):
                old_style += ";"
            replacement = f' style="{old_style}{declarations}"'
            attrs = attrs[:style_match.start()] + replacement + attrs[style_match.end():]
        else:
            attrs += f' style="{declarations}"'
        marker = "data-swar-local-color" if local else "data-swar-color"
        attrs += f' {marker}="{safe_canonical}"'
        return f"<{tag}{attrs}>"

    return _COLORABLE_TAG_RE.sub(replace, html)


def render_block(block: Block, theme: Theme, allow_online_links: bool = False, fancy_variant: int = 0) -> str:
    kind = block.kind
    text = block.text or ""
    margin = min(80, max(0, block.level * 22))

    if kind == "blank":
        return '<div class="blank"></div>'

    if kind == "markdown_paragraph_gap":
        count = max(3, int(block.attrs.get("blank_count", 3)))
        return (
            f'<div class="extended-paragraph-gap" data-blank-lines="{count}" '
            f'title="Extended paragraph break: {count} blank lines">'
            f'<span>•&nbsp;&nbsp;•&nbsp;&nbsp;•</span></div>'
        )

    if kind == "header":
        href = _copy_href(text)
        return (
            f'<section class="header-card">'
            f'<a class="copy-field header-title" href="{href}" title="Click to copy title" '
            f'style="color:{theme.title}; text-decoration:none;">{escape(text)}</a>'
            f'</section>'
        )

    if kind == "meta_secret":
        key = escape(block.attrs.get("key", "META"))
        href = _copy_href(text)
        return (
            f'<div class="meta-secret">'
            f'<a class="copy-field meta-copy" href="{href}" title="Click to copy hidden {key}" '
            f'style="color:{theme.text}; text-decoration:none;">'
            f'<span style="color:{theme.title}; font-weight:800;">{key}:</span> '
            f'<code style="color:{theme.highlight}; font-weight:900;">******</code>'
            f'</a></div>'
        )

    if kind == "bang_notice":
        return f'<div class="bang-notice" style="margin-left:{margin}px">⚠ {escape(text or "NOTICE")} ⚠</div>'

    if kind == "divider":
        center = _inline_markdown(escape(block.attrs.get("center_text", "")), theme)
        if center:
            return f'<div class="divider labeled"><span>{center}</span></div>'
        return '<div class="divider"></div>'

    if kind == "markdown_hr":
        return '<div class="markdown-hr"></div>'

    if kind == "markdown_fenced_box":
        return _render_fenced_box(block, theme, fancy_variant=fancy_variant)

    if kind == "spoken":
        return f'<p class="spoken" style="margin-left:{margin}px">{_inline_markdown(escape(text), theme)}</p>'

    if kind == "plain":
        return f'<p class="plain" style="margin-left:{margin}px">{_inline_markdown(escape(text), theme)}</p>'

    if kind == "legacy_label":
        return f'<div class="legacy-label" style="margin-left:{margin}px">{_inline_markdown(escape(text.upper()), theme)}</div>'

    if kind == "source":
        return _render_source(block, theme, allow_online_links)

    if kind == "down_arrows":
        count = int(block.attrs.get("count", 3))
        arrows = " ".join("⬇" for _ in range(min(16, max(2, count))))
        return f'<div class="down-arrows">{arrows}</div>'

    if kind.startswith("arrow_"):
        return _render_arrow(block, theme)

    if kind == "important":
        body_html = _format_important_html(text, theme, block.attrs.get("line_colors"))
        arrow_count = int(block.attrs.get("arrow_count", 2))
        label = "IMPORTANT" if arrow_count == 2 else "IMPORTANT VERBATIM"
        rail = "!!   !!   !!"
        return f'''
        <table class="important-table" width="100%" cellpadding="0" cellspacing="0" style="margin-left:{margin}px">
          <tr><td class="important-rail" colspan="3">{rail}</td></tr>
          <tr>
            <td class="important-side">!!</td>
            <td class="important-main"><div class="nameplate">{label}</div>{body_html}</td>
            <td class="important-side">!!</td>
          </tr>
          <tr><td class="important-rail" colspan="3">{rail}</td></tr>
        </table>'''

    if kind == "markdown_blockquote":
        qlevel = int(block.attrs.get("quote_level", 1))
        cls = "md-blockquote nested" if qlevel >= 2 else "md-blockquote"
        return f'<blockquote class="{cls}" style="margin-left:{margin}px">{_inline_markdown(escape(text), theme)}</blockquote>'

    if kind in {
        "markdown_check_item", "markdown_num_item", "markdown_money_item", "markdown_bullet_item",
        "markdown_dash_item", "markdown_numbered_tab", "markdown_ordered_item",
    }:
        if kind == "markdown_check_item":
            label = "☑" if block.attrs.get("checked") else "☐"
        elif kind == "markdown_num_item":
            label = "#"
        elif kind == "markdown_money_item":
            label = escape(str(block.attrs.get("marker", "$")))
        elif kind == "markdown_bullet_item":
            label = "+"
        elif kind in {"markdown_numbered_tab", "markdown_ordered_item"}:
            label = f"({int(block.attrs.get('marker', 0))})"
        else:
            label = ""
        no_mark = " no-mark" if kind == "markdown_dash_item" else ""
        return (
            f'<div class="md-list-item {kind}{no_mark}" style="margin-left:{margin}px">'
            f'<span class="md-list-mark">{label}</span>'
            f'<span class="md-list-text">{_inline_markdown(escape(text), theme)}</span></div>'
        )

    if kind == "markdown_percent_list":
        return _render_percent_list(block, theme)

    if kind == "markdown_heading":
        level = min(max(int(block.attrs.get("heading_level", 1)), 1), 6)
        tag = f"h{level}"
        return f'<{tag} class="md-heading md-h{level}">{_inline_markdown(escape(text), theme)}</{tag}>'

    if kind == "markdown_table":
        return _render_markdown_table(text, theme, block.attrs.get("row_colors"))

    return f'<p class="plain" style="margin-left:{margin}px">{_inline_markdown(escape(text), theme)}</p>'


def _copy_href(value: str) -> str:
    return "copy:" + quote(value or "", safe="")


def _render_source(block: Block, theme: Theme, allow_online_links: bool) -> str:
    attrs = block.attrs
    margin = min(80, max(0, block.level * 22))
    if attrs.get("is_empty"):
        return f'<div class="source empty" style="margin-left:{margin}px">- empty source slot</div>'
    if attrs.get("is_url"):
        tld = escape(attrs.get("tld", ""))
        host = escape(attrs.get("host", ""))
        page = escape(attrs.get("page", ""))
        meta_line = f'<div class="source-meta">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;TLD: {tld}&nbsp;&nbsp; HOST: {host}&nbsp;&nbsp; PAGE: {page}</div>'
        if attrs.get("private"):
            return f'''<div class="source url private" style="margin-left:{margin}px" title="Private link hidden in reader mode">
                <span>PRIVATE LINK: <code>******</code></span>
                {meta_line}
            </div>'''
        target = attrs.get("target", block.text)
        copy_target = attrs.get("url", target)
        safe_target = escape(target)
        href = _copy_href(copy_target)
        tooltip = "Click to copy source link" if allow_online_links else "Link, Go Online to Visit / click copies link"
        return f'''<div class="source url" style="margin-left:{margin}px" title="{escape(tooltip)}">
            <a href="{href}" class="source-link">{safe_target}</a>
            {meta_line}
        </div>'''
    display = escape(attrs.get("display", block.text))
    return f'<div class="source local" style="margin-left:{margin}px">{display}<div class="source-meta">&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;LOCAL PATH</div></div>'


def _render_arrow(block: Block, theme: Theme) -> str:
    count = int(block.attrs.get("arrow_count", 2))
    text_html = _inline_markdown(escape(block.text), theme)
    text_plain = re.sub(r"<[^>]+>", "", block.text or "").strip()
    margin = 0 if block.attrs.get("center") else min(80, max(0, block.level * 22))
    important = " important-arrow" if block.attrs.get("important") else ""
    balanced = "" if block.attrs.get("balanced", True) else " unbalanced"
    arrows_left = "➤" * min(count, 8)
    arrows_right = "◀" * min(count, 8)

    if count == 2:
        cls = "arrow-data"
    elif count == 3:
        cls = "arrow-verbatim"
        if _looks_like_mini_section(text_plain):
            cls += " arrow-mini-title centered"
    elif count == 4:
        cls = "arrow-title centered"
    elif count == 5:
        cls = "arrow-descriptor centered"
    elif count == 6:
        cls = "arrow-explainer"
    else:
        cls = "arrow-major centered"

    transition_cls = _transition_class(text_plain)
    if transition_cls:
        cls += " " + transition_cls

    if count >= 7:
        return f'<div class="{cls}{important}{balanced}" style="margin-left:{margin}px"><span class="side-arrows">{arrows_left}</span><span class="arrow-text">{text_html}</span><span class="side-arrows">{arrows_right}</span></div>'
    return f'<div class="{cls}{important}{balanced}" style="margin-left:{margin}px">{text_html}</div>'


def _looks_like_mini_section(text: str) -> bool:
    clean = re.sub(r"[^A-Z0-9 ]+", "", (text or "").upper()).strip()
    if not clean:
        return False
    words = clean.split()
    if len(words) > 5:
        return False
    action_starts = {
        "READ", "CLICK", "SHOW", "HOVER", "SCROLL", "PLAY", "REVIEW", "SWITCH", "MOVE",
        "MAKE", "OPEN", "WAIT", "ROLL", "THANK", "VIEW", "GIVE", "USE", "GO", "DO",
    }
    return words[0] not in action_starts


def _transition_class(text: str) -> str:
    clean = re.sub(r"\s+", " ", (text or "").strip().upper())
    if clean == "LEAVE CONTEXT" or (clean.startswith("EXIT") and clean.endswith("BACKGROUND")):
        return "transition-exit"
    if clean == "JUMP IN" or (clean.startswith("RETURN") and clean.endswith("SHOW")):
        return "transition-return"
    return ""


def _format_important_html(text: str, theme: Theme, line_colors: list[str | None] | None = None) -> str:
    lines = text.splitlines() or [text]
    out: list[str] = []
    for i, line in enumerate(lines):
        clean = line.strip().strip('"')
        if not clean:
            continue
        normalized = " ".join(clean.split())
        line_html = (
            f'<div class="important-line important-line-{min(i, 8)}">'
            f'{_inline_markdown(escape(normalized), theme)}</div>'
        )
        color = line_colors[i] if line_colors and i < len(line_colors) else None
        out.append(_apply_color_profile(line_html, color, theme, local=True))
    return "\n".join(out) if out else '<div class="important-line"></div>'


def _render_fenced_box(block: Block, theme: Theme, fancy_variant: int = 0) -> str:
    info = str(block.attrs.get("fence_info") or "CODE").strip()[:40]
    label = str(block.attrs.get("box_label") or "").strip()[:48]
    top_label = escape(info.upper())
    bottom_label = "```"
    variant = " fancy-alt" if fancy_variant else ""
    unclosed = " fancy-unclosed" if block.attrs.get("unclosed") else ""
    margin = min(80, max(0, block.level * 22))
    body_html = _format_fenced_body(block.text or "", theme, block.attrs.get("line_colors"))
    nameplate = f'<div class="fancy-label">{_inline_markdown(escape(label), theme)}</div>' if label else ""
    return f'''
    <table class="fancy-box{variant}{unclosed}" width="100%" cellpadding="0" cellspacing="0" style="margin-left:{margin}px">
      <tr><td class="fancy-rail" colspan="3">!!&nbsp;&nbsp;{top_label}&nbsp;&nbsp;!!</td></tr>
      <tr>
        <td class="fancy-side">!!</td>
        <td class="fancy-main">{nameplate}{body_html}</td>
        <td class="fancy-side">!!</td>
      </tr>
      <tr><td class="fancy-rail fancy-bottom" colspan="3">!!&nbsp;&nbsp;{bottom_label}&nbsp;&nbsp;!!</td></tr>
    </table>'''


def _format_fenced_body(text: str, theme: Theme, line_colors: list[str | None] | None = None) -> str:
    lines = text.splitlines() or [text]
    out: list[str] = []
    for line_index, line in enumerate(lines):
        clean = line.strip()
        if not clean:
            out.append('<div class="fancy-gap"></div>')
            continue
        list_match = re.match(r"^(?:[-+]|\d+[.)]|-#)\s+(.+)$", clean)
        task_match = re.match(r"^-\s*\[([ xX])\]\s+(.+)$", clean)
        if task_match:
            mark = "☑" if task_match.group(1).lower() == "x" else "☐"
            content = task_match.group(2)
            line_html = f'<div class="fancy-line fancy-list"><span>{mark}</span> {_inline_markdown(escape(content), theme)}</div>'
        elif list_match:
            line_html = f'<div class="fancy-line fancy-list">{_inline_markdown(escape(list_match.group(1)), theme)}</div>'
        else:
            line_html = f'<div class="fancy-line">{_inline_markdown(escape(clean), theme)}</div>'
        color = line_colors[line_index] if line_colors and line_index < len(line_colors) else None
        out.append(_apply_color_profile(line_html, color, theme, local=True))
    return "\n".join(out) if out else '<div class="fancy-line"></div>'

def _render_percent_list(block: Block, theme: Theme) -> str:
    items = list(block.attrs.get("items", []))
    if not items:
        return ""
    total = sum(max(0, int(item.get("percent", 0))) for item in items)
    goal = max(100, ((total + 99) // 100) * 100)
    values = [int(item.get("percent", 0)) for item in items]
    high = max(values) if values else 0
    low = min(values) if values else 0
    margin = min(80, max(0, block.level * 22))
    out = [f'<div class="md-percent-list" style="margin-left:{margin}px" title="Percent goal: {goal}%">']
    for idx, item in enumerate(items):
        pct = max(0, int(item.get("percent", 0)))
        label = escape(str(item.get("text", "")))
        if pct == high and high != low:
            cls = "best"
        elif pct == low and high != low:
            cls = "worst"
        else:
            cls = "alt5" if idx % 2 == 0 else "alt4"
        width = max(2, min(100, int((pct / goal) * 100)))
        item_html = f'<div class="md-percent-item {cls}"><span class="pct">{pct}%</span><span class="pct-label">{_inline_markdown(label, theme)}</span><span class="pct-bar"><span style="width:{width}%"></span></span></div>'
        out.append(_apply_color_profile(item_html, item.get("color_profile"), theme, local=True))
    out.append('</div>')
    return "\n".join(out)


def _split_markdown_table_cells(line: str) -> list[str]:
    r"""Split a table row on unescaped pipes and preserve \| for inline unescape."""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    cells: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(stripped):
        char = stripped[index]
        if char == "\\" and index + 1 < len(stripped) and stripped[index + 1] == "|":
            current.extend(["\\", "|"])
            index += 2
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    cells.append("".join(current).strip())
    return cells


def _render_markdown_table(raw: str, theme: Theme, row_colors: list[str | None] | None = None) -> str:
    rows: list[tuple[list[str], str | None]] = []
    for line_index, line in enumerate(raw.splitlines()):
        raw_cells = _split_markdown_table_cells(line)
        if raw_cells and all(re.fullmatch(r":?-{3,}:?", c.strip()) for c in raw_cells):
            continue
        row_color = row_colors[line_index] if row_colors and line_index < len(row_colors) else None
        rows.append(([escape(c) for c in raw_cells], row_color))
    if not rows:
        return ""
    html = ['<table class="md-table">']
    for r, (cells, row_color) in enumerate(rows):
        tag = "th" if r == 0 else "td"
        row_html = "<tr>" + "".join(f"<{tag}>{_inline_markdown(c, theme)}</{tag}>" for c in cells) + "</tr>"
        html.append(_apply_color_profile(row_html, row_color, theme, local=True))
    html.append("</table>")
    return "\n".join(html)


def _protect_backslash_escapes(safe_text: str) -> tuple[str, list[str]]:
    """Protect standard Markdown backslash escapes before inline styling.

    ``safe_text`` has already passed through html.escape(), so five punctuation
    characters appear as entities. Tokens are restored only after all Markdown
    regexes run, which makes escaped markers literal and safe.
    """
    entity_tokens = {
        "&quot;": "&quot;",
        "&#x27;": "&#x27;",
        "&amp;": "&amp;",
        "&lt;": "&lt;",
        "&gt;": "&gt;",
    }
    punctuation = set("!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~")
    held: list[str] = []
    out: list[str] = []
    index = 0

    def hold(value: str) -> None:
        held.append(value)
        out.append(f"@@SWAR_ESC{len(held) - 1}@@")

    while index < len(safe_text):
        if safe_text[index] != "\\":
            out.append(safe_text[index])
            index += 1
            continue
        if index + 1 >= len(safe_text):
            out.append("\\")
            index += 1
            continue
        matched_entity = False
        for encoded, restored in entity_tokens.items():
            if safe_text.startswith(encoded, index + 1):
                hold(restored)
                index += 1 + len(encoded)
                matched_entity = True
                break
        if matched_entity:
            continue
        next_char = safe_text[index + 1]
        if next_char in punctuation:
            hold(next_char)
            index += 2
            continue
        out.append("\\")
        index += 1
    return "".join(out), held


def _inline_markdown(safe_text: str, theme: Theme, *, allow_links: bool = True) -> str:
    """Render a safe, intentionally small inline Markdown subset.

    Input is already HTML-escaped. Code spans are protected first so their
    contents act as a syntax breakout and are never recursively styled.
    """
    code_tokens: list[str] = []
    link_tokens: list[str] = []
    staged, escape_tokens = _protect_backslash_escapes(safe_text)

    def hold_code(match: re.Match[str]) -> str:
        code_tokens.append(f"<code>{match.group(1)}</code>")
        return f"@@SWAR_CODE_{len(code_tokens) - 1}@@"

    staged = re.sub(r"`([^`\n]+)`", hold_code, staged)

    if allow_links:
        def hold_link(match: re.Match[str]) -> str:
            label = _inline_markdown(match.group(1), theme, allow_links=False)
            raw_url = unescape(match.group(2).strip())
            normalized = "https://" + raw_url if raw_url.lower().startswith("www.") else raw_url
            if not re.match(r"^https?://", normalized, re.IGNORECASE):
                return match.group(0)
            href = _copy_href(normalized)
            link_tokens.append(
                f'<a class="inline-copy-link" href="{href}" title="Click to copy link">{label}</a>'
            )
            return f"@@SWAR_LINK_{len(link_tokens) - 1}@@"
        staged = re.sub(r"\[([^]\n]+)\]\(((?:https?://|www\.)[^\s)]+)\)", hold_link, staged, flags=re.IGNORECASE)

    staged = re.sub(r"___(.+?)___", r"<u>\1</u>", staged)
    staged = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", staged)
    staged = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", staged)
    staged = re.sub(r"__(.+?)__", r"<strong>\1</strong>", staged)
    staged = re.sub(r"~~(.+?)~~", r"<del>\1</del>", staged)
    staged = re.sub(r"(?<!~)~(?!~)(.+?)(?<!~)~(?!~)", r"<del>\1</del>", staged)
    staged = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", staged)

    for index, value in enumerate(link_tokens):
        staged = staged.replace(f"@@SWAR_LINK_{index}@@", value)
    for index, value in enumerate(code_tokens):
        staged = staged.replace(f"@@SWAR_CODE_{index}@@", value)
    for index, value in enumerate(escape_tokens):
        staged = staged.replace(f"@@SWAR_ESC{index}@@", value)
    return staged

def _html_head(theme: Theme, title: str) -> str:
    return f'''<!doctype html>
<html><head><meta charset="utf-8"><title>{escape(title)}</title>
<style>
body {{
  background: {theme.bg};
  color: {theme.text};
  font-family: "DejaVu Sans", "Noto Color Emoji", "Segoe UI Emoji", "Apple Color Emoji", "Liberation Sans", Arial, sans-serif;
  font-size: 18px;
  line-height: 1.48;
  margin: 18px 24px;
}}
.blank {{ height: 12px; }}
.extended-paragraph-gap {{
  display:flex; align-items:center; justify-content:center; gap:12px;
  min-height:72px; margin:18px 8%; color:{theme.muted}; opacity:0.78;
}}
.extended-paragraph-gap::before, .extended-paragraph-gap::after {{
  content:""; flex:1; border-top:1px dashed {theme.border};
}}
.extended-paragraph-gap span {{ font-size:16px; letter-spacing:5px; color:{theme.highlight3}; }}
.header-card {{
  border: 3px solid {theme.border};
  background: {theme.panel};
  border-radius: 14px;
  padding: 20px 16px;
  margin: 0 0 22px 0;
}}
.header-title {{ display:block; text-align:center; font-size: 30px; font-weight: 900; letter-spacing: 0.5px; color:{theme.title}; }}
.copy-field {{ text-decoration:none; }}
.copy-field:hover {{ text-decoration: underline; }}
.meta-secret {{ color:{theme.text}; font-size: 15px; margin: 6px 0; }}
.meta-copy {{ color:{theme.text}; }}
.meta-secret span {{ color:{theme.title}; }}
.meta-secret code {{ color:{theme.highlight}; }}
a {{ color: {theme.link}; text-decoration: none; font-weight: 800; }}
a:hover {{ text-decoration: underline; }}
.spoken {{ border-left: 4px solid {theme.border}; padding: 8px 14px; background: {theme.panel}; border-radius: 0 10px 10px 0; margin-bottom:16px; }}
.plain {{ padding: 4px 10px; margin-bottom:14px; }}
.bang-notice {{ color:{theme.important}; border: 2px dashed {theme.important}; background:{theme.panel}; padding:10px; border-radius:10px; font-weight:800; text-align:center; }}
.divider {{ display:flex; align-items:center; text-align:center; margin: 22px 0; color:{theme.muted}; }}
.divider::before, .divider::after {{ content:""; flex:1; border-bottom: 5px solid {theme.border}; }}
.divider span {{ padding: 0 14px; font-weight:900; color:{theme.highlight}; }}
.markdown-hr {{ height:0; border:0; border-top:4px double {theme.highlight3}; margin:26px 5%; }}
.legacy-label {{ font-weight:900; color:{theme.title}; border-bottom:2px solid {theme.border}; padding-top:12px; font-size:22px; }}
.source-pre-gap {{ height: 38px; }}
.source-next-gap {{ height: 78px; }}
.source {{ border: 2px solid {theme.source}; border-radius:12px; padding: 10px 12px; margin-top: 14px; margin-bottom: 20px; background:{theme.panel}; }}
.source.local {{ color:{theme.muted}; border-style:dotted; }}
.source.private {{ border-style:dashed; color:{theme.muted}; }}
.source-link {{ word-wrap: break-word; overflow-wrap: anywhere; }}
.source-meta {{ color:{theme.muted}; font-size: 13px; margin-top: 5px; display:block; }}
.arrow-data, .arrow-verbatim, .arrow-title, .arrow-descriptor, .arrow-explainer, .arrow-major {{
  padding: 8px 12px;
  margin-top: 8px;
  margin-bottom: 8px;
  border-radius: 10px;
  font-weight: 900;
  letter-spacing: 0.9px;
}}
.arrow-data {{ border-left: 6px solid {theme.data}; color:{theme.data}; background:{theme.panel}; }}
.arrow-verbatim {{ border-left: 6px double {theme.verbatim}; color:{theme.verbatim}; background:{theme.panel}; }}
.arrow-mini-title {{ border-left: 0; border-top:2px solid {theme.border}; border-bottom:2px solid {theme.border}; font-size:24px; color:{theme.section_title}; }}
.arrow-title {{ border: 3px solid {theme.section_title}; color:{theme.section_title}; background:{theme.panel}; font-size:26px; }}
.arrow-descriptor {{ border: 3px dashed {theme.descriptor}; color:{theme.descriptor}; background:{theme.panel}; font-size:24px; }}
.arrow-explainer {{ border-left: 10px solid {theme.explainer}; color:{theme.explainer}; background:{theme.panel}; }}
.arrow-major {{ border-top: 5px solid {theme.major_explainer}; border-bottom: 5px solid {theme.major_explainer}; color:{theme.major_explainer}; font-size:25px; background:{theme.panel}; }}
.arrow-title strong, .arrow-descriptor strong, .arrow-major strong {{ font-weight: 1000; font-size: 118%; }}
.centered {{ text-align:center; }}
.side-arrows {{ padding: 0 10px; color:{theme.major_explainer}; }}
.transition-exit .side-arrows {{ color:{RED_ARROW}; }}
.transition-return .side-arrows {{ color:{GREEN_ARROW}; }}
.important-arrow {{ box-shadow: 0 0 0 3px {theme.highlight} inset; }}
.unbalanced {{ outline: 2px dotted red; }}
.important-table {{ border: 4px solid {theme.important}; background:{theme.panel}; border-radius:14px; padding: 8px; margin-top: 16px; margin-bottom: 18px; }}
.important-side {{ font-size:34px; color:{theme.important}; font-weight:900; text-align:center; vertical-align:middle; width:42px; }}
.important-rail {{ font-size:20px; color:{theme.important}; font-weight:900; text-align:center; letter-spacing: 8px; padding: 2px 0; }}
.important-main {{ text-align:center; }}
.important-main .nameplate {{ text-align:center; color:{theme.important}; font-weight:900; padding:4px 0 10px 0; font-size:18px; }}
.important-line {{ text-align:center; color:{theme.text}; font-size:21px; line-height:1.85; word-spacing: 1.65em; font-family: "DejaVu Sans Mono", "Noto Color Emoji", monospace; }}
.important-line-1 {{ padding-left: 12px; }}
.important-line-2 {{ padding-left: 24px; }}
.important-line-3 {{ padding-left: 36px; }}
.fancy-box {{ border: 4px solid {theme.highlight3}; background:{theme.panel}; border-radius:14px; padding:8px; margin-top:18px; margin-bottom:22px; color:{theme.text}; }}
.fancy-box.fancy-alt {{ border-color:{theme.highlight4}; }}
.fancy-box.fancy-unclosed {{ border-style:dashed; }}
.fancy-side {{ font-size:34px; color:{theme.highlight3}; font-weight:900; text-align:center; vertical-align:middle; width:42px; }}
.fancy-alt .fancy-side, .fancy-alt .fancy-rail {{ color:{theme.highlight4}; }}
.fancy-rail {{ font-size:20px; color:{theme.highlight3}; font-weight:900; text-align:center; letter-spacing:5px; padding:3px 0; }}
.fancy-bottom {{ font-family:"DejaVu Sans Mono", monospace; }}
.fancy-main {{ text-align:center; padding:8px 14px; }}
.fancy-label {{ display:inline-block; color:{theme.highlight3}; border:2px solid {theme.highlight3}; border-radius:9px; padding:4px 12px; margin:2px auto 12px auto; font-weight:900; }}
.fancy-alt .fancy-label {{ color:{theme.highlight4}; border-color:{theme.highlight4}; }}
.fancy-line {{ text-align:center; color:{theme.text}; font-size:19px; line-height:1.7; margin:5px 0; }}
.fancy-list {{ padding:5px 10px; border-left:4px solid {theme.highlight3}; background:{theme.bg}; }}
.fancy-gap {{ height:10px; }}
.down-arrows {{ text-align:center; color:{theme.highlight}; font-size:30px; letter-spacing: 6px; font-weight:900; margin: 2px 0 18px 0; }}
.md-heading {{ color:{theme.markdown_heading}; font-weight:900; line-height:1.22; }}
.md-h1 {{ text-align:center; font-size:36px; border:3px solid {theme.highlight3}; background:{theme.panel}; border-radius:12px; padding:14px 18px; margin:30px 0 22px; }}
.md-h2 {{ font-size:32px; border-left:9px solid {theme.highlight3}; border-bottom:3px solid {theme.border}; padding:8px 14px; margin:26px 0 18px; }}
.md-h3 {{ font-size:28px; border-bottom:3px double {theme.border}; padding:6px 8px; margin:23px 0 16px; }}
.md-h4 {{ font-size:24px; border-left:5px solid {theme.highlight4}; padding:5px 10px; margin:20px 0 14px; }}
.md-h5 {{ font-size:21px; color:{theme.highlight2}; letter-spacing:0.6px; margin:18px 0 12px; }}
.md-h6 {{ text-align:right; font-size:17px; color:{theme.muted}; border-bottom:1px dotted {theme.border}; padding-bottom:4px; margin:16px 0 10px; font-style:italic; }}
.md-table {{ margin: 18px auto; border-collapse: collapse; color:{theme.text}; background:{theme.panel}; }}
.md-table th, .md-table td {{ border: 1px solid {theme.markdown_table}; padding: 8px 12px; }}
.md-table th {{ color:{theme.markdown_table}; font-weight:900; }}
.md-blockquote {{ border-left: 8px solid {theme.highlight}; background:{theme.panel}; margin: 18px auto; padding: 14px 18px; max-width: 86%; border-radius: 0 12px 12px 0; color:{theme.text}; }}
.md-blockquote.nested {{ border-left-color:{theme.highlight4}; margin-left: 48px; max-width: 80%; }}
.md-list-item {{ background:{theme.panel}; border-left:5px solid {theme.highlight5}; margin:8px 0; padding:8px 12px; border-radius: 0 10px 10px 0; }}
.md-list-mark {{ color:{theme.highlight}; font-weight:900; display:inline-block; min-width: 42px; }}
.md-list-text {{ display:inline; }}
.md-list-item.no-mark {{ border-left-color:{theme.border}; margin-bottom:16px; }}
.md-list-item.no-mark .md-list-mark {{ min-width:14px; }}
.markdown_numbered_tab {{ margin-bottom:16px; border-left-color:{theme.highlight4}; }}
.markdown_ordered_item {{ border-left-color:{theme.highlight3}; }}
.markdown_num_item .md-list-mark {{ color:{theme.highlight4}; }}
.markdown_money_item .md-list-mark {{ color:{theme.fade_green1}; }}
.markdown_bullet_item .md-list-mark {{ color:{theme.fade_purple1}; }}
.md-percent-list {{ margin: 16px 0 18px 0; padding: 10px; background:{theme.panel}; border-radius:12px; border: 1px solid {theme.border}; }}
.md-percent-item {{ display:block; margin:8px 0; padding:6px 8px; border-left: 5px solid {theme.highlight5}; }}
.md-percent-item .pct {{ font-weight:900; min-width:56px; display:inline-block; }}
.md-percent-item.best {{ color:#55dd77; border-left-color:#55dd77; }}
.md-percent-item.worst {{ color:#ff4040; border-left-color:#ff4040; }}
.md-percent-item.alt5 {{ color:{theme.highlight5}; }}
.md-percent-item.alt4 {{ color:{theme.highlight4}; }}
.pct-bar {{ display:block; height: 6px; background:{theme.bg}; margin-top:4px; border-radius:6px; overflow:hidden; }}
.pct-bar span {{ display:block; height:6px; background: currentColor; }}
strong {{ font-weight: 1000; color:{theme.title}; }}
em {{ color:{theme.highlight}; }}
u {{ text-decoration: underline; text-decoration-thickness: 2px; color:{theme.highlight2}; }}
del {{ text-decoration: line-through; text-decoration-thickness:2px; color:{theme.muted}; }}
.inline-copy-link {{ color:{theme.link}; border-bottom:1px dotted {theme.link}; cursor:pointer; }}
code {{ background:{theme.bg}; color:{theme.highlight}; padding:2px 5px; border-radius:4px; }}
.warnings {{ border:2px solid #cc0000; color:#ff6666; padding:10px; margin:16px 0; }}
</style></head><body>'''
