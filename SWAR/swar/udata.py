from __future__ import annotations

from dataclasses import dataclass, field, fields, replace
from pathlib import Path
import re

from .themes import DEFAULT_THEME, THEMES

END_CHARS = set(".,;/\\|{}[]!")
SECTION_HEADERS = {"HEADER", "PRE-BODY", "BODY", "POST-BODY", "TOP-FOOTER", "BOTTOM-FOOTER"}


DEFAULT_UDATA_TEXT = """# SWAR.udata - ABI-style persistence for Script Writer and Reader.
# Unknown variables are preserved by SWAR when possible and ignored when not recognized.

HEADER:
current_theme:Dark Mode.
current_mode:standard.
reader_network_policy:local_only.
editor_network_policy:ask.
last_file:abc.
last_tab_index:0.

PRE-BODY:
default_theme:Dark Mode.
default_extension:script.
outline_export_links_only:true.
mask_header_secrets:true.

BODY:
theme.Light Mode.bg:#f9fbff.
theme.Light Mode.text:#001a44.
theme.Light Mode.link:#8000aa.
theme.Light Mode.highlight:#ff9900.
theme.Dark Mode.bg:#000000.
theme.Dark Mode.text:#c0c0c0.
theme.Dark Mode.link:#39ff14.
theme.Dark Mode.highlight:#d0d0d0.
theme.Paper Mode.bg:#F5F5F0.
theme.Paper Mode.text:#245c9e.
theme.Paper Mode.link:#b00020.
theme.Paper Mode.highlight:#7a3fb0.
theme.Terminal Mode.bg:#000000.
theme.Terminal Mode.text:#39ff14.
theme.Terminal Mode.link:#ff9900.
theme.Terminal Mode.highlight:#d0d0d0.
theme.Blue Mode.bg:#00172d.
theme.Blue Mode.text:#ffffff.
theme.Blue Mode.link:#ff9900.
theme.Blue Mode.highlight:#444444.
section.important.color:#ff9900.
section.source.color:#2f7acc.
section.data.color:#6aa4ff.
section.verbatim.color:#dddddd.
section.title.color:#ffffff.
section.descriptor.color:#cc99ff.
section.explainer.color:#ffaa44.
section.major_explainer.color:#ffcc66.
markdown.heading.color:#88aaff.
markdown.table.color:#cccccc.
# Custom snippets can be added as snippet.<DropdownGroup>.<Label>:text with \n for new lines.
# Example disabled markers abc/xyz are ignored until replaced.
snippet.Template.abc:abc.
snippet.Sections.xyz:xyz.

POST-BODY:
last_window_width:1180.
last_window_height:720.
last_scroll_percent:0.

TOP-FOOTER:
startup_count:0.
save_count:0.
reader_launch_count:0.
standard_launch_count:0.

BOTTOM-FOOTER:
recent_files:[abc].
custom_theme_memory:[xyz].
"""


@dataclass
class UData:
    path: Path
    values: dict[str, str] = field(default_factory=dict)
    lines: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: str | Path) -> "UData":
        path = Path(path)
        if not path.exists():
            path.write_text(DEFAULT_UDATA_TEXT, encoding="utf-8")
        text = path.read_text(encoding="utf-8", errors="replace")
        obj = cls(path=path, lines=text.splitlines())
        obj._parse()
        return obj

    def _parse(self) -> None:
        current_section = ""
        for line in self.lines:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if stripped.endswith(":") and stripped[:-1] in SECTION_HEADERS:
                current_section = stripped[:-1]
                continue
            if ":" not in stripped:
                continue
            name, raw_value = stripped.split(":", 1)
            name = name.strip()
            value = raw_value.strip()
            value = _strip_terminal(value)
            if name:
                self.values[name] = value
                if current_section:
                    self.values[f"{current_section}.{name}"] = value

    def get(self, name: str, default: str = "") -> str:
        return self.values.get(name, default)

    def get_theme_name(self) -> str:
        name = self.get("current_theme", DEFAULT_THEME)
        return name if name in THEMES else DEFAULT_THEME

    def bump_counter(self, name: str) -> None:
        # TOP-FOOTER counters can only increase by +1 per call.
        old = self.values.get(name, "0")
        try:
            new = str(int(old) + 1)
        except ValueError:
            new = "1"
        self.set(name, new, section="TOP-FOOTER")

    def set(self, name: str, value: str, section: str = "POST-BODY") -> None:
        if section not in SECTION_HEADERS:
            section = "POST-BODY"
        pattern = re.compile(rf"^(\s*{re.escape(name)}\s*:\s*)(.*)$")
        found = False
        active_section = ""
        for i, line in enumerate(self.lines):
            stripped = line.strip()
            if stripped.endswith(":") and stripped[:-1] in SECTION_HEADERS:
                active_section = stripped[:-1]
                continue
            if active_section == section and pattern.match(line.strip()):
                prefix = line.split(":", 1)[0] + ":"
                self.lines[i] = f"{prefix}{value}."
                found = True
                break
        if not found:
            insert_at = len(self.lines)
            for i, line in enumerate(self.lines):
                if line.strip() == f"{section}:":
                    insert_at = i + 1
                    while insert_at < len(self.lines):
                        s = self.lines[insert_at].strip()
                        if s.endswith(":") and s[:-1] in SECTION_HEADERS:
                            break
                        insert_at += 1
                    break
            self.lines.insert(insert_at, f"{name}:{value}.")
        self.values[name] = value
        self.values[f"{section}.{name}"] = value

    def apply_theme_overrides(self) -> int:
        """Apply safe color overrides from SWAR.udata to the runtime theme map.

        Supported variable form:
            theme.Dark Mode.text:#c0c0c0.
            theme.NIGHT.highlight:#ff9900.   # display aliases are accepted too

        Unknown fields and invalid colors are ignored so shared *.udata files
        remain safe across different SWAR versions.
        """
        from . import themes as theme_module

        alias = {
            "LIGHT": "Light Mode",
            "NIGHT": "Dark Mode",
            "PAPER": "Paper Mode",
            "TERM": "Terminal Mode",
            "OCEAN": "Blue Mode",
        }
        allowed_fields = {f.name for f in fields(theme_module.Theme)} - {"name"}
        grouped: dict[str, dict[str, str]] = {}

        # Global section/markdown color variables are intentionally shared across themes.
        # They keep Script Markup colors consistent even when a theme highlight color is
        # deliberately neutral, such as Dark Mode's grey highlight.
        global_color_map = {
            "section.important.color": "important",
            "section.source.color": "source",
            "section.data.color": "data",
            "section.verbatim.color": "verbatim",
            "section.title.color": "section_title",
            "section.descriptor.color": "descriptor",
            "section.explainer.color": "explainer",
            "section.major_explainer.color": "major_explainer",
            "markdown.heading.color": "markdown_heading",
            "markdown.table.color": "markdown_table",
        }
        global_overrides: dict[str, str] = {}
        for key, field_name in global_color_map.items():
            value = self.values.get(key, "")
            if field_name in allowed_fields and _valid_color(value):
                global_overrides[field_name] = value

        for key, value in self.values.items():
            if not key.startswith("theme."):
                continue
            parts = key.split(".")
            if len(parts) < 3:
                continue
            field_name = parts[-1]
            theme_key = ".".join(parts[1:-1])
            theme_name = alias.get(theme_key, theme_key)
            if theme_name not in theme_module.THEMES or field_name not in allowed_fields:
                continue
            if not _valid_color(value):
                continue
            grouped.setdefault(theme_name, {})[field_name] = value

        changed = 0
        for theme_name in list(theme_module.THEMES.keys()):
            overrides = dict(global_overrides)
            overrides.update(grouped.get(theme_name, {}))
            if overrides:
                theme_module.THEMES[theme_name] = replace(theme_module.THEMES[theme_name], **overrides)
                changed += len(overrides)
        return changed

    def custom_snippets(self):
        """Return custom snippets from SWAR.udata.

        Supported variables:
            snippet.Template.My Clip:>>>> MY CLIP <<<<.
            snippet_desc.Template.My Clip:Description text.
            snippet_cursor_back.Template.My Clip:4.

        Text uses simple escapes: \\n, \\t, \\r, and \\:.
        Unknown groups can still be returned; the shell places them in Template.
        """
        from .editor_tools import Snippet

        snippets = []
        for key, value in self.values.items():
            if not key.startswith("snippet."):
                continue
            if value.strip().lower() in {"", "abc", "xyz", "0", "00"}:
                continue
            parts = key.split(".", 2)
            if len(parts) != 3:
                continue
            group = parts[1].strip()
            label = parts[2].strip()
            if not group or not label or label.lower() in {"abc", "xyz"}:
                continue
            desc = self.get(f"snippet_desc.{group}.{label}", "Custom SWAR.udata snippet.")
            cursor_raw = self.get(f"snippet_cursor_back.{group}.{label}", "0")
            try:
                cursor_back = max(0, int(cursor_raw))
            except ValueError:
                cursor_back = 0
            text = _unescape_udata_text(value)
            snippets.append((group, Snippet(label=label, text=text, cursor_back=cursor_back, description=desc)))
        return snippets

    def save(self) -> None:
        self.path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")



def _valid_color(value: str) -> bool:
    return bool(re.fullmatch(r"#[0-9A-Fa-f]{3}(?:[0-9A-Fa-f]{3})?", value.strip()))


def _unescape_udata_text(value: str) -> str:
    # Preserve normal text while supporting compact one-line snippet definitions.
    return (
        value.replace(r"\n", "\n")
        .replace(r"\r", "\r")
        .replace(r"\t", "\t")
        .replace(r"\:", ":")
    )


def _strip_terminal(value: str) -> str:
    if not value:
        return value
    # udata line-ending characters terminate only when they are the final character.
    if value[-1] in END_CHARS:
        return value[:-1].strip()
    return value.strip()
