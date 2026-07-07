from swar.parser import SwarParser
from swar.renderer_html import render_doc_html


def test_header_copy_fields_are_visible_inline_styles():
    doc = SwarParser().parse('3D Changes Perspectives:: Test: R2\nURL: rtmp://example/live\nKEY: secret\nCHAT TOKEN: https://example/chat\nMETA DATA: abc\n')
    html = render_doc_html(doc, 'Dark Mode')
    assert 'style="color:#e0e0e0; text-decoration:none;"' in html
    assert 'URL:</span> <code style="color:#ff9900; font-weight:900;">******</code>' in html
    assert 'KEY:</span> <code style="color:#ff9900; font-weight:900;">******</code>' in html
    assert 'copy:secret' in html


def test_repeated_one_child_sources_get_large_gap():
    text = '''3D Changes Perspectives:: Test: Sources
- https://one.example/a
  "one child"
- https://two.example/b
  "one child"
- https://three.example/c
  "one child"
'''
    doc = SwarParser().parse(text)
    html = render_doc_html(doc, 'Dark Mode')
    assert html.count('source-next-gap') >= 2
    assert '.source-next-gap { height: 78px; }' in html
