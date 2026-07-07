from pathlib import Path

from swar.save_ops import resolve_save_path, with_extension, section_for_scroll, short_bytes
from swar.parser import SwarParser


def test_phase2_save_path_resolution():
    assert with_extension('show.txt', 'script').name == 'show.script'
    assert with_extension('show', None).name == 'show.script'
    assert resolve_save_path('/tmp/show.txt', 'md').name == 'show.md'
    assert resolve_save_path('/tmp/show.txt', None).name == 'show.txt'


def test_phase2_footer_section_estimate():
    doc = SwarParser().parse('3D Changes Perspectives:: Test: One\n\n>>>> FIRST <<<<\n"hello"\n\n>>>>>>> EXIT TO BACKGROUND <<<<<<<\n')
    assert section_for_scroll(doc, 0).startswith('3D Changes')
    assert section_for_scroll(doc, 90) in {'FIRST', 'EXIT TO BACKGROUND'}


def test_phase2_short_bytes():
    assert short_bytes(9) == '9 B'
    assert short_bytes(2048) == '2.0 KB'
