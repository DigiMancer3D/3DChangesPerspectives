#!/usr/bin/env python3
from __future__ import annotations

from html import escape
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from swar.arc_tools import new_arc_template, parse_arc_line, parse_story_arc_data  # noqa: E402
from swar.local_tools import SimpleSpellChecker  # noqa: E402
from swar.parser import SwarParser  # noqa: E402
from swar.renderer_html import _inline_markdown, render_doc_html  # noqa: E402
from swar.save_ops import auto_save_path, resolve_save_path  # noqa: E402
from swar.themes import get_theme  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"PASS: {message}")


def main() -> int:
    parser = SwarParser()
    sample = '''3D Changes Perspectives:: Hypertext Test

-> Indented exactly four spaces
A -> B <- C ^-^ U v-v D ^-> NE v-> SE <-v SW <-^ NW
######## .. <<<<<<<
###### >> .. <<
###### Prefix => Dim gold <<<<<
###### !Bright Gold! <<<<
#########  ATTENTION REQUIRED <<<<<<
x #12 y !!4 z
#one!!two# and !!low#high!! and #a#b#c#
#12/value rest !!3/value rest
#outer !!inner#!! and !!outer #inner!!#
>>!!
 NOTE: "A quote begins
 and the final quote remains"
 !! !! !!<<
'''
    doc = parser.parse(sample, path="sample.script")
    kinds = [block.kind for block in doc.blocks]
    for expected in (
        "indent4", "vertical_gap", "golden_dim", "golden_bright",
        "attention_red", "important",
    ):
        require(expected in kinds, f"parsed {expected}")
    gaps = [block.attrs["gap_lines"] for block in doc.blocks if block.kind == "vertical_gap"]
    require(gaps == [7, 13], "seven-line gap and thirteen-line page break")

    html = render_doc_html(doc, "Dark Mode")
    for symbol in ("→", "←", "↑", "↓", "↗", "↘", "↙", "↖"):
        require(symbol in html, f"rendered inline arrow {symbol}")
    require("<sup>#12</sup>" in html and "<sub>!!4</sub>" in html, "visible super/sub prefixes")
    require("<sup>one</sup>" in html and "<sub>two</sub>" in html, "super-to-sub cross group")
    require("<sub>low</sub>" in html and "<sup>high</sup>" in html, "sub-to-super cross group")
    require("<sup>a</sup> <sup>b</sup> <sup>c</sup>" in html, "multi-group superscript chain")
    require("<sup>12/value</sup>" in html and "<sub>3/value</sub>" in html, "hidden slash-prefix groups")
    require("<sup>outer <sub>inner</sub></sup>" in html, "nested subscript inside superscript")
    require("<sub>outer <sup>inner</sup></sub>" in html, "nested superscript inside subscript")
    require("final quote remains&quot;" in html, "Important block preserves meaningful final quote")
    require('name="swar-line-1"' in html, "rendered source-line anchors for linked scrolling")

    indent_block = next(block for block in doc.blocks if block.kind == "indent4")
    require(indent_block.text == "Indented exactly four spaces", "line-start arrow remains indent syntax")
    inline_start = _inline_markdown(escape("-> start"), get_theme("Dark Mode"))
    require("→" not in inline_start, "inline arrow alias does not activate at line start")

    color_doc = parser.parse(
        '>>>> PREVIOUS <<<<\n"Colored" [#ff0000]\n"Plain after"\n',
        path="color.script",
    )
    require(color_doc.blocks[0].attrs.get("color_profile") is None, "color does not leak to previous object")
    require(color_doc.blocks[1].attrs.get("color_profile") == "#ff0000", "color applies to target object")
    require(color_doc.blocks[2].attrs.get("color_profile") is None, "color does not leak to following object")

    arc_doc = parser.parse(new_arc_template() + "\n", path="story.arcs")
    require([block.kind for block in arc_doc.blocks] == ["arc_record"], "parsed .arcs Story record")
    require("New Arc" in render_doc_html(arc_doc, "Dark Mode"), "rendered basic Story card")
    record = parse_arc_line(
        "Meet Guide||3:2:3||Safe||***Begin***||$imported map#||enter ->'Guide'||***Done***"
    )
    require(not record.warnings, "accepted valid seven-field Arc record")

    story_data = (
        'Alice: "We made it."; "Keep your voice down." :Bob; '
        'Carol: "I found the sigil."; Dana: "I will watch the gate."; '
        'Alice: "Move now."; _The gate opens_; SEARCH GATE -> CLUE FOUND; '
        '^Ask about the sigil^; *Follow the guide*; [enter/user {unlock}]; '
        '@{GATE}; ~brass key~; drop%25; '
        '>>>> SCENE CUE <<<<\\n"Normal *.script speech inside Arc Data."\\n'
        '>>!!\\n"Boxed Arc detail."\\n!! !! !!<<'
    )
    story_elements = parse_story_arc_data(story_data)
    talks = [item for item in story_elements if item["kind"] == "talk"]
    require([item.get("speaker") for item in talks[:4]] == ["Alice", "Bob", "Carol", "Dana"], "parsed four named screenplay speakers")
    require(any(item["kind"] == "notice" for item in story_elements), "parsed centered noticed-action plot point")
    require(any(item["kind"] == "directive" and item.get("arrow") == "->" for item in story_elements), "parsed twin action/result directive")
    require(sum(1 for item in story_elements if item["kind"] == "option") == 2, "parsed interactable and mandatory options")
    require(any(item["kind"] == "data" and item.get("category") == "Binding" for item in story_elements), "parsed grouped binding data")
    require(any(item["kind"] == "markup" for item in story_elements), "parsed normal *.script block markup inside Arc Data")

    story_line = (
        "Four Voices||3:2:3||Safe||***>>>> ARRIVAL <<<<\\n\"A voice calls from the gate.\"***||$imported gate#||"
        + story_data
        + "||***>>>> COMPLETE <<<<\\n\"The route opens.\"***"
    )
    screenplay_doc = parser.parse(story_line + "\n", path="screenplay.arcs")
    screenplay_html = render_doc_html(screenplay_doc, "Dark Mode")
    for token, label in (
        ('class="story-arc-divider"', "unique Story Arc divider"),
        ('class="story-convo-rail"', "CONVO top rail"),
        ("CONVO END", "CONVO END bottom rail"),
        ('class="story-talk-row left', "left talker box"),
        ('class="story-talk-row right', "right talker box"),
        ('class="story-talk-row center', "center third-speaker box"),
        ('speaker-3', "fourth speaker color/position rotation"),
        ('class="story-directive-grid"', "twin directive boxes"),
        ("➜", "overlapping forward direction glyph"),
        ("COMMON / ENGINE DATA", "grouped common-data table"),
        ("OPTION", "interactable option row"),
        ("REQUIRED", "mandatory event row"),
        ("arrow-title", "embedded *.script arrow styling in Arc Data"),
        ("important-table", "embedded *.script Important box in Arc Data"),
    ):
        require(token in screenplay_html, f"rendered {label}")
    require('right-buffer" style="color:#5fc8ff;">!!</td>' in screenplay_html, "left talker shows only the opposite-side !! edge")
    require('left-buffer" style="color:#ff9bcf;">!!</td>' in screenplay_html, "right talker shows only the opposite-side !! edge")
    require(screenplay_html.count('speaker-2') >= 1 and screenplay_html.count('>!!</td>') >= 4, "center talker uses two colored !! edges")

    checker = SimpleSpellChecker(["script", "reader", "editor", "scrolling"])
    require("script" in checker.suggestions("scrpt"), "local spell suggestion generation")
    require(auto_save_path("arcs").suffix == ".arcs", ".arcs autosave extension")
    require(resolve_save_path("demo.script", "arcs").suffix == ".arcs", ".arcs typed save conversion")

    gui_source = (ROOT / "swar" / "gui_shell.py").read_text(encoding="utf-8")
    for token, label in (
        ("SHARED_SCROLL_STEPS = 10000", "normalized shared Split/Story scrollbar"),
        ("def rebuild_reader_line_map", "rendered source-line anchor map"),
        ("def _editor_source_position", "editor-led visible source position"),
        ("self.sync_reader_to_editor_scroll()", "editor-to-Reader anchor synchronization"),
        ("self.editor_scroll = QScrollBar", "dedicated Editor bottom scroller"),
        ("self.reader_scroll = QScrollBar", "dedicated Reader bottom scroller"),
        ("shared_single = max(1, round(SHARED_SCROLL_STEPS / editor_span))", "one-click shared scrollbar scaling"),
        ("self.editor, self.reader,", "uniform linked key handling over either pane"),
        ('self._toolbar_separator("|:|")', "Story-only editor/Arc separator"),
        ("TOOLBAR_EDGE_PADDING = 18", "top-row edge padding"),
        ("active_cursor.hasSelection()", "right-click selection preservation"),
        ("cancel_pending_context_menu", "held-right-click menu suppression"),
        ("menu.popup(global_point)", "non-modal replaceable context menu"),
    ):
        require(token in gui_source, f"GUI source includes {label}")
    require('QPushButton("Story Mode")' not in gui_source, "removed redundant center Story Mode button")
    require('editor_row = self._interleave_toolbar' in gui_source, "dedicated second-row editor controls")
    require('source == "editor"' in gui_source, "linked scrolling remains editor-led")

    arc_source = (ROOT / "swar" / "arc_tools.py").read_text(encoding="utf-8")
    require('Snippet("Named Talker"' in arc_source and 'Snippet("Named Talker Right"' in arc_source, "Story menu includes named-speaker inserts")

    example = ROOT / "examples" / "example.script"
    example_text = example.read_text(encoding="utf-8")
    require(example.is_file() and "CONVO / MULTI-SPEAKER STORY OUTPUT" in example_text, "updated comprehensive examples/example.script")
    story_demo = ROOT / "examples" / "story_screenplay_demo.arcs"
    require(story_demo.is_file() and 'Alice: "' in story_demo.read_text(encoding="utf-8"), "updated named-speaker Story screenplay example")

    print("\nALL SWAR v0.7.1-rc1-r3 LINKED/STORY QA SELFTESTS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
