from swar.parser import SwarParser, describe_url
from swar.renderer_html import render_doc_html


def test_host_display_drops_tld():
    meta = describe_url('https://www.youtube.com/@DeOrganized')
    assert meta['tld'] == 'com'
    assert meta['host'] == 'www.youtube'


def test_down_arrow_art_is_not_markdown_table():
    text = (
        'Header:: EP: Details\n\n'
        '>>>> !!! DO NOT RESPOND TO THIS YET !!! <<<<\n'
        ' || || || || ||\n'
        ' \\/ \\/ \\/ \\/ \\/\n'
    )
    doc = SwarParser().parse(text)
    assert any(b.kind == 'down_arrows' for b in doc.blocks)
    assert not any(b.kind == 'markdown_table' for b in doc.blocks)

def test_render_copy_links_and_source_meta_new_line():
    doc = SwarParser().parse('Header:: EP: Details\nURL: secret\n\n- https://presearch.com/search?q=test+query\n')
    html = render_doc_html(doc, 'Dark Mode')
    assert 'copy:Header%3A%3A%20EP%3A%20Details' in html
    assert 'copy:secret' in html
    assert 'source-meta' in html
    assert 'HOST: presearch' in html
    assert 'HOST: presearch.com' not in html


def test_exit_and_return_transition_classes():
    doc = SwarParser().parse('Header:: EP: Details\n\n>>>>>>>EXIT TO BACKGROUND<<<<<<<\n>>>>>>>RETURN TO SHOW<<<<<<<\n')
    html = render_doc_html(doc, 'Dark Mode')
    assert 'transition-exit' in html
    assert 'transition-return' in html


def test_markdown_inside_arrow_marker():
    doc = SwarParser().parse('Header:: EP: Details\n\n>>>> **go over process** <<<<\n')
    html = render_doc_html(doc, 'Dark Mode')
    assert '<strong>GO OVER PROCESS</strong>' in html
