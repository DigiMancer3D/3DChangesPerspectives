from __future__ import annotations

import os
from pathlib import Path

import pytest


def test_phase5_r2_gui_load_keeps_file_text(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    monkeypatch.setenv("QT_QPA_PLATFORM", os.environ.get("QT_QPA_PLATFORM", "offscreen"))
    from PySide6.QtWidgets import QApplication
    from swar.gui_shell import SwarShellWindow

    app = QApplication.instance() or QApplication([])
    sample = tmp_path / "sample.script"
    sample.write_text('3D Changes Perspectives:: Test: Load\n\n"Visible words."\n', encoding="utf-8")
    win = SwarShellWindow(str(sample), udata_path=str(tmp_path / "SWAR.udata"), reader_only=False)
    tab = win.active_tab()
    assert tab is not None
    assert "Visible words" in tab.state.text
    assert "Visible words" in tab.editor.toPlainText()
    assert tab.state.dirty is False
    assert not win.tabs.tabText(0).startswith("*")
    win.close()
    app.processEvents()
