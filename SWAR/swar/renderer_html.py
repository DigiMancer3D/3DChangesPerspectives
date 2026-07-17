from __future__ import annotations

from html import escape, unescape
import re
from urllib.parse import quote

from .parser import ScriptDoc, Block, SwarParser, _normalize_color_profile
from .themes import Theme, get_theme


RED_ARROW = "#ff4040"
GREEN_ARROW = "#42e66b"
DIM_GOLD = "#b88a32"
BRIGHT_GOLD = "#ffd75a"
ATTN_RED = "#ff3b3b"
STORY_ARC_COLOR = "#b889ff"
STORY_LEFT_COLOR = "#5fc8ff"
STORY_RIGHT_COLOR = "#ff9bcf"
STORY_CENTER_COLOR = "#ffd75a"
STORY_DIRECTIVE_COLOR = "#8ce6a2"


def render_doc_html(
    doc: ScriptDoc,
    theme_name: str = "Dark Mode",
    allow_online_links: bool = False,
    story_collapsed: set[str] | None = None,
) -> str:
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

        # Zero-width named anchors let Split/Story map editor source lines to
        # exact rendered Y positions.  They account for tall boxes and vertical
        # gap marks without adding visible content.
        parts.append(f'<a name="swar-line-{max(1, int(block.line_start))}" style="font-size:0; line-height:0;">&#8203;</a>')
        fancy_variant = 1 if block.kind == "markdown_fenced_box" and last_real_kind in {"markdown_fenced_box", "arrow_title"} else 0
        html = render_block(
            block,
            theme,
            allow_online_links=allow_online_links,
            fancy_variant=fancy_variant,
            story_collapsed=story_collapsed,
        )
        if html:
            parts.append(_apply_color_profile(html, block.attrs.get("color_profile"), theme))

        if block.kind != "blank":
            last_real_kind = block.kind
            if block.kind == "source" and block.level <= 1:
                last_top_source_index = i

    if doc.blocks:
        final_line = max(int(block.line_end) for block in doc.blocks) + 1
        parts.append(f'<a name="swar-line-{final_line}" style="font-size:0; line-height:0;">&#8203;</a>')
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


def render_block(
    block: Block,
    theme: Theme,
    allow_online_links: bool = False,
    fancy_variant: int = 0,
    story_collapsed: set[str] | None = None,
) -> str:
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

    if kind == "vertical_gap":
        count = max(1, min(40, int(block.attrs.get("gap_lines", 7))))
        page_cls = " page-break-gap" if block.attrs.get("page_break") else ""
        return f'<div class="swar-vertical-gap{page_cls}" data-gap-lines="{count}">' + ("<br>" * count) + "</div>"

    if kind == "golden_dim":
        prefix = _inline_markdown(escape(str(block.attrs.get("prefix", text))), theme)
        highlighted = _inline_markdown(escape(str(block.attrs.get("highlight", ""))), theme)
        return (f'<div class="golden-line golden-dim" style="margin-left:{margin}px">'
                f'<span class="golden-prefix">{prefix}</span> '
                f'<span class="golden-highlight">{highlighted}</span></div>')

    if kind == "golden_bright":
        highlighted = _inline_markdown(escape(str(block.attrs.get("highlight", text))), theme)
        return f'<div class="golden-line golden-bright" style="margin-left:{margin}px">{highlighted}</div>'

    if kind == "attention_red":
        arrows = escape(str(block.attrs.get("arrows", "<<<<<<")))
        return (f'<div class="attention-red" style="margin-left:{margin}px">'
                f'<span>{_inline_markdown(escape(text), theme)}</span> <span class="attention-arrows">{arrows}</span></div>')

    if kind == "indent4":
        return f'<p class="plain indent-four" style="margin-left:{margin}px">{_inline_markdown(escape(text), theme)}</p>'

    if kind == "arc_record":
        return _render_arc_record(
            block,
            theme,
            allow_online_links=allow_online_links,
            story_collapsed=story_collapsed,
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
        clean = line.strip()
        # Remove quotes only when this exact line has one complete outer pair.
        # The earlier strip('"') ate a meaningful final quote on multi-line content.
        if len(clean) >= 2 and clean.startswith('"') and clean.endswith('"'):
            clean = clean[1:-1]
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


def _story_arc_divider(*, compact: bool = False, theme: Theme | None = None) -> str:
    cls = "story-arc-divider compact" if compact else "story-arc-divider"
    color = STORY_ARC_COLOR
    if theme is not None:
        color = _story_palette(theme)[0]
    border = f"2px solid {color}" if compact else f"4px double {color}"
    return (
        f'<table class="{cls}" width="100%" cellspacing="0" cellpadding="0" style="color:{color};">'
        f'<tr><td class="story-divider-line" style="border-bottom:{border};"></td>'
        f'<th style="color:{color};">STORY ARC</th>'
        f'<td class="story-divider-line" style="border-bottom:{border};"></td></tr></table>'
    )


def _render_embedded_story_markup(
    text: str,
    theme: Theme,
    allow_online_links: bool = False,
    *,
    suppress_header_card: bool = False,
) -> str:
    """Render normal SWAR markup inside Story fields and nested dialogue.

    Literal ``\\n`` sequences are accepted because one .arcs record occupies one
    physical source line. The embedded parse deliberately uses a .script path,
    so it cannot recurse into Arc-record parsing. For nested speech/thought, a
    plain first line is rendered as ordinary content rather than a document
    header card.
    """
    decoded = str(text or "").replace("\\n", "\n").strip()
    if not decoded:
        return '<span class="arc-empty">empty</span>'
    embedded = SwarParser().parse(decoded, path="embedded_story.script")
    rendered: list[str] = []
    for item in embedded.blocks:
        if suppress_header_card and item.kind == "header":
            html = f'<p class="story-embedded-plain">{_inline_markdown(escape(item.text or ""), theme)}</p>'
        else:
            html = render_block(item, theme, allow_online_links=allow_online_links)
        if html:
            rendered.append(_apply_color_profile(html, item.attrs.get("color_profile"), theme))
    return "\n".join(rendered) if rendered else _inline_markdown(escape(decoded), theme)


def _story_inline(value: str, theme: Theme) -> str:
    return _inline_markdown(escape(str(value or "")), theme)


def _story_rgb(value: str, fallback: tuple[int, int, int] = (128, 128, 128)) -> tuple[int, int, int]:
    return _hex_rgb(value, fallback=fallback)


def _story_hex(rgb: tuple[int, int, int]) -> str:
    return "#" + "".join(f"{max(0, min(255, int(channel))):02x}" for channel in rgb)


def _story_luminance(value: str) -> float:
    rgb = _story_rgb(value)
    channels: list[float] = []
    for channel in rgb:
        point = channel / 255.0
        channels.append(point / 12.92 if point <= 0.04045 else ((point + 0.055) / 1.055) ** 2.4)
    return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2]


def _story_mix(color: str, target: str, amount: float) -> str:
    amount = max(0.0, min(1.0, float(amount)))
    left = _story_rgb(color)
    right = _story_rgb(target)
    return _story_hex(tuple(round(a + (b - a) * amount) for a, b in zip(left, right)))


def _story_solid_color(value: str | None, theme: Theme, fallback: str) -> str:
    resolved = _qt_safe_profile_color(str(value or ""), theme)
    return resolved[1] if resolved else fallback


def _story_palette(theme: Theme) -> tuple[str, ...]:
    """Build a deterministic speaker/section palette from the active theme.

    Colors are taken from SWAR's existing theme highlight profiles, then moved
    away from the current background when necessary. This keeps the Story view
    readable in NIGHT/TERM/BLUE and in LIGHT/PAPER without adding a separate
    hard-coded Story theme system.
    """
    candidates = (
        theme.highlight,
        theme.highlight2,
        theme.highlight3,
        theme.highlight4,
        theme.highlight5,
        theme.data,
        theme.descriptor,
        theme.explainer,
        theme.major_explainer,
        theme.fade_purple1,
        theme.fade_green1,
        theme.link,
    )
    bg = _story_solid_color(theme.bg, theme, "#000000")
    bg_luma = _story_luminance(bg)
    target = "#ffffff" if bg_luma < 0.45 else "#000000"
    colors: list[str] = []
    for candidate in candidates:
        color = _story_solid_color(candidate, theme, STORY_ARC_COLOR)
        if abs(_story_luminance(color) - bg_luma) < 0.24:
            color = _story_mix(color, target, 0.48)
        if color.casefold() not in {item.casefold() for item in colors}:
            colors.append(color)
    for fallback in (STORY_LEFT_COLOR, STORY_RIGHT_COLOR, STORY_CENTER_COLOR, STORY_DIRECTIVE_COLOR, BRIGHT_GOLD):
        color = _story_solid_color(fallback, theme, fallback)
        if color.casefold() not in {item.casefold() for item in colors}:
            colors.append(color)
    return tuple(colors) or (STORY_ARC_COLOR,)


def _story_speaker_color(index: int, theme: Theme, sequence_step: int = 0) -> str:
    palette = _story_palette(theme)
    base = palette[index % len(palette)]
    # Sequential lines from the same speaker gently brighten on dark themes and
    # darken on light themes. The fifth line reflows to the base color; any
    # speaker change also resets the sequence immediately.
    step = max(0, int(sequence_step)) % 5
    if step == 0:
        return base
    bg = _story_solid_color(theme.bg, theme, "#000000")
    target = "#ffffff" if _story_luminance(bg) < 0.45 else "#000000"
    return _story_mix(base, target, (0.075, 0.14, 0.205, 0.27)[step - 1])


_STORY_BLOCK_MARK_RE = re.compile(
    r'(?m)^\s*(?:>{2,}|#{1,6}\s+|`{3,}|---|\*{3,}\s*$|->\s+|!!(?:\s|$)|-{3,}\s*$)'
)


def _render_story_talk_content(value: str, theme: Theme, allow_online_links: bool = False) -> tuple[str, bool]:
    decoded = str(value or "").replace("\\n", "\n").strip()
    rich = "\n" in decoded or bool(_STORY_BLOCK_MARK_RE.search(decoded))
    if rich:
        return _render_embedded_story_markup(
            decoded,
            theme,
            allow_online_links,
            suppress_header_card=True,
        ), True
    return _story_inline(decoded, theme), False


def _render_story_talk(
    item: dict[str, str],
    theme: Theme,
    *,
    slot: str,
    speaker_index: int,
    sequence_step: int = 0,
    allow_online_links: bool = False,
) -> str:
    slot = slot if slot in {"left", "right", "center"} else "center"
    speaker_raw = str(item.get("speaker", "TALKER") or "TALKER").strip()
    speaker = _story_inline(speaker_raw, theme)
    text, rich = _render_story_talk_content(item.get("text", ""), theme, allow_online_links)
    target = str(item.get("target", "")).strip()
    color = _story_speaker_color(speaker_index, theme, sequence_step)
    target_html = ""
    if target:
        target_html = f'<div class="story-talk-target">TO&nbsp;→&nbsp;{_story_inline(target, theme)}</div>'
    is_thought = item.get("talk_type") == "thought"
    thought = " thought" if is_thought else " talk"
    kind_label = "THOUGHT" if is_thought else ("RICH DIALOGUE" if rich else "DIALOGUE")
    left_buffer = "!!" if slot in {"right", "center"} else ""
    right_buffer = "!!" if slot in {"left", "center"} else ""
    quote_open = "" if is_thought or rich else "&quot;"
    quote_close = "" if is_thought or rich else "&quot;"
    kind_badge = f'<div class="story-talk-kind" style="color:{color};">{kind_label}</div>'
    if slot == "left":
        body = (
            f'{kind_badge}<div class="story-speech"><span class="story-speaker-inline" style="color:{color};">{speaker}:</span> '
            f'<span class="story-quote">{quote_open}{text}{quote_close}</span></div>{target_html}'
        )
    elif slot == "right":
        body = (
            f'{kind_badge}<div class="story-speech"><span class="story-quote">{quote_open}{text}{quote_close}</span> '
            f'<span class="story-speaker-inline" style="color:{color};">:{speaker}</span></div>{target_html}'
        )
    else:
        body = (
            f'{kind_badge}<div class="story-speech story-center-speech"><span class="story-quote">{quote_open}{text}{quote_close}</span></div>'
            f'<div class="story-center-speaker" style="color:{color};">{speaker}</div>{target_html}'
        )
    safe_speaker = escape(speaker_raw, quote=True)
    return (
        f'<table class="story-talk-row {slot}{thought} speaker-{speaker_index % 12}" '
        f'data-story-speaker="{safe_speaker}" data-story-slot="{slot}" width="100%" cellpadding="0" cellspacing="0">'
        '<tr>'
        f'<td class="story-talk-buffer left-buffer" style="color:{color};">{left_buffer}</td>'
        f'<td class="story-talk-main" style="border-color:{color};">{body}</td>'
        f'<td class="story-talk-buffer right-buffer" style="color:{color};">{right_buffer}</td>'
        '</tr></table>'
    )


def _render_story_conversation(
    talks: list[dict[str, str]],
    theme: Theme,
    speaker_assignments: dict[str, tuple[str, int]],
    allow_online_links: bool = False,
) -> str:
    if not talks:
        return ""
    rows: list[str] = []
    previous_key = ""
    sequence_step = 0
    for item in talks:
        key = str(item.get("speaker", "TALKER")).strip().casefold() or "talker"
        if key == previous_key:
            sequence_step += 1
        else:
            sequence_step = 0
            previous_key = key
        slot, index = speaker_assignments[key]
        rows.append(_render_story_talk(
            item,
            theme,
            slot=slot,
            speaker_index=index,
            sequence_step=sequence_step,
            allow_online_links=allow_online_links,
        ))
    arc_color = _story_palette(theme)[0]
    return (
        f'<div class="story-conversation" style="border-color:{arc_color};">'
        '<table class="story-convo-rail-table" width="100%" cellspacing="0" cellpadding="0"><tr>'
        f'<td style="color:{arc_color};">!!</td><th style="color:{arc_color};">CONVO</th><td style="color:{arc_color};">!!</td>'
        '</tr></table>'
        + "".join(rows)
        + f'<div class="story-convo-end" style="color:{arc_color}; border-color:{arc_color};">CONVO END</div></div>'
    )


def _render_story_markup(value: str, theme: Theme, allow_online_links: bool = False) -> str:
    return (
        '<div class="story-script-markup"><div class="story-subtitle">SCRIPT MARKUP</div>'
        + _render_embedded_story_markup(value, theme, allow_online_links)
        + '</div>'
    )


def _render_story_directive(item: dict[str, str], theme: Theme) -> str:
    left = _story_inline(item.get("left", ""), theme)
    right = _story_inline(item.get("right", ""), theme)
    arrow = item.get("arrow", "->")
    glyph = {"->": "➜", "<-": "⬅", ">>": "⟹", "<<": "⇐"}.get(arrow, "➜")
    backward = arrow in {"<-", "<<"}
    direction = " backward" if backward else " forward"
    lingering = " lingering" if arrow in {">>", "<<"} else " instant"
    left_label = "RESULT / EFFECT" if backward else "ACTION / POINT"
    right_label = "ACTION / POINT" if backward else "RESULT / EFFECT"
    color = _story_palette(theme)[min(3, len(_story_palette(theme)) - 1)]
    return (
        f'<div class="story-directive{direction}{lingering}">'
        '<table class="story-directive-grid" width="100%" cellspacing="0" cellpadding="0"><tr>'
        f'<td class="story-directive-box story-left-box" style="border-color:{color};"><div class="story-directive-label">{left_label}</div>{left}</td>'
        f'<td class="story-directive-arrow" style="border-color:{color}; color:{color};" title="{escape(arrow)}">{glyph}</td>'
        f'<td class="story-directive-box story-right-box" style="border-color:{color};"><div class="story-directive-label">{right_label}</div>{right}</td>'
        '</tr></table></div>'
    )


def _render_story_notice(item: dict[str, str], theme: Theme) -> str:
    text = _story_inline(item.get("text", ""), theme)
    target = str(item.get("target", "")).strip()
    target_html = f'<div class="story-notice-target">DIRECTED TO: {_story_inline(target, theme)}</div>' if target else ""
    color = _story_palette(theme)[min(4, len(_story_palette(theme)) - 1)]
    return (
        f'<div class="story-notice" style="border-color:{color};">'
        f'<div class="story-notice-label" style="color:{color};">DIRECTIVE / PLOT POINT</div>{text}{target_html}</div>'
    )


def _render_story_option(item: dict[str, str], theme: Theme) -> str:
    mandatory = item.get("option_type") == "mandatory"
    cls = "story-option mandatory" if mandatory else "story-option interactable"
    label = "REQUIRED" if mandatory else "OPTION"
    marker = "◆" if mandatory else "◇"
    return f'<div class="{cls}"><span class="story-option-marker">{marker}</span><b>{label}</b><span>{_story_inline(item.get("text", ""), theme)}</span></div>'


def _render_story_data_table(items: list[dict[str, str]], theme: Theme) -> str:
    if not items:
        return '<div class="story-empty-section">No engine/common Arc Data tokens were detected.</div>'
    rows: list[str] = []
    for item in items:
        category = _story_inline(item.get("category", "Arc Data"), theme)
        label = _story_inline(item.get("label", "Data"), theme)
        value = _story_inline(item.get("text", ""), theme)
        rows.append(f'<tr><th>{category}</th><td class="story-data-label">{label}</td><td>{value}</td></tr>')
    return (
        '<div class="story-data-group">'
        '<table class="story-data-table" width="100%" cellspacing="0" cellpadding="0">'
        '<tr><th>GROUP</th><th>TYPE</th><th>VALUE</th></tr>'
        + "".join(rows)
        + '</table></div>'
    )


def _story_assign_speakers(elements: list[dict[str, str]]) -> dict[str, tuple[str, int]]:
    assignments: dict[str, tuple[str, int]] = {}
    used_initial: set[str] = set()
    for item in elements:
        if item.get("kind") != "talk":
            continue
        key = str(item.get("speaker", "TALKER")).strip().casefold() or "talker"
        if key in assignments:
            continue
        index = len(assignments)
        hint = str(item.get("side_hint", item.get("side", ""))).lower()
        if index < 2 and hint in {"left", "right"} and hint not in used_initial:
            slot = hint
        else:
            slot = ("left", "right", "center")[index % 3]
            if index < 3 and slot in used_initial:
                slot = next((candidate for candidate in ("left", "right", "center") if candidate not in used_initial), slot)
        assignments[key] = (slot, index)
        if index < 3:
            used_initial.add(slot)
    return assignments


def _render_story_flow(
    elements: list[dict[str, str]],
    theme: Theme,
    allow_online_links: bool = False,
) -> tuple[str, str, dict[str, int]]:
    visible: list[str] = []
    data_items: list[dict[str, str]] = []
    talk_buffer: list[dict[str, str]] = []
    speaker_assignments = _story_assign_speakers(elements)
    counts = {
        "speakers": len(speaker_assignments),
        "dialogue": 0,
        "thoughts": 0,
        "directives": 0,
        "plot": 0,
        "choices": 0,
        "markup": 0,
        "data": 0,
    }

    def flush_talks() -> None:
        nonlocal talk_buffer
        if talk_buffer:
            visible.append(_render_story_conversation(talk_buffer, theme, speaker_assignments, allow_online_links))
            talk_buffer = []

    for item in elements:
        kind = item.get("kind", "")
        if kind == "talk":
            if item.get("talk_type") == "thought":
                counts["thoughts"] += 1
            else:
                counts["dialogue"] += 1
            talk_buffer.append(item)
            continue
        flush_talks()
        if kind == "directive":
            counts["directives"] += 1
            visible.append(_story_arc_divider(compact=True, theme=theme))
            visible.append(_render_story_directive(item, theme))
            visible.append(_story_arc_divider(compact=True, theme=theme))
        elif kind in {"notice", "plot"}:
            counts["plot"] += 1
            visible.append(_story_arc_divider(compact=True, theme=theme))
            visible.append(_render_story_notice(item, theme))
            visible.append(_story_arc_divider(compact=True, theme=theme))
        elif kind == "markup":
            counts["markup"] += 1
            visible.append(_render_story_markup(item.get("text", ""), theme, allow_online_links))
        elif kind == "option":
            counts["choices"] += 1
            visible.append(_render_story_option(item, theme))
        elif kind == "data":
            counts["data"] += 1
            data_items.append(item)
    flush_talks()

    flow = "".join(visible) or '<div class="story-empty-section">No conversation, thought, directive, choice, or nested SWAR markup was detected in this Arc.</div>'
    return flow, _render_story_data_table(data_items, theme), counts


def _story_count_summary(counts: dict[str, int], theme: Theme) -> str:
    labels = (
        ("SPEAKERS", "speakers"),
        ("DIALOGUE", "dialogue"),
        ("THOUGHTS", "thoughts"),
        ("DIRECTIONS", "directives"),
        ("PLOT", "plot"),
        ("CHOICES", "choices"),
        ("SCRIPT", "markup"),
        ("DATA", "data"),
    )
    palette = _story_palette(theme)
    cells: list[str] = []
    for index, (label, key) in enumerate(labels):
        color = palette[index % len(palette)]
        cells.append(
            f'<td class="story-count-cell" style="border-color:{color};">'
            f'<div class="story-count-number" style="color:{color};">{int(counts.get(key, 0))}</div>'
            f'<div class="story-count-label">{label}</div></td>'
        )
    return '<table class="story-count-table" width="100%" cellspacing="4" cellpadding="0"><tr>' + "".join(cells) + '</tr></table>'


def _story_section_key(line: int, section: str) -> str:
    return f"{max(1, int(line))}:{section}"


def _render_story_section(
    *,
    line: int,
    section: str,
    title: str,
    body: str,
    theme: Theme,
    collapsed_sections: set[str] | None,
    subtitle: str = "",
    color_index: int = 0,
) -> str:
    interactive = collapsed_sections is not None
    key = _story_section_key(line, section)
    collapsed = bool(interactive and key in collapsed_sections)
    palette = _story_palette(theme)
    color = palette[color_index % len(palette)]
    marker = "+" if collapsed else "−"
    subtitle_html = f'<span class="story-section-subtitle">{escape(subtitle)}</span>' if subtitle else ""
    if interactive:
        heading = (
            f'<a href="storytoggle:{max(1, int(line))}:{quote(section, safe="")}" '
            f'class="story-section-toggle" style="color:{color}; text-decoration:none;">'
            f'<b>{marker}&nbsp;&nbsp;{escape(title)}</b>{subtitle_html}</a>'
        )
    else:
        heading = f'<span class="story-section-toggle" style="color:{color};"><b>{escape(title)}</b>{subtitle_html}</span>'
    header = (
        f'<table class="story-section-header" data-story-section="{escape(section, quote=True)}" '
        f'width="100%" cellspacing="0" cellpadding="0" style="border-color:{color};">'
        f'<tr><td>{heading}</td><td class="story-section-state" style="color:{color};">'
        f'{"COLLAPSED" if collapsed else "OPEN"}</td></tr></table>'
    )
    if collapsed:
        return header + '<div class="story-section-collapsed">Click the section title to expand.</div>'
    return header + f'<div class="story-section-body" style="border-color:{color};">{body}</div>'


def _render_arc_record(
    block: Block,
    theme: Theme,
    allow_online_links: bool = False,
    *,
    story_collapsed: set[str] | None = None,
) -> str:
    attrs = block.attrs
    name_raw = str(attrs.get("name", block.text or "Untitled Arc"))
    name = _story_inline(name_raw, theme)
    estimated = _story_inline(str(attrs.get("estimated", "0:0:0")), theme)
    zone = _story_inline(str(attrs.get("zone_type", "Safe")), theme)
    map_ref = _story_inline(str(attrs.get("map_ref", "")), theme)
    start = _render_embedded_story_markup(str(attrs.get("start_message", "")), theme, allow_online_links)
    confirm = _render_embedded_story_markup(str(attrs.get("confirm_message", "")), theme, allow_online_links)
    elements = list(attrs.get("story_elements", []))
    flow, data_html, counts = _render_story_flow(elements, theme, allow_online_links)
    warnings = list(attrs.get("record_warnings", []))
    warning_html = ""
    if warnings:
        warning_html = '<div class="arc-warnings">' + '<br>'.join(escape(str(item)) for item in warnings) + '</div>'
    raw_data = str(attrs.get("arc_data", ""))
    if not elements and raw_data:
        flow = (
            '<div class="story-unparsed-warning"><b>UNPARSED ARC DATA</b><br>'
            'The source is preserved below so conversation or markup syntax cannot disappear silently.</div>'
            f'<div class="arc-data">{_story_inline(raw_data, theme)}</div>'
        )

    line = max(1, int(block.line_start))
    interactive = story_collapsed is not None
    controls = ""
    if interactive:
        controls = (
            '<div class="story-arc-controls">'
            f'<a href="storyexpand:{line}">EXPAND ALL</a>&nbsp;&nbsp;|&nbsp;&nbsp;'
            f'<a href="storycollapse:{line}">COLLAPSE ALL</a>'
            '</div>'
        )
    opening_section = _render_story_section(
        line=line, section="opening", title="OPENING / SETUP", body=start,
        theme=theme, collapsed_sections=story_collapsed,
        subtitle="Nested .script markup supported", color_index=1,
    )
    flow_section = _render_story_section(
        line=line, section="flow", title="PLAY / READ STORY FLOW", body=flow,
        theme=theme, collapsed_sections=story_collapsed,
        subtitle="Conversation • thoughts • directions • choices • nested markup", color_index=2,
    )
    data_section = _render_story_section(
        line=line, section="data", title="AUTHOR / ENGINE DATA", body=data_html,
        theme=theme, collapsed_sections=story_collapsed,
        subtitle="Bindings • entities • rates • locations • relay phrases", color_index=3,
    )
    completion_section = _render_story_section(
        line=line, section="completion", title="COMPLETION / OUTCOME", body=confirm,
        theme=theme, collapsed_sections=story_collapsed,
        subtitle="Nested .script markup supported", color_index=4,
    )
    arc_color = _story_palette(theme)[0]
    return (
        _story_arc_divider(theme=theme)
        + f'<section class="arc-card story-screenplay-card" data-swar-line="{line}" '
          f'data-arc-name="{escape(name_raw, quote=True)}" style="border-color:{arc_color};">'
          f'<div class="arc-title" style="border-color:{arc_color};">{name}</div>'
          f'{controls}'
          '<table class="story-base-table" width="100%" cellspacing="0" cellpadding="0">'
          f'<tr><th>ESTIMATE</th><td>{estimated}</td><th>ZONE</th><td>{zone}</td></tr>'
          f'<tr><th>MAP</th><td colspan="3">{map_ref}</td></tr>'
          f'<tr><th>SOURCE</th><td colspan="3">ARCS LINE {line}</td></tr>'
          '</table>'
          f'{_story_count_summary(counts, theme)}'
          f'{opening_section}{flow_section}{data_section}{completion_section}'
          f'{warning_html}'
          '</section>'
        + _story_arc_divider(theme=theme)
    )

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


_INLINE_ARROW_RE = re.compile(
    r"\^-&gt;|[vV]-&gt;|&lt;-[vV]|&lt;-\^|\^-\^|[vV]-[vV]|-&gt;|&lt;-"
)
_INLINE_ARROW_MAP = {
    "^-&gt;": "↗", "v-&gt;": "↘", "V-&gt;": "↘",
    "&lt;-v": "↙", "&lt;-V": "↙", "&lt;-^": "↖",
    "^-^": "↑", "v-v": "↓", "V-V": "↓",
    "-&gt;": "→", "&lt;-": "←",
}


def _replace_inline_arrows(staged: str) -> str:
    """Replace arrow aliases only after real content on the same rendered line."""
    def replace(match: re.Match[str]) -> str:
        prefix = staged[:match.start()]
        if not prefix.strip():
            return match.group(0)
        return _INLINE_ARROW_MAP.get(match.group(0), match.group(0))
    return _INLINE_ARROW_RE.sub(replace, staged)


def _protect_super_sub_markup(staged: str, depth: int = 0) -> tuple[str, list[str]]:
    """Protect SWAR super/sub markup before the Markdown pass.

    This is a left-to-right scanner instead of a sequence of global regular
    expressions.  The scanner consumes the outermost construct before looking
    at later text, preventing one super/sub group from stealing delimiters that
    belong to a following group on the same line.
    """
    tokens: list[str] = []

    def hold(html: str) -> str:
        tokens.append(html)
        return f"@@SWAR_SCRIPT_{len(tokens) - 1}@@"

    def render_inner(value: str) -> str:
        if not value or depth >= 4:
            return value
        inner, held = _protect_super_sub_markup(value, depth + 1)
        for index, html in enumerate(held):
            inner = inner.replace(f"@@SWAR_SCRIPT_{index}@@", html)
        return inner

    def wrapped(tag: str, value: str, *, keep_prefix: str = "") -> str:
        return hold(f"<{tag}>{keep_prefix}{render_inner(value)}</{tag}>")

    def match_cross(position: int, first: str) -> tuple[int, str] | None:
        if first == "#":
            match = re.match(r"#([^#!\n]+?)!!([^#!\n]+?)#", staged[position:])
            if not match:
                return None
            html = (
                f"<sup>{render_inner(match.group(1).strip())}</sup> "
                f"<sub>{render_inner(match.group(2).strip())}</sub>"
            )
        else:
            match = re.match(r"!!([^!#\n]+?)#([^!#\n]+?)!!", staged[position:])
            if not match:
                return None
            html = (
                f"<sub>{render_inner(match.group(1).strip())}</sub> "
                f"<sup>{render_inner(match.group(2).strip())}</sup>"
            )
        return position + match.end(), hold(html)

    def match_chain(position: int, delim: str, tag: str) -> tuple[int, str] | None:
        """Match compact multi-groups such as ``#a#b#c#``.

        Chain groups intentionally stay compact (no whitespace inside a group)
        so ordinary prose containing separated hash/exclamation punctuation is
        not captured as one giant construct.
        """
        cursor = position + len(delim)
        segments: list[str] = []
        while cursor < len(staged):
            close = staged.find(delim, cursor)
            if close < 0:
                return None
            segment = staged[cursor:close]
            if not segment or any(ch.isspace() for ch in segment):
                return None
            if (delim == "#" and "!" in segment) or (delim == "!!" and "#" in segment):
                return None
            segments.append(segment)
            end = close + len(delim)
            # A chain needs at least two wrapped values.  Continue while the
            # next character starts another compact value; otherwise this is
            # the closing delimiter for the complete chain.
            if len(segments) >= 2 and (
                end >= len(staged)
                or staged[end].isspace()
                or staged[end] in ",.;:!?)]}<>/\\-+="
            ):
                html = " ".join(f"<{tag}>{render_inner(part)}</{tag}>" for part in segments)
                return end, hold(html)
            cursor = end
        return None

    out: list[str] = []
    i = 0
    while i < len(staged):
        # HTML entities contain a literal '#', for example ``&#39;``.  They
        # must never be interpreted as SWAR markup.
        if staged.startswith("#", i) and i > 0 and staged[i - 1] == "&":
            out.append("#")
            i += 1
            continue

        marker = "!!" if staged.startswith("!!", i) else "#" if staged.startswith("#", i) else ""
        if not marker:
            out.append(staged[i])
            i += 1
            continue

        # Do not begin a prefix form in the middle of an alphanumeric token.
        if i > 0 and (staged[i - 1].isalnum() or staged[i - 1] == "_"):
            out.append(marker)
            i += len(marker)
            continue

        # One bounded level of true nesting is supported by choosing an outer
        # closing marker that is at a token boundary. Examples:
        # ``#outer !!inner#!!`` and ``!!outer #inner!!#``.
        outer_close = "!!" if marker == "#" else "#"
        search_at = i + len(marker)
        nested_match: tuple[int, str] | None = None
        while True:
            close_at = staged.find(outer_close, search_at)
            if close_at < 0:
                break
            close_end = close_at + len(outer_close)
            boundary = close_end >= len(staged) or not (
                staged[close_end].isalnum() or staged[close_end] == "_"
            )
            content = staged[i + len(marker):close_at]
            if boundary and content and len(content) <= 240:
                # Avoid swallowing later independent groups. One nested opposite
                # opener/closer is allowed inside the outer wrapper.
                if marker == "#":
                    safe_shape = content.count("!!") <= 1 and content.count("#") <= 1
                else:
                    safe_shape = content.count("#") <= 1 and content.count("!!") <= 1
                if safe_shape:
                    nested_match = (
                        close_end,
                        wrapped("sub" if marker == "!!" else "sup", content.strip()),
                    )
                    break
            search_at = close_at + len(outer_close)
        if nested_match is not None:
            i, token = nested_match
            out.append(token)
            continue

        cross = match_cross(i, marker)
        if cross is not None:
            i, token = cross
            out.append(token)
            continue

        chain = match_chain(i, marker, "sub" if marker == "!!" else "sup")
        if chain is not None:
            i, token = chain
            out.append(token)
            continue

        if marker == "#":
            # ``#value!!`` hides both wrappers and superscripts value.
            close = staged.find("!!", i + 1)
            competing = staged.find("#", i + 1)
            close_boundary = close >= 0 and (
                close + 2 >= len(staged)
                or not (staged[close + 2].isalnum() or staged[close + 2] == "_")
            )
            if close_boundary and (competing < 0 or close < competing):
                value = staged[i + 1:close]
                if value and "\n" not in value:
                    out.append(wrapped("sup", value.strip()))
                    i = close + 2
                    continue
        else:
            # ``!!value#`` hides both wrappers and subscripts value.
            close = staged.find("#", i + 2)
            competing = staged.find("!!", i + 2)
            close_boundary = close >= 0 and (
                close + 1 >= len(staged)
                or not (staged[close + 1].isalnum() or staged[close + 1] == "_")
            )
            if close_boundary and (competing < 0 or close < competing):
                value = staged[i + 2:close]
                if value and "\n" not in value:
                    out.append(wrapped("sub", value.strip()))
                    i = close + 1
                    continue

        # Slash-prefix forms hide the leading marker and continue until space.
        slash_pattern = r"!!([^\s!]+/[^\s]+)" if marker == "!!" else r"#([^\s#]+/[^\s]+)"
        slash_match = re.match(slash_pattern, staged[i:])
        if slash_match:
            out.append(wrapped("sub" if marker == "!!" else "sup", slash_match.group(1)))
            i += slash_match.end()
            continue

        # Ordinary prefix forms keep their visible marker inside the script.
        prefix_pattern = r"!!([A-Za-z0-9][^\s!]*)" if marker == "!!" else r"#([A-Za-z0-9][^\s#]*)"
        prefix_match = re.match(prefix_pattern, staged[i:])
        if prefix_match:
            out.append(wrapped(
                "sub" if marker == "!!" else "sup",
                prefix_match.group(1),
                keep_prefix=marker,
            ))
            i += prefix_match.end()
            continue

        out.append(marker)
        i += len(marker)

    return "".join(out), tokens


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

    staged = _replace_inline_arrows(staged)
    staged, script_tokens = _protect_super_sub_markup(staged)

    staged = re.sub(r"___(.+?)___", r"<u>\1</u>", staged)
    staged = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", staged)
    staged = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", staged)
    staged = re.sub(r"__(.+?)__", r"<strong>\1</strong>", staged)
    staged = re.sub(r"~~(.+?)~~", r"<del>\1</del>", staged)
    staged = re.sub(r"(?<!~)~(?!~)(.+?)(?<!~)~(?!~)", r"<del>\1</del>", staged)
    staged = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", staged)

    for index, value in enumerate(script_tokens):
        staged = staged.replace(f"@@SWAR_SCRIPT_{index}@@", value)
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
.indent-four {{ border-left:3px dotted {theme.border}; padding-left:14px; }}
.swar-vertical-gap {{ display:block; min-height:1px; }}
.page-break-gap {{ border-top:1px dotted {theme.border}; border-bottom:1px dotted {theme.border}; }}
.golden-line {{ background:{theme.panel}; border-radius:8px; padding:8px 12px; margin:10px 0; font-weight:850; }}
.golden-prefix {{ color:{theme.text}; }}
.golden-dim .golden-highlight {{ color:{DIM_GOLD}; }}
.golden-bright {{ color:{BRIGHT_GOLD}; border:2px solid {BRIGHT_GOLD}; text-align:center; font-size:20px; }}
.attention-red {{ color:{ATTN_RED}; border-left:8px solid {ATTN_RED}; border-right:8px solid {ATTN_RED}; background:{theme.panel}; padding:10px 14px; margin:12px 0; font-weight:1000; text-align:center; }}
.attention-arrows {{ letter-spacing:2px; }}
.story-arc-divider {{ margin:28px 0 18px; border-collapse:separate; border-spacing:0; }}
.story-arc-divider .story-divider-line {{ border-bottom:4px double currentColor; width:43%; }}
.story-arc-divider th {{ padding:0 14px 5px; font-weight:1000; letter-spacing:2px; white-space:nowrap; }}
.story-arc-divider.compact {{ margin:30px 6% 26px; opacity:0.92; }}
.story-arc-divider.compact .story-divider-line {{ border-bottom-width:2px; border-bottom-style:solid; }}
.story-arc-divider.compact th {{ font-size:12px; letter-spacing:1.4px; }}
.arc-card {{ border:4px solid; border-radius:14px; background:{theme.panel}; margin:18px 0 26px; padding:12px; }}
.story-screenplay-card {{ box-shadow:0 0 0 2px {theme.border} inset; }}
.arc-title {{ color:{theme.title}; text-align:center; font-size:28px; font-weight:1000; border-bottom:2px solid; padding:6px; }}
.story-arc-controls {{ text-align:center; font-size:12px; letter-spacing:0.9px; padding:8px 0 3px; }}
.story-arc-controls a {{ color:{theme.highlight}; }}
.story-base-table, .story-data-table {{ width:100%; border-collapse:collapse; margin:10px 0 16px; background:{theme.bg}; font-family:"DejaVu Sans Mono", monospace; }}
.story-base-table th, .story-base-table td, .story-data-table th, .story-data-table td {{ border:1px solid {theme.border}; padding:7px 9px; vertical-align:top; }}
.story-base-table th, .story-data-table th {{ color:{theme.highlight3}; background:{theme.panel}; text-align:left; font-size:13px; letter-spacing:0.7px; }}
.story-base-table td {{ color:{theme.text}; }}
.story-data-label {{ color:{theme.highlight}; font-weight:800; white-space:nowrap; }}
.story-count-table {{ width:100%; table-layout:fixed; margin:8px 0 16px; }}
.story-count-cell {{ border:1px solid; background:{theme.bg}; text-align:center; padding:7px 2px; vertical-align:middle; }}
.story-count-number {{ font-size:20px; font-weight:1000; }}
.story-count-label {{ color:{theme.muted}; font-size:9px; font-weight:900; letter-spacing:0.4px; }}
.story-section-header {{ width:100%; border:2px solid; border-collapse:collapse; background:{theme.bg}; margin-top:13px; }}
.story-section-header td {{ padding:9px 11px; vertical-align:middle; }}
.story-section-toggle {{ display:block; font-size:14px; font-weight:1000; letter-spacing:1px; }}
.story-section-subtitle {{ color:{theme.muted}; font-size:10px; font-weight:700; letter-spacing:0.2px; padding-left:12px; }}
.story-section-state {{ width:74px; text-align:right; font-size:10px; font-weight:900; letter-spacing:0.8px; white-space:nowrap; }}
.story-section-body {{ border-left:2px solid; border-right:2px solid; border-bottom:2px solid; background:{theme.panel}; padding:12px; margin-bottom:12px; }}
.story-section-collapsed {{ color:{theme.muted}; border-left:2px dotted {theme.border}; padding:6px 12px 10px; margin-bottom:10px; font-size:12px; font-style:italic; }}
.arc-stage, .arc-data, .arc-map {{ border-left:5px solid {theme.highlight4}; background:{theme.bg}; margin:12px 0; padding:10px 12px; }}
.arc-complete {{ border-left-color:{GREEN_ARROW}; }}
.arc-start {{ border-left-color:{BRIGHT_GOLD}; }}
.story-stage-label, .story-subtitle {{ color:{theme.highlight3}; font-weight:1000; text-align:center; letter-spacing:1.2px; padding:3px 0 8px; }}
.arc-stage .header-card {{ margin:4px 0 12px; }}
.arc-stage .arrow-title, .arc-stage .arrow-descriptor, .arc-stage .arrow-major {{ margin-left:0 !important; }}
.story-conversation {{ border:3px solid; border-radius:12px; background:{theme.bg}; padding:0 10px 10px; margin:20px 0; overflow:hidden; }}
.story-convo-rail-table {{ width:100%; border-collapse:collapse; border-bottom:3px double {theme.border}; margin-bottom:12px; }}
.story-convo-rail-table th {{ text-align:center; padding:8px; letter-spacing:4px; font-size:17px; }}
.story-convo-rail-table td {{ width:54px; text-align:center; font-size:24px; font-weight:1000; padding:8px; }}
.story-convo-end {{ border-top:3px double; text-align:center; font-weight:1000; letter-spacing:3px; padding:9px 6px 1px; margin:12px -10px 0; }}
.story-talk-row {{ width:100%; border-collapse:separate; border-spacing:0; margin:11px 0; table-layout:fixed; }}
.story-talk-main {{ background:{theme.panel}; border:2px solid {theme.border}; padding:11px 14px; vertical-align:middle; }}
.story-talk-row.left .story-talk-main {{ border-left-width:7px; border-radius:10px 0 0 10px; text-align:left; }}
.story-talk-row.right .story-talk-main {{ border-right-width:7px; border-radius:0 10px 10px 0; text-align:right; }}
.story-talk-row.center .story-talk-main {{ border-left-width:5px; border-right-width:5px; border-radius:10px; text-align:center; }}
.story-talk-row.thought .story-talk-main {{ border-style:dashed; font-style:italic; background:{theme.bg}; }}
.story-talk-buffer {{ width:46px; font-size:31px; font-weight:1000; text-align:center; vertical-align:middle; }}
.story-talk-kind {{ font-size:10px; font-weight:1000; letter-spacing:1.3px; margin-bottom:6px; }}
.story-speaker-inline {{ font-size:15px; font-weight:1000; letter-spacing:0.8px; }}
.story-speech {{ color:{theme.text}; font-size:21px; line-height:1.55; }}
.story-speech .important-table, .story-speech .fancy-box {{ margin-left:0 !important; }}
.story-speech .header-card {{ margin:5px 0; padding:8px; }}
.story-embedded-plain {{ padding:3px 4px; margin:3px 0 8px; }}
.story-center-speaker {{ font-size:14px; font-weight:1000; letter-spacing:1.5px; margin-top:7px; text-align:center; }}
.story-talk-target {{ color:{theme.muted}; font-size:12px; margin-top:7px; font-family:"DejaVu Sans Mono", monospace; }}
.story-script-markup {{ border:2px dotted {theme.highlight3}; background:{theme.bg}; border-radius:10px; padding:10px 12px; margin:20px 0; }}
.story-script-markup .important-table, .story-script-markup .fancy-box {{ margin-left:0 !important; }}
.story-notice {{ text-align:center; color:{theme.text}; border:2px solid; background:{theme.panel}; border-radius:10px; padding:12px 16px; margin:46px 8%; line-height:1.65; }}
.story-notice-label {{ font-size:12px; font-weight:1000; letter-spacing:1.2px; margin-bottom:8px; }}
.story-notice-target {{ color:{theme.muted}; font-size:12px; margin-top:8px; }}
.story-directive {{ margin:48px 0; padding:4px 0; }}
.story-directive-grid {{ border-collapse:separate; border-spacing:0; table-layout:fixed; position:relative; }}
.story-directive-box {{ border:2px solid; background:{theme.panel}; padding:13px; min-height:64px; text-align:center; vertical-align:middle; }}
.story-left-box {{ border-radius:11px 0 0 11px; }}
.story-right-box {{ border-radius:0 11px 11px 0; }}
.story-directive-label {{ color:{theme.muted}; font-size:11px; font-weight:900; letter-spacing:1px; margin-bottom:7px; }}
.story-directive-arrow {{ position:relative; z-index:3; width:58px; min-width:58px; height:58px; line-height:58px; text-align:center; vertical-align:middle; border-radius:50%; border:3px solid; background:{theme.bg}; font-size:34px; font-weight:1000; }}
.story-option {{ border:2px solid {theme.highlight4}; background:{theme.panel}; padding:9px 12px; margin:10px 5%; border-radius:9px; }}
.story-option b {{ color:{theme.highlight4}; padding:0 12px; }}
.story-option-marker {{ color:{theme.highlight4}; font-size:22px; padding-right:8px; }}
.story-option.mandatory {{ border-color:{ATTN_RED}; }}
.story-option.mandatory b, .story-option.mandatory .story-option-marker {{ color:{ATTN_RED}; }}
.story-data-group {{ margin:4px 0; }}
.story-empty-section {{ color:{theme.muted}; text-align:center; font-style:italic; padding:16px; border:1px dotted {theme.border}; }}
.story-unparsed-warning {{ color:{ATTN_RED}; border:2px dashed {ATTN_RED}; background:{theme.bg}; padding:10px; margin:8px 0; text-align:center; }}
.arc-empty {{ color:{theme.muted}; font-style:italic; }}
.arc-warnings {{ color:{ATTN_RED}; border:1px dashed {ATTN_RED}; padding:7px; margin-top:8px; }}
sup {{ font-size:72%; vertical-align:super; line-height:0; color:{theme.highlight3}; }}
sub {{ font-size:72%; vertical-align:sub; line-height:0; color:{theme.highlight4}; }}
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
