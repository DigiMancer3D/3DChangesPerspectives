from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    text: str
    link: str
    highlight: str
    panel: str
    muted: str
    border: str
    important: str
    cue: str
    title: str
    source: str
    table_border: str
    highlight2: str = "#cc7a00"
    highlight3: str = "#cc5500"
    highlight4: str = "#cc3333"
    highlight5: str = "#8b0000"
    fade_purple1: str = "#8050c8"
    fade_purple2: str = "#5a2a9a"
    fade_green1: str = "#2aa84a"
    fade_green2: str = "#126a30"
    fade_red1: str = "#d24a4a"
    fade_red2: str = "#ff7070"
    data: str | None = None
    verbatim: str | None = None
    section_title: str | None = None
    descriptor: str | None = None
    explainer: str | None = None
    major_explainer: str | None = None
    markdown_heading: str | None = None
    markdown_table: str | None = None

    def __post_init__(self):
        object.__setattr__(self, "data", self.data or self.highlight)
        object.__setattr__(self, "verbatim", self.verbatim or self.highlight2)
        object.__setattr__(self, "section_title", self.section_title or self.highlight3)
        object.__setattr__(self, "descriptor", self.descriptor or self.highlight4)
        object.__setattr__(self, "explainer", self.explainer or self.highlight5)
        object.__setattr__(self, "major_explainer", self.major_explainer or self.fade_purple1)
        object.__setattr__(self, "markdown_heading", self.markdown_heading or self.title)
        object.__setattr__(self, "markdown_table", self.markdown_table or self.table_border)


THEMES: dict[str, Theme] = {
    "Light Mode": Theme(
        name="Light Mode", bg="#f9fbff", text="#001a44", link="#8000aa", highlight="#ff9900",
        panel="#f3f6fb", muted="#607080", border="#0b3a75", important="#d96b00",
        cue="#345aa8", title="#142f64", source="#235789", table_border="#606060", data="#6aa4ff", verbatim="#dddddd", section_title="#ffffff", descriptor="#cc99ff", explainer="#ffaa44", major_explainer="#ffcc66", markdown_heading="#88aaff", markdown_table="#cccccc",
        highlight2="#b85f00", highlight3="#b84b2f", highlight4="#c72020", highlight5="#7a0000",
        fade_purple1="#7d3bb0", fade_purple2="#4c176e", fade_green1="#2a8f45", fade_green2="#0f5a24",
    ),
    "Dark Mode": Theme(
        name="Dark Mode", bg="#000000", text="#c0c0c0", link="#39ff14", highlight="#ff9900",
        panel="#101010", muted="#858585", border="#666666", important="#e69500",
        cue="#9a9a9a", title="#e0e0e0", source="#55d05a", table_border="#777777", data="#6aa4ff", verbatim="#dddddd", section_title="#ffffff", descriptor="#cc99ff", explainer="#ffaa44", major_explainer="#ffcc66", markdown_heading="#88aaff", markdown_table="#cccccc",
        highlight2="#ffbf59", highlight3="#e88a36", highlight4="#2f78d6", highlight5="#77b8ff",
        fade_purple1="#b476ff", fade_purple2="#d4a8ff", fade_green1="#42e66b", fade_green2="#9bffb3",
    ),
    "Paper Mode": Theme(
        name="Paper Mode", bg="#F5F5F0", text="#245c9e", link="#b00020", highlight="#7a3fb0",
        panel="#fffdf6", muted="#6e6e6e", border="#bca987", important="#7a3fb0",
        cue="#245c9e", title="#123f73", source="#b00020", table_border="#9b8c6f", data="#6aa4ff", verbatim="#dddddd", section_title="#ffffff", descriptor="#cc99ff", explainer="#ffaa44", major_explainer="#ffcc66", markdown_heading="#88aaff", markdown_table="#cccccc",
        highlight2="#54227d", highlight3="#3e3aa8", highlight4="#2460c2", highlight5="#123a83",
        fade_purple1="#e06a00", fade_purple2="#984000", fade_green1="#2a8f45", fade_green2="#0f5a24",
    ),
    "Terminal Mode": Theme(
        name="Terminal Mode", bg="#000000", text="#39ff14", link="#ff9900", highlight="#ff9900",
        panel="#060606", muted="#8a8a8a", border="#1eff00", important="#ff9900",
        cue="#39ff14", title="#8aff80", source="#ff9900", table_border="#39ff14", data="#6aa4ff", verbatim="#dddddd", section_title="#ffffff", descriptor="#cc99ff", explainer="#ffaa44", major_explainer="#ffcc66", markdown_heading="#88aaff", markdown_table="#cccccc",
        highlight2="#ffbf59", highlight3="#e88a36", highlight4="#2f78d6", highlight5="#77b8ff",
        fade_purple1="#b476ff", fade_purple2="#d4a8ff", fade_green1="#ff5555", fade_green2="#ff9999",
    ),
    "Blue Mode": Theme(
        name="Blue Mode", bg="#00172d", text="#ffffff", link="#ff9900", highlight="#ff9900",
        panel="#08245f", muted="#b8c4df", border="#7da2ff", important="#ffb347",
        cue="#dbe5ff", title="#ffffff", source="#ff9900", table_border="#7da2ff", data="#6aa4ff", verbatim="#dddddd", section_title="#ffffff", descriptor="#cc99ff", explainer="#ffaa44", major_explainer="#ffcc66", markdown_heading="#88aaff", markdown_table="#cccccc",
        highlight2="#ffbf59", highlight3="#d96b4f", highlight4="#ff4040", highlight5="#ff7777",
        fade_purple1="#b476ff", fade_purple2="#d4a8ff", fade_green1="#42e66b", fade_green2="#9bffb3",
    ),
}

DEFAULT_THEME = "Dark Mode"


def get_theme(name: str | None) -> Theme:
    if not name:
        return THEMES[DEFAULT_THEME]
    return THEMES.get(name, THEMES[DEFAULT_THEME])
