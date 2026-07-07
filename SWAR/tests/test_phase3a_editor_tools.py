from swar.editor_tools import SNIPPET_GROUPS, get_snippet
from swar.parser import SwarParser
from swar.renderer_html import render_doc_html
from swar.themes import get_theme


def test_phase3a_markdown_snippets_added_and_important_ends_removed():
    labels = {s.label for s in SNIPPET_GROUPS["Markdown"]}
    for label in ["Caption", "Strong", "Blocks", "Nests", "Num-List", "$-List", "%-List", "Bulleted", "Underline"]:
        assert label in labels
    end_labels = {s.label for s in SNIPPET_GROUPS["End-Sect"]}
    assert "Important End <<" not in end_labels


def test_phase3a_parser_lists_quotes_and_caption():
    text = """3D Changes Perspectives:: Test: MD

###### Caption
> block quote
>> nested quote
- [#] item
- [$] money
- [%15] Topic A
- [%50] Topic B
+ bullet
___under___ ***strong***
"""
    doc = SwarParser().parse(text)
    kinds = [b.kind for b in doc.blocks]
    assert "markdown_heading" in kinds
    assert kinds.count("markdown_blockquote") == 2
    assert "markdown_num_item" in kinds
    assert "markdown_money_item" in kinds
    assert "markdown_percent_list" in kinds
    assert "markdown_bullet_item" in kinds
    html = render_doc_html(doc, "Dark Mode")
    assert "md-caption" in html
    assert "md-blockquote nested" in html
    assert "md-percent-list" in html
    assert "<u>under</u>" in html
    assert "<strong><em>strong</em></strong>" in html


def test_phase3a_theme_has_expanded_highlights():
    theme = get_theme("Blue Mode")
    assert theme.highlight2
    assert theme.highlight3
    assert theme.highlight4
    assert theme.highlight5
    assert theme.fade_purple1
