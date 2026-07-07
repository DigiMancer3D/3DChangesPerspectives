from __future__ import annotations

from html import escape
import re
from urllib.parse import quote

from .parser import ScriptDoc, Block
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

        html = render_block(block, theme, allow_online_links=allow_online_links)
        if html:
            parts.append(html)

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

def render_block(block: Block, theme: Theme, allow_online_links: bool = False) -> str:
    kind = block.kind
    text = block.text or ""
    margin = min(80, max(0, block.level * 22))

    if kind == "blank":
        return '<div class="blank"></div>'

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
        body_html = _format_important_html(text)
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

    if kind in {"markdown_check_item", "markdown_num_item", "markdown_money_item", "markdown_bullet_item"}:
        labels = {
            "markdown_check_item": "☐",
            "markdown_num_item": "#",
            "markdown_money_item": escape(block.attrs.get("marker", "$")),
            "markdown_bullet_item": "+",
        }
        return f'<div class="md-list-item {kind}" style="margin-left:{margin}px"><span class="md-list-mark">{labels[kind]}</span> {_inline_markdown(escape(text), theme)}</div>'

    if kind == "markdown_percent_list":
        return _render_percent_list(block, theme)

    if kind == "markdown_heading":
        level = int(block.attrs.get("heading_level", 1))
        tag = f"h{min(max(level, 1), 6)}"
        cls = "md-heading md-caption" if level >= 6 else "md-heading"
        return f'<{tag} class="{cls}">{_inline_markdown(escape(text), theme)}</{tag}>'

    if kind == "markdown_table":
        return _render_markdown_table(text, theme)

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


def _format_important_html(text: str) -> str:
    lines = text.splitlines() or [text]
    out: list[str] = []
    for i, line in enumerate(lines):
        clean = line.strip().strip('"')
        if not clean:
            continue
        words = clean.split()
        if not words:
            continue
        line_text = escape(" ".join(words))
        # Each important line is centered and word-spaced instead of relying on fixed screen width.
        out.append(f'<div class="important-line important-line-{min(i, 8)}">{line_text}</div>')
    return "\n".join(out) if out else '<div class="important-line"></div>'


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
        out.append(f'<div class="md-percent-item {cls}"><span class="pct">{pct}%</span><span class="pct-label">{_inline_markdown(label, theme)}</span><span class="pct-bar"><span style="width:{width}%"></span></span></div>')
    out.append('</div>')
    return "\n".join(out)


def _render_markdown_table(raw: str, theme: Theme) -> str:
    rows = []
    for line in raw.splitlines():
        stripped = line.strip().strip("|")
        cells = [escape(c.strip()) for c in stripped.split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c.strip()) for c in stripped.split("|")):
            continue
        rows.append(cells)
    if not rows:
        return ""
    html = ['<table class="md-table">']
    for r, cells in enumerate(rows):
        tag = "th" if r == 0 else "td"
        html.append("<tr>" + "".join(f"<{tag}>{_inline_markdown(c, theme)}</{tag}>" for c in cells) + "</tr>")
    html.append("</table>")
    return "\n".join(html)


def _inline_markdown(safe_text: str, theme: Theme) -> str:
    # Input must already be HTML-escaped. Lightweight GitHub-ish inline handling for reader mode.
    safe_text = re.sub(r"___(.+?)___", r"<u>\1</u>", safe_text)
    safe_text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", safe_text)
    safe_text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", safe_text)
    safe_text = re.sub(r"__(.+?)__", r"<strong>\1</strong>", safe_text)
    safe_text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", safe_text)
    safe_text = re.sub(r"`([^`]+)`", r"<code>\1</code>", safe_text)
    return safe_text


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
.down-arrows {{ text-align:center; color:{theme.highlight}; font-size:30px; letter-spacing: 6px; font-weight:900; margin: 2px 0 18px 0; }}
.md-heading {{ color:{theme.markdown_heading}; border-bottom: 2px solid {theme.border}; padding-bottom: 5px; }}
.md-table {{ margin: 18px auto; border-collapse: collapse; color:{theme.text}; background:{theme.panel}; }}
.md-table th, .md-table td {{ border: 1px solid {theme.markdown_table}; padding: 8px 12px; }}
.md-table th {{ color:{theme.markdown_table}; font-weight:900; }}
.md-caption {{ text-align:right; font-size:14px; color:{theme.muted}; border-bottom:0; font-style:italic; }}
.md-blockquote {{ border-left: 8px solid {theme.highlight}; background:{theme.panel}; margin: 18px auto; padding: 14px 18px; max-width: 86%; border-radius: 0 12px 12px 0; color:{theme.text}; }}
.md-blockquote.nested {{ border-left-color:{theme.highlight4}; margin-left: 48px; max-width: 80%; }}
.md-list-item {{ background:{theme.panel}; border-left:5px solid {theme.highlight5}; margin:8px 0; padding:8px 12px; border-radius: 0 10px 10px 0; }}
.md-list-mark {{ color:{theme.highlight}; font-weight:900; display:inline-block; min-width: 32px; }}
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
code {{ background:{theme.bg}; color:{theme.highlight}; padding:2px 5px; border-radius:4px; }}
.warnings {{ border:2px solid #cc0000; color:#ff6666; padding:10px; margin:16px 0; }}
</style></head><body>'''
