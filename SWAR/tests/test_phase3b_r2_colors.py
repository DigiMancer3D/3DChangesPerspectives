from pathlib import Path

from swar.parser import SwarParser
from swar.renderer_html import render_doc_html
from swar.udata import UData
from swar.themes import get_theme


def test_global_section_colors_override_bang_notice(tmp_path: Path):
    udata_path = tmp_path / "SWAR.udata"
    udata = UData.load(udata_path)
    udata.set("theme.Dark Mode.highlight", "#d0d0d0", section="BODY")
    udata.set("section.important.color", "#ff9900", section="BODY")
    udata.apply_theme_overrides()
    theme = get_theme("Dark Mode")
    assert theme.highlight == "#d0d0d0"
    assert theme.important == "#ff9900"
    doc = SwarParser().parse("3D Changes Perspectives:: Test\n\n!!!!!!!! EXTRA CLIP before exit !!!!!!!!")
    html = render_doc_html(doc, "Dark Mode")
    assert ".bang-notice { color:#ff9900;" in html


def test_requested_default_theme_backgrounds():
    assert get_theme("Light Mode").bg.lower() == "#f9fbff"
    assert get_theme("Paper Mode").bg.lower() == "#f5f5f0"
    assert get_theme("Blue Mode").bg.lower() == "#00172d"
