from __future__ import annotations

from pathlib import Path
import sys
from urllib.parse import unquote

from .parser import SwarParser
from .renderer_html import render_doc_html
from .outline import export_outline
from .themes import THEMES, get_theme
from .udata import UData

try:
    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import QAction, QGuiApplication
    from PySide6.QtWidgets import (
        QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
        QMessageBox, QPushButton, QScrollBar, QTextBrowser, QToolBar, QToolTip, QVBoxLayout,
        QWidget,
    )
except Exception as exc:  # pragma: no cover
    Qt = None
    QMainWindow = object  # lets CLI import this module without PySide6 installed
    _PYSIDE_IMPORT_ERROR = exc
else:
    _PYSIDE_IMPORT_ERROR = None


class SwarReaderWindow(QMainWindow):
    def __init__(self, file_path: str | None = None, udata_path: str = "SWAR.udata", reader_only: bool = True):
        super().__init__()
        self.parser = SwarParser()
        self.doc = None
        self.file_path = file_path
        self.reader_only = reader_only
        self.udata = UData.load(udata_path)
        self.udata.apply_theme_overrides()
        self.udata.bump_counter("reader_launch_count")
        self.udata.save()
        self.theme_name = self.udata.get_theme_name()
        self.allow_online_links = False

        self.setWindowTitle("SWAR Reader - Script Writer and Reader")
        self.resize(980, 720)
        self.setMinimumSize(260, 280)
        self._build_ui()
        if file_path:
            self.load_file(file_path)
        else:
            self._render_empty()

    def _build_ui(self) -> None:
        toolbar = QToolBar("SWAR Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        open_action = QAction("Open", self)
        open_action.triggered.connect(self.open_file)
        toolbar.addAction(open_action)

        reload_action = QAction("Reload", self)
        reload_action.triggered.connect(self.reload_file)
        toolbar.addAction(reload_action)

        export_action = QAction("Export Outline", self)
        export_action.triggered.connect(self.export_outline)
        toolbar.addAction(export_action)

        toolbar.addSeparator()
        toolbar.addWidget(QLabel("Theme: "))
        self.theme_box = QComboBox()
        self.theme_box.setMaximumWidth(145)
        self.theme_box.addItems(list(THEMES.keys()))
        self.theme_box.setCurrentText(self.theme_name)
        self.theme_box.currentTextChanged.connect(self.change_theme)
        toolbar.addWidget(self.theme_box)

        toolbar.addSeparator()
        self.mode_label = QLabel("Reader Mode | Local Only")
        toolbar.addWidget(self.mode_label)

        self.browser = QTextBrowser()
        self.browser.setMinimumWidth(0)
        self.browser.setOpenLinks(False)
        self.browser.setOpenExternalLinks(False)
        self.browser.anchorClicked.connect(self.handle_anchor)
        self.browser.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.browser.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.bottom_scroll = QScrollBar(Qt.Horizontal)
        self.bottom_scroll.valueChanged.connect(self._bottom_scroll_changed)
        self.browser.verticalScrollBar().rangeChanged.connect(self._sync_scroll_range)
        self.browser.verticalScrollBar().valueChanged.connect(self._sync_footer)

        self.footer = QLabel("Lines: 0    Section: none    0% through file    type: UTF-8    ext: none    size: 0 bytes :: 0 B    sections: 0")
        self.footer.setWordWrap(True)
        self.footer.setMinimumHeight(24)
        self.footer.setMinimumWidth(0)

        central = QWidget()
        central.setMinimumWidth(0)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(self.browser, 1)
        layout.addWidget(self.bottom_scroll)
        layout.addWidget(self.footer)
        self.setCentralWidget(central)

    def _render_empty(self) -> None:
        theme = get_theme(self.theme_name)
        self.browser.setHtml(f"<html><body style='background:{theme.bg}; color:{theme.text}; font-size:20px;'>Open a .script, .md, or .txt file to preview it in SWAR Reader.</body></html>")

    def load_file(self, file_path: str) -> None:
        self.file_path = file_path
        self.doc = self.parser.parse_file(file_path)
        self.render_current()
        self._sync_footer()

    def render_current(self) -> None:
        if not self.doc:
            self._render_empty()
            return
        html = render_doc_html(self.doc, self.theme_name, allow_online_links=self.allow_online_links)
        self.browser.setHtml(html)
        self.setWindowTitle(f"SWAR Reader - {Path(self.file_path).name if self.file_path else 'Untitled'}")
        self._sync_scroll_range()

    def open_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open SWAR Script", "", "Scripts (*.script *.md *.txt);;All Files (*)")
        if path:
            self.load_file(path)

    def reload_file(self) -> None:
        if self.file_path:
            self.load_file(self.file_path)

    def export_outline(self) -> None:
        if not self.doc or not self.file_path:
            QMessageBox.information(self, "SWAR", "Open a file before exporting an outline.")
            return
        out = export_outline(self.doc, self.file_path)
        QMessageBox.information(self, "SWAR Outline Export", f"Outline exported:\n{out}")

    def change_theme(self, name: str) -> None:
        self.theme_name = name
        self.udata.set("current_theme", name, section="HEADER")
        self.udata.save()
        self.render_current()

    def handle_anchor(self, url: QUrl) -> None:
        value = url.toString()
        if value.startswith("copy:"):
            text = unquote(value[5:])
            QGuiApplication.clipboard().setText(text)
            self.statusBar().showMessage("Copied to clipboard.", 2200)
            try:
                QToolTip.showText(QGuiApplication.cursor().pos(), "Copied to clipboard.", self, msecShowTime=1200)
            except Exception:
                pass
        # Local paths are intentionally not anchors in Phase 1B.

    def _sync_scroll_range(self) -> None:
        bar = self.browser.verticalScrollBar()
        self.bottom_scroll.blockSignals(True)
        self.bottom_scroll.setMinimum(bar.minimum())
        self.bottom_scroll.setMaximum(bar.maximum())
        self.bottom_scroll.setPageStep(bar.pageStep())
        self.bottom_scroll.setValue(bar.value())
        self.bottom_scroll.blockSignals(False)

    def _bottom_scroll_changed(self, value: int) -> None:
        self.browser.verticalScrollBar().setValue(value)

    def _sync_footer(self) -> None:
        if not self.doc:
            return
        bar = self.browser.verticalScrollBar()
        maxv = max(1, bar.maximum())
        pct = int((bar.value() / maxv) * 100) if maxv else 0
        size = Path(self.file_path).stat().st_size if self.file_path and Path(self.file_path).exists() else 0
        ext = Path(self.file_path).suffix.lstrip(".") if self.file_path else "none"
        total_lines = 0
        if self.file_path and Path(self.file_path).exists():
            total_lines = len(Path(self.file_path).read_text(encoding="utf-8", errors="replace").splitlines())
        self.footer.setText(
            f"Lines: {total_lines}    Section: {self.doc.header_first_line[:48]}    {pct}% through file    "
            f"type: len-us + UTF-8    ext: {ext}    size: {size} bytes :: {_short_bytes(size)}    sections: {self.doc.section_count}"
        )
        self.bottom_scroll.blockSignals(True)
        self.bottom_scroll.setValue(bar.value())
        self.bottom_scroll.blockSignals(False)


def _short_bytes(size: int) -> str:
    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{size} B"


def run_gui(file_path: str | None = None, udata_path: str = "SWAR.udata", reader_only: bool = True) -> int:
    if _PYSIDE_IMPORT_ERROR is not None:
        print("PySide6 is required for the GUI reader.", file=sys.stderr)
        print("Install on Kubuntu with: python3 -m pip install PySide6", file=sys.stderr)
        print(f"Import error: {_PYSIDE_IMPORT_ERROR}", file=sys.stderr)
        return 2
    app = QApplication(sys.argv)
    win = SwarReaderWindow(file_path=file_path, udata_path=udata_path, reader_only=reader_only)
    win.show()
    return app.exec()
