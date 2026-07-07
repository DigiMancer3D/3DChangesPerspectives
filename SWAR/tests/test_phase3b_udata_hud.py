from pathlib import Path

from swar.udata import UData
from swar.themes import THEMES
from swar.editor_tools import Snippet


def test_udata_theme_override_and_custom_snippet(tmp_path):
    p = tmp_path / "SWAR.udata"
    p.write_text(
        "HEADER:\ncurrent_theme:Dark Mode.\n\n"
        "BODY:\n"
        "theme.Dark Mode.link:#123456.\n"
        "theme.NIGHT.highlight:#abcdef.\n"
        "theme.Dark Mode.not_a_field:#ffffff.\n"
        "theme.Dark Mode.text:not-a-color.\n"
        "snippet.Template.Test Clip:>>>> TEST CLIP <<<<.\n"
        "snippet_desc.Template.Test Clip:Test description.\n"
        "snippet_cursor_back.Template.Test Clip:5.\n"
        "snippet.Custom.Loose Clip:line one\\nline two.\n",
        encoding="utf-8",
    )
    u = UData.load(p)
    changed = u.apply_theme_overrides()
    assert changed >= 2
    assert THEMES["Dark Mode"].link == "#123456"
    assert THEMES["Dark Mode"].highlight == "#abcdef"

    snippets = u.custom_snippets()
    assert ("Template", Snippet("Test Clip", ">>>> TEST CLIP <<<<", 5, "Test description")) in snippets
    loose = [item for item in snippets if item[0] == "Custom"][0][1]
    assert loose.text == "line one\nline two"


def test_gui_shell_phase3b_symbols_importable():
    import swar.gui_shell as gui_shell

    assert hasattr(gui_shell, "SwarShellWindow")
    assert hasattr(gui_shell, "SwarPlainTextEdit")
