from swar.parser import SwarParser
from swar.outline import outline_text


def test_split_dash_source_url_is_absorbed():
    text = 'Header:: EP: Details\n\n- \nhttps://example.com/path/page.html\n\n"script"\n'
    doc = SwarParser().parse(text)
    sources = [b for b in doc.blocks if b.kind == 'source']
    assert len(sources) == 1
    assert sources[0].attrs['split_dash_source'] is True
    assert sources[0].attrs['is_url'] is True
    assert doc.source_links == ['https://example.com/path/page.html']


def test_private_bang_url_is_not_exported():
    text = 'Header:: EP: Details\n\n! https://example.com/private !\n'
    doc = SwarParser().parse(text)
    sources = [b for b in doc.blocks if b.kind == 'source']
    assert len(sources) == 1
    assert sources[0].attrs['private'] is True
    assert doc.source_links == []
    assert 'https://example.com/private' not in outline_text(doc)


def test_www_source_normalizes_for_outline():
    text = 'Header:: EP: Details\n\n- www.example.com/test\n'
    doc = SwarParser().parse(text)
    assert doc.source_links == ['https://www.example.com/test']
