from pathlib import Path
from swar.parser import SwarParser
from swar.outline import outline_text


def test_example_parser():
    doc = SwarParser().parse_file(Path(__file__).parent.parent / "examples" / "example.script")
    assert doc.header_first_line.startswith("3D Changes Perspectives::")
    assert any(b.kind == "meta_secret" for b in doc.blocks)
    assert any(b.kind == "important" for b in doc.blocks)
    assert any(b.kind == "markdown_table" for b in doc.blocks)
    assert any(b.kind == "source" and b.attrs.get("is_url") for b in doc.blocks)
    assert any(b.kind == "source" and b.attrs.get("is_local") for b in doc.blocks)
    out = outline_text(doc)
    assert "https://presearch.com/search" in out
    assert "local_assets" not in out
