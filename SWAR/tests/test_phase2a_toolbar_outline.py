from pathlib import Path

from swar.outline import outline_path_for


def test_outline_replaces_shownotes_suffix():
    assert outline_path_for('Episode - shownotes.txt').name == 'Episode - outline.txt'
    assert outline_path_for('Episode_shownotes.script').name == 'Episode_outline.txt'


def test_outline_replaces_note_notes_show_suffixes():
    assert outline_path_for('Episode-notes.md').name == 'Episode-outline.txt'
    assert outline_path_for('Episode-note.md').name == 'Episode-outline.txt'
    assert outline_path_for('Episode-show.script').name == 'Episode-outline.txt'


def test_outline_falls_back_to_append_outline():
    assert outline_path_for('Episode Draft.script').name == 'Episode Draft_outline.txt'
