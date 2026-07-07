from pathlib import Path

from swar.emoji_tools import parse_emoji_text, load_current_emoji, default_emoji_candidates


def test_pipe_emoji_file_parses_category_and_label():
    entries = parse_emoji_text("✅|Check|Status /,\n🧪|Test Tube|Lab /,\n")
    assert entries[0].symbol == "✅"
    assert entries[0].label == "Check"
    assert entries[0].category == "Status"
    assert "lab" in entries[1].search_text


def test_json_emoji_future_format_parses():
    entries = parse_emoji_text('[{"emoji":"🔥","name":"Fire","category":"Lab","tags":["hot","signal"]}]')
    assert entries[0].symbol == "🔥"
    assert entries[0].label == "Fire"
    assert entries[0].category == "Lab"
    assert "signal" in entries[0].search_text


def test_load_current_emoji_from_extra_dir(tmp_path):
    p = tmp_path / "current.emoji"
    p.write_text("🔍|Magnifier|Lab /,\n", encoding="utf-8")
    entries, source = load_current_emoji([tmp_path])
    assert source == p
    assert entries[0].label == "Magnifier"


def test_gui_shell_phase4_symbols_importable():
    import swar.gui_shell as gui_shell

    assert hasattr(gui_shell, "SwarShellWindow")
    assert hasattr(gui_shell, "EmojiEntry")
