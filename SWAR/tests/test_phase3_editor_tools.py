from swar.editor_tools import SNIPPET_GROUPS, get_snippet


def test_phase3_snippet_groups_exist():
    for group in ["Sections", "Sub-Sections", "End-Sect", "Source", "Markdown", "Template"]:
        assert group in SNIPPET_GROUPS
        assert SNIPPET_GROUPS[group]


def test_phase3_core_script_snippets():
    assert get_snippet("Sections", "EXIT").text.lower().find("exit to background") >= 0
    assert get_snippet("Sections", "RETURN").text.lower().find("return to show") >= 0
    assert get_snippet("Source", "Web Source").text.startswith("- https://")
    assert "| Segment | Purpose |" in get_snippet("Markdown", "Table").text


def test_phase3_full_template_contains_required_parts():
    full = get_snippet("Template", "Full Mini Script").text
    assert "3D Changes Perspectives::" in full
    assert "URL:" in full
    assert "CHAT TOKEN:" in full
    assert "EXIT TO BACKGROUND" in full
    assert "RETURN TO SHOW" in full
