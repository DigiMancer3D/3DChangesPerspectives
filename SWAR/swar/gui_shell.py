from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from urllib.parse import unquote

from .parser import SwarParser, ScriptDoc
from .renderer_html import render_doc_html
from .outline import export_outline
from .themes import THEMES, get_theme
from .udata import UData
from .save_ops import resolve_save_path, auto_save_path, short_bytes, section_for_scroll
from .editor_tools import SNIPPET_GROUPS, Snippet
from .emoji_tools import EmojiEntry, load_current_emoji
from .local_tools import SimpleSpellChecker, find_matches

try:
    from PySide6.QtCore import Qt, QUrl, QTimer, QSize
    from PySide6.QtGui import QAction, QGuiApplication, QFont, QTextOption, QSyntaxHighlighter, QTextCharFormat, QColor, QTextCursor, QPainter, QTextDocument, QKeySequence
    from PySide6.QtWidgets import (
        QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
        QCheckBox, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QMenu, QPlainTextEdit, QPushButton, QScrollBar, QSplitter,
        QTabWidget, QTextBrowser, QToolBar, QToolButton, QToolTip, QVBoxLayout,
        QWidget, QWidgetAction,
    )
except Exception as exc:  # pragma: no cover
    Qt = None
    QMainWindow = object
    QWidget = object
    _PYSIDE_IMPORT_ERROR = exc
else:
    _PYSIDE_IMPORT_ERROR = None


THEME_DISPLAY = {
    "Light Mode": "LIGHT",
    "Dark Mode": "NIGHT",
    "Paper Mode": "PAPER",
    "Terminal Mode": "TERM",
    "Blue Mode": "OCEAN",
}
THEME_FROM_DISPLAY = {v: k for k, v in THEME_DISPLAY.items()}
NETWORK_DISPLAY = {"local": "LOCAL", "online": "HTTPS"}
NETWORK_FROM_DISPLAY = {"LOCAL": "local", "HTTPS": "online", "Online Ready": "online", "Local Only": "local"}


def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        spacer = item.spacerItem()
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
        elif spacer is not None:
            pass

@dataclass
class TabState:
    path: str | None = None
    text: str = ""
    doc: ScriptDoc | None = None
    mode: str = "reader"  # reader | editor | split
    dirty: bool = False
    network_mode: str = "local"  # local | online




if _PYSIDE_IMPORT_ERROR is None:
    class ScriptSyntaxHighlighter(QSyntaxHighlighter):
        """Low-cost editor highlighting for SWAR Script Markup and common Markdown."""

        def __init__(self, document, theme_name: str):
            super().__init__(document)
            self.theme_name = theme_name
            self.spell_enabled = False
            self.spell_checker: SimpleSpellChecker | None = None
            self._build_formats()

        def set_spell_enabled(self, enabled: bool, checker: SimpleSpellChecker | None = None) -> None:
            self.spell_enabled = bool(enabled)
            self.spell_checker = checker if enabled else None
            self.rehighlight()

        def set_theme(self, theme_name: str) -> None:
            self.theme_name = theme_name
            self._build_formats()
            self.rehighlight()

        def _fmt(self, color: str, *, bold: bool = False, italic: bool = False) -> QTextCharFormat:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(color))
            if bold:
                fmt.setFontWeight(QFont.Bold)
            if italic:
                fmt.setFontItalic(True)
            return fmt

        def _build_formats(self) -> None:
            theme = get_theme(self.theme_name)
            self.f_source = self._fmt(theme.link, bold=True)
            self.f_arrow2 = self._fmt(theme.data, bold=True)
            self.f_arrow3 = self._fmt(theme.verbatim, bold=True)
            self.f_arrow4 = self._fmt(theme.section_title, bold=True)
            self.f_arrow5 = self._fmt(theme.descriptor, bold=True)
            self.f_arrow6 = self._fmt(theme.explainer, bold=True)
            self.f_arrow7 = self._fmt(theme.major_explainer, bold=True)
            self.f_important = self._fmt(theme.important, bold=True)
            self.f_divider = self._fmt(theme.muted, bold=True)
            self.f_secret = self._fmt(theme.muted, italic=True)
            self.f_quote = self._fmt(theme.text)
            self.f_markdown = self._fmt(theme.markdown_heading, bold=True)
            self.f_markdown2 = self._fmt(theme.fade_green1, bold=True)
            self.f_comment = self._fmt(theme.muted, italic=True)
            self.f_spell = QTextCharFormat()
            self.f_spell.setUnderlineColor(QColor(theme.important))
            try:
                self.f_spell.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SpellCheckUnderline)
            except Exception:
                self.f_spell.setUnderlineStyle(QTextCharFormat.UnderlineStyle.SingleUnderline)

        def _arrow_format(self, count: int) -> QTextCharFormat:
            if count <= 2:
                return self.f_arrow2
            if count == 3:
                return self.f_arrow3
            if count == 4:
                return self.f_arrow4
            if count == 5:
                return self.f_arrow5
            if count == 6:
                return self.f_arrow6
            return self.f_arrow7

        def highlightBlock(self, text: str) -> None:  # noqa: N802 - Qt method name
            stripped = text.strip()
            lower = stripped.lower()
            if not stripped:
                return
            if lower.startswith(("url:", "key:", "chat token:", "meta data:")):
                self.setFormat(0, len(text), self.f_secret)
                return
            if stripped.startswith(("http://", "https://", "www.")) or stripped.startswith("- http") or stripped.startswith("- www"):
                self.setFormat(0, len(text), self.f_source)
            if stripped.startswith("!") and ("http://" in stripped or "https://" in stripped):
                self.setFormat(0, len(text), self.f_secret)
            if stripped.startswith("-") and not stripped.startswith("---"):
                if any(stripped.startswith(prefix) for prefix in ("- [ ]", "- [x]", "- [X]", "- [#]", "- [$]", "- [€]", "- [£]", "- [¥]", "- [¢]", "- [%")):
                    self.setFormat(0, len(text), self.f_markdown2)
                else:
                    self.setFormat(0, min(len(text), max(1, text.find(stripped) + 1)), self.f_source)
            if stripped.startswith("+") and not stripped.startswith("++"):
                self.setFormat(0, len(text), self.f_markdown2)
            if stripped.startswith(">") and not ("<<" in stripped):
                self.setFormat(0, len(text), self.f_arrow2 if stripped.startswith(">>") else self.f_markdown)
            if set(stripped) <= {"-", " "} and stripped.count("-") >= 3:
                self.setFormat(0, len(text), self.f_divider)
            if stripped.startswith("---") and stripped.endswith("---"):
                self.setFormat(0, len(text), self.f_divider)
            arrow_match = None
            if stripped.startswith(">"):
                import re
                arrow_match = re.match(r"^(>+)", stripped)
            if arrow_match and "<<" in stripped:
                self.setFormat(0, len(text), self._arrow_format(len(arrow_match.group(1))))
            if stripped.startswith(">>") and "!!" in stripped:
                self.setFormat(0, len(text), self.f_important)
            if stripped.startswith("!!") or stripped.endswith("!!<<") or stripped.endswith("!!<<<"):
                self.setFormat(0, len(text), self.f_important)
            if stripped.startswith('"') or stripped.endswith('"'):
                if "!!" not in stripped and not stripped.startswith(">"):
                    self.setFormat(0, len(text), self.f_quote)
            for marker in ("***", "**", "___", "__", "#", "|", "- [ ]", "- [x]", "- [#]", "- [$]", "- [%", "> ", ">>"):
                pos = text.find(marker)
                if pos >= 0:
                    self.setFormat(pos, min(len(text) - pos, max(2, len(marker) + 80)), self.f_markdown)
                    break
            if self.spell_enabled and self.spell_checker is not None:
                for start, length, _word in self.spell_checker.iter_unknown(text):
                    self.setFormat(start, length, self.f_spell)
else:  # pragma: no cover - GUI unavailable
    ScriptSyntaxHighlighter = None


if _PYSIDE_IMPORT_ERROR is None:
    class LineNumberArea(QWidget):
        def __init__(self, editor: "SwarPlainTextEdit"):
            super().__init__(editor)
            self.editor = editor

        def sizeHint(self):  # noqa: N802 - Qt method name
            return QSize(self.editor.line_number_area_width(), 0)

        def paintEvent(self, event):  # noqa: N802 - Qt method name
            self.editor.line_number_area_paint_event(event)


    class SwarPlainTextEdit(QPlainTextEdit):
        """QPlainTextEdit with a low-resource line metadata gutter."""

        def __init__(self):
            super().__init__()
            self.line_number_area = LineNumberArea(self)
            self.blockCountChanged.connect(self.update_line_number_area_width)
            self.updateRequest.connect(self.update_line_number_area)
            self.cursorPositionChanged.connect(self.highlight_current_line)
            self.update_line_number_area_width(0)

        def line_number_area_width(self) -> int:
            digits = max(2, len(str(max(1, self.blockCount()))))
            return 14 + self.fontMetrics().horizontalAdvance("9") * digits

        def update_line_number_area_width(self, _new_block_count: int) -> None:
            self.setViewportMargins(self.line_number_area_width(), 0, 0, 0)

        def update_line_number_area(self, rect, dy: int) -> None:
            if dy:
                self.line_number_area.scroll(0, dy)
            else:
                self.line_number_area.update(0, rect.y(), self.line_number_area.width(), rect.height())
            if rect.contains(self.viewport().rect()):
                self.update_line_number_area_width(0)

        def resizeEvent(self, event) -> None:  # noqa: N802 - Qt method name
            super().resizeEvent(event)
            cr = self.contentsRect()
            self.line_number_area.setGeometry(cr.left(), cr.top(), self.line_number_area_width(), cr.height())

        def highlight_current_line(self) -> None:
            # Keep this cheap and theme-neutral. The editor's selection color still comes from the theme.
            self.line_number_area.update()

        def line_number_area_paint_event(self, event) -> None:
            painter = QPainter(self.line_number_area)
            palette = self.palette()
            painter.fillRect(event.rect(), palette.window())
            current_block_number = self.textCursor().blockNumber()
            block = self.firstVisibleBlock()
            block_number = block.blockNumber()
            top = int(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
            bottom = top + int(self.blockBoundingRect(block).height())
            width = self.line_number_area.width() - 4
            while block.isValid() and top <= event.rect().bottom():
                if block.isVisible() and bottom >= event.rect().top():
                    number = str(block_number + 1)
                    if block_number == current_block_number:
                        painter.setPen(palette.highlight().color())
                        number = "▶" + number
                    else:
                        painter.setPen(palette.mid().color())
                    painter.drawText(0, top, width, self.fontMetrics().height(), Qt.AlignRight, number)
                block = block.next()
                top = bottom
                bottom = top + int(self.blockBoundingRect(block).height())
                block_number += 1
else:  # pragma: no cover
    SwarPlainTextEdit = object


class SwarTab(QWidget):
    def __init__(self, shell: "SwarShellWindow", state: TabState):
        super().__init__()
        self.shell = shell
        self.state = state
        self.parser = SwarParser()
        self._syncing_scroll = False
        # Some Qt/PySide6 builds emit textChanged while a syntax highlighter is
        # attached or rehighlighted, even before the file text has been loaded.
        # Suppress those setup-only signals so an opened file cannot be cleared
        # or marked dirty during construction/theme application.
        self._suppress_editor_change = True
        self._build_ui()
        self.set_text(state.text, from_file=True)
        self.set_mode(state.mode)
        self._suppress_editor_change = False

    def _build_ui(self) -> None:
        self.splitter = QSplitter(Qt.Horizontal)
        self.editor = SwarPlainTextEdit()
        self.editor.setLineWrapMode(QPlainTextEdit.WidgetWidth)
        self.editor.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.editor.setTabChangesFocus(False)
        self.editor.setUndoRedoEnabled(True)
        self.editor.textChanged.connect(self._editor_changed)
        self.editor.cursorPositionChanged.connect(self._cursor_changed)

        fixed = QFont("DejaVu Sans Mono")
        fixed.setPointSize(12)
        self.editor.setFont(fixed)
        self.highlighter = ScriptSyntaxHighlighter(self.editor.document(), self.shell.theme_name) if ScriptSyntaxHighlighter else None
        if self.highlighter is not None:
            self.highlighter.set_spell_enabled(self.shell.spell_enabled, self.shell.spell_checker)

        self.reader = QTextBrowser()
        self.reader.setOpenLinks(False)
        self.reader.setOpenExternalLinks(False)
        self.reader.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.reader.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.reader.anchorClicked.connect(self.shell.handle_anchor)

        self.splitter.addWidget(self.editor)
        self.splitter.addWidget(self.reader)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)

        self.bottom_scroll = QScrollBar(Qt.Horizontal)
        self.bottom_scroll.valueChanged.connect(self._bottom_scroll_changed)
        for bar in (self.editor.verticalScrollBar(), self.reader.verticalScrollBar()):
            bar.rangeChanged.connect(self.sync_scroll_range)
            bar.valueChanged.connect(self.sync_scroll_value)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 0)
        layout.addWidget(self.splitter, 1)
        layout.addWidget(self.bottom_scroll)

    def set_text(self, text: str, from_file: bool = False) -> None:
        self.state.text = text
        self.editor.blockSignals(True)
        self.editor.setPlainText(text)
        self.editor.blockSignals(False)
        self.parse_and_render()
        if from_file:
            self.state.dirty = False

    def current_text(self) -> str:
        if self.editor.toPlainText() != self.state.text:
            self.state.text = self.editor.toPlainText()
        return self.state.text

    def parse_and_render(self) -> None:
        text = self.current_text()
        self.state.doc = self.parser.parse(text, path=self.state.path or "")
        html = render_doc_html(
            self.state.doc,
            self.shell.theme_name,
            allow_online_links=self.state.network_mode == "online",
        )
        self.reader.setHtml(html)
        QTimer.singleShot(0, self.sync_scroll_range)
        self.shell.update_footer()

    def set_mode(self, mode: str) -> None:
        self.state.mode = mode
        if mode == "reader":
            self.editor.hide()
            self.reader.show()
            self.parse_and_render()
        elif mode == "editor":
            self.reader.hide()
            self.editor.show()
        else:
            self.editor.show()
            self.reader.show()
            self.parse_and_render()
        QTimer.singleShot(0, self.sync_scroll_range)

    def set_theme(self) -> None:
        theme = get_theme(self.shell.theme_name)
        self.editor.setStyleSheet(
            f"QPlainTextEdit {{ background: {theme.bg}; color: {theme.text}; "
            f"selection-background-color: {theme.highlight}; border: 2px solid {theme.border}; }}"
        )
        if self.highlighter is not None:
            self.highlighter.set_theme(self.shell.theme_name)
            self.highlighter.set_spell_enabled(self.shell.spell_enabled, self.shell.spell_checker)
        self.parse_and_render()

    def set_spell_enabled(self, enabled: bool) -> None:
        if self.highlighter is not None:
            self.highlighter.set_spell_enabled(enabled, self.shell.spell_checker)

    def find_text(self, query: str, *, forward: bool = True, case_sensitive: bool = False) -> tuple[int, int]:
        """Find text in the visible active view. Returns current_index,total."""
        text = self.current_text()
        matches = find_matches(text, query, case_sensitive=case_sensitive)
        total = len(matches)
        if not query or total == 0:
            return 0, 0
        flags = QTextDocument.FindFlag(0)
        if not forward:
            flags |= QTextDocument.FindFlag.FindBackward
        if case_sensitive:
            flags |= QTextDocument.FindFlag.FindCaseSensitively
        widget = self.editor if self.state.mode in {"editor", "split"} else self.reader
        found = widget.find(query, flags)
        if not found:
            cursor = widget.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start if forward else QTextCursor.MoveOperation.End)
            widget.setTextCursor(cursor)
            widget.find(query, flags)
        pos = 0
        try:
            pos = widget.textCursor().selectionStart()
        except Exception:
            pos = 0
        current = 1
        for i, match in enumerate(matches, start=1):
            if match.start <= pos < match.end or pos <= match.start:
                current = i
                break
        return current, total

    def search_count(self, query: str, *, case_sensitive: bool = False) -> int:
        return len(find_matches(self.current_text(), query, case_sensitive=case_sensitive))

    def _editor_changed(self) -> None:
        text = self.editor.toPlainText()
        if getattr(self, "_suppress_editor_change", False):
            return
        # QSyntaxHighlighter.rehighlight() may emit textChanged without changing
        # actual text. Do not mark tabs dirty or rewrite state for those signals.
        if text == self.state.text:
            self.shell.update_footer()
            return
        self.state.text = text
        self.state.dirty = True
        self.shell.refresh_tab_title(self)
        if self.state.mode == "split":
            self.shell.debounce_preview_refresh(self)
        self.shell.update_footer()

    def _cursor_changed(self) -> None:
        self.shell.update_footer()

    def cursor_line_col(self) -> tuple[int, int]:
        cursor = self.editor.textCursor()
        return cursor.blockNumber() + 1, cursor.positionInBlock() + 1

    def block_for_line(self, line_no: int):
        doc = self.state.doc
        if doc is None or self.state.text != self.editor.toPlainText():
            self.state.doc = self.parser.parse(self.current_text(), path=self.state.path or "")
            doc = self.state.doc
        if not doc:
            return None
        previous = None
        for block in doc.blocks:
            if block.kind == "blank":
                continue
            if block.line_start <= line_no <= block.line_end:
                return block
            if block.line_start <= line_no:
                previous = block
            if block.line_start > line_no:
                break
        return previous

    def insert_snippet(self, snippet: Snippet) -> None:
        if self.state.mode == "reader":
            self.set_mode("editor")
            self.shell.mode_box.blockSignals(True)
            self.shell.mode_box.setCurrentText("Editor")
            self.shell.mode_box.blockSignals(False)
        self.editor.setFocus()
        cursor = self.editor.textCursor()
        prefix = ""
        if cursor.position() > 0:
            before = self.editor.toPlainText()[:cursor.position()]
            if before and not before.endswith("\n"):
                prefix = "\n"
        cursor.insertText(prefix + snippet.text)
        if snippet.cursor_back:
            cursor.movePosition(QTextCursor.MoveOperation.Left, QTextCursor.MoveMode.MoveAnchor, min(snippet.cursor_back, len(snippet.text)))
            self.editor.setTextCursor(cursor)
        self.state.dirty = True
        self.shell.refresh_tab_title(self)
        self.shell.update_footer()

    def active_scrollbar(self):
        if self.state.mode == "editor":
            return self.editor.verticalScrollBar()
        return self.reader.verticalScrollBar()

    def sync_scroll_range(self) -> None:
        if self._syncing_scroll:
            return
        bar = self.active_scrollbar()
        self.bottom_scroll.blockSignals(True)
        self.bottom_scroll.setMinimum(bar.minimum())
        self.bottom_scroll.setMaximum(bar.maximum())
        self.bottom_scroll.setPageStep(bar.pageStep())
        self.bottom_scroll.setValue(bar.value())
        self.bottom_scroll.blockSignals(False)
        self.shell.update_footer()

    def sync_scroll_value(self) -> None:
        if self._syncing_scroll:
            return
        bar = self.active_scrollbar()
        self.bottom_scroll.blockSignals(True)
        self.bottom_scroll.setValue(bar.value())
        self.bottom_scroll.blockSignals(False)
        self.shell.update_footer()

    def _bottom_scroll_changed(self, value: int) -> None:
        self._syncing_scroll = True
        self.active_scrollbar().setValue(value)
        self._syncing_scroll = False
        self.shell.update_footer()


class SwarShellWindow(QMainWindow):
    def __init__(self, file_path: str | None = None, udata_path: str = "SWAR.udata", reader_only: bool = False):
        super().__init__()
        self.parser = SwarParser()
        self.reader_only = reader_only
        self.udata = UData.load(udata_path)
        self.udata.apply_theme_overrides()
        self.udata.bump_counter("reader_launch_count" if reader_only else "standard_launch_count")
        self.udata.save()
        self.theme_name = self.udata.get_theme_name()
        self.spell_enabled = self.udata.get("spellcheck_enabled", "0").strip() in {"1", "true", "TRUE", "yes", "YES"}
        self.spell_checker: SimpleSpellChecker | None = None
        if self.spell_enabled:
            self.spell_checker = SimpleSpellChecker.from_system()
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._run_debounced_preview)
        self._preview_tab: SwarTab | None = None

        self.setWindowTitle("SWAR - Script Writer and Reader")
        self.resize(1040, 720)
        self.setMinimumSize(240, 260)
        self._build_ui()
        self.apply_theme()

        if file_path:
            self.open_path(file_path)
        else:
            self.new_tab()
        self.update_toolbar_state()

    def _build_ui(self) -> None:
        self.toolbar_host = QWidget()
        self.toolbar_host.setObjectName("toolbarHost")
        self.toolbar_vbox = QVBoxLayout(self.toolbar_host)
        self.toolbar_vbox.setContentsMargins(2, 2, 2, 2)
        self.toolbar_vbox.setSpacing(2)
        self.toolbar_rows: list[QWidget] = []
        self.toolbar_row_layouts: list[QHBoxLayout] = []
        for _ in range(4):
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(4)
            self.toolbar_rows.append(row)
            self.toolbar_row_layouts.append(layout)
            self.toolbar_vbox.addWidget(row)

        self.open_button = QPushButton("Open")
        self.open_button.clicked.connect(self.open_file_dialog)

        self.new_button = QPushButton("+TAB")
        self.new_button.clicked.connect(self.new_tab)

        self.reload_button = QPushButton("Reload")
        self.reload_button.clicked.connect(self.reload_file)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_preview)

        self.save_button = QToolButton()
        self.save_button.setText("Save")
        self.save_button.setPopupMode(QToolButton.MenuButtonPopup)
        self.save_button.clicked.connect(lambda: self.save_action("save_now"))
        save_menu = QMenu(self.save_button)
        for key, label in [
            ("save_now", "SAVE NOW"),
            ("save_as", "SAVE AS"),
            ("save_script", "SAVE SCRIPT (*.script)"),
            ("save_marked", "SAVE MARKED (*.md)"),
            ("save_text", "SAVE TEXT (*.txt)"),
        ]:
            act = QAction(label, self)
            act.triggered.connect(lambda checked=False, k=key: self.save_action(k))
            save_menu.addAction(act)
        self.save_button.setMenu(save_menu)

        self.outline_button = QPushButton("Outline")
        self.outline_button.clicked.connect(self.export_outline)

        self.tools_button = QToolButton()
        self.tools_button.setText("Tools")
        self.tools_button.setPopupMode(QToolButton.InstantPopup)
        tools_menu = QMenu(self.tools_button)
        self.find_action = QAction("Find / Search", self)
        self.find_action.setShortcut(QKeySequence.Find)
        self.find_action.triggered.connect(self.show_find_panel)
        tools_menu.addAction(self.find_action)
        self.spell_action = QAction(f"Spell Check: {'ON' if self.spell_enabled else 'OFF'}", self)
        self.spell_action.triggered.connect(self.toggle_spellcheck)
        tools_menu.addAction(self.spell_action)
        self.next_find_action = QAction("Find Next", self)
        self.next_find_action.setShortcut(QKeySequence.FindNext)
        self.next_find_action.triggered.connect(lambda: self.find_next(True))
        tools_menu.addAction(self.next_find_action)
        self.prev_find_action = QAction("Find Previous", self)
        self.prev_find_action.setShortcut(QKeySequence.FindPrevious)
        self.prev_find_action.triggered.connect(lambda: self.find_next(False))
        tools_menu.addAction(self.prev_find_action)
        self.tools_button.setMenu(tools_menu)
        self.addAction(self.find_action)
        self.addAction(self.next_find_action)
        self.addAction(self.prev_find_action)

        self.theme_box = QComboBox()
        self.theme_box.setMaximumWidth(98)
        self.theme_box.addItems([THEME_DISPLAY[name] for name in THEMES.keys()])
        self.theme_box.setCurrentText(THEME_DISPLAY.get(self.theme_name, "NIGHT"))
        self.theme_box.currentTextChanged.connect(self.change_theme_display)

        self.mode_box = QComboBox()
        self.mode_box.setMaximumWidth(92)
        self.mode_box.addItems(["Reader", "Editor", "Split"])
        self.mode_box.currentTextChanged.connect(self.change_mode)

        self.network_box = QComboBox()
        self.network_box.setMaximumWidth(82)
        self.network_box.addItems(["LOCAL", "HTTPS"])
        self.network_box.currentTextChanged.connect(self.change_network)

        self.sep_theme_mode = QLabel("|")
        self.sep_mode_network = QLabel("|")
        self.sep_theme_network = QLabel("|")

        self._build_editor_tools()
        self._build_find_panel()

        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.currentChanged.connect(self._active_tab_changed)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        self.footer = QLabel("Lines:\u00a00    Section:\u00a0none    0%\u00a0through\u00a0file    type:\u00a0UTF-8    ext:\u00a0none    size:\u00a00\u00a0bytes\u00a0::\u00a00\u00a0B    sections:\u00a00")
        self.footer.setWordWrap(True)
        self.footer.setMinimumHeight(24)
        self.footer.setMinimumWidth(0)
        self.footer.setTextFormat(Qt.PlainText)

        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.addWidget(self.toolbar_host, 0)
        layout.addWidget(self.find_panel, 0)
        layout.addWidget(self.tabs, 1)
        layout.addWidget(self.footer)
        self.setCentralWidget(central)
        self.statusBar().showMessage("SWAR ready.", 1200)
        self._reflow_toolbar()

    def _build_find_panel(self) -> None:
        self.find_panel = QWidget()
        self.find_panel.setObjectName("findPanel")
        row = QHBoxLayout(self.find_panel)
        row.setContentsMargins(6, 3, 6, 3)
        row.setSpacing(4)
        self.find_label = QLabel("Find:")
        self.find_input = QLineEdit()
        self.find_input.setPlaceholderText("Search current tab...")
        self.find_input.returnPressed.connect(lambda: self.find_next(True))
        self.find_input.textChanged.connect(self._find_text_changed)
        self.find_case_box = QCheckBox("Case")
        self.find_case_box.stateChanged.connect(lambda _state: self._find_text_changed(self.find_input.text()))
        self.find_count_label = QLabel("0/0")
        prev_button = QPushButton("Prev")
        next_button = QPushButton("Next")
        close_button = QPushButton("Close")
        prev_button.clicked.connect(lambda: self.find_next(False))
        next_button.clicked.connect(lambda: self.find_next(True))
        close_button.clicked.connect(self.hide_find_panel)
        row.addWidget(self.find_label)
        row.addWidget(self.find_input, 1)
        row.addWidget(self.find_case_box)
        row.addWidget(self.find_count_label)
        row.addWidget(prev_button)
        row.addWidget(next_button)
        row.addWidget(close_button)
        self.find_panel.hide()

    def show_find_panel(self) -> None:
        self.find_panel.show()
        self.find_input.setFocus()
        self.find_input.selectAll()
        self._find_text_changed(self.find_input.text())

    def hide_find_panel(self) -> None:
        self.find_panel.hide()

    def _find_text_changed(self, query: str) -> None:
        tab = self.active_tab() if hasattr(self, "tabs") else None
        if not tab:
            self.find_count_label.setText("0/0")
            return
        total = tab.search_count(query, case_sensitive=self.find_case_box.isChecked())
        self.find_count_label.setText(f"0/{total}" if query else "0/0")

    def find_next(self, forward: bool = True) -> None:
        tab = self.active_tab()
        if not tab:
            return
        query = self.find_input.text()
        if not query:
            self.show_find_panel()
            return
        current, total = tab.find_text(query, forward=forward, case_sensitive=self.find_case_box.isChecked())
        self.find_count_label.setText(f"{current}/{total}")
        if total:
            self.statusBar().showMessage(f"Found {current} of {total}: {query}", 1400)
        else:
            self.statusBar().showMessage(f"No matches: {query}", 1600)

    def toggle_spellcheck(self) -> None:
        self.spell_enabled = not self.spell_enabled
        if self.spell_enabled and self.spell_checker is None:
            self.spell_checker = SimpleSpellChecker.from_system()
        self.spell_action.setText(f"Spell Check: {'ON' if self.spell_enabled else 'OFF'}")
        self.udata.set("spellcheck_enabled", "1" if self.spell_enabled else "0", section="HEADER")
        self.udata.save()
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, SwarTab):
                tab.set_spell_enabled(self.spell_enabled)
        self.statusBar().showMessage(f"Local spellcheck {'enabled' if self.spell_enabled else 'disabled'}.", 1800)

    def _add_widgets(self, layout: QHBoxLayout, widgets: list[QWidget | str]) -> None:
        for widget in widgets:
            if widget == "stretch":
                layout.addStretch(1)
            elif isinstance(widget, QWidget):
                widget.setParent(self.toolbar_host)
                layout.addWidget(widget)

    def _add_aligned_toolbar_row(
        self,
        layout: QHBoxLayout,
        *,
        left: list[QWidget] | None = None,
        center: list[QWidget] | None = None,
        right: list[QWidget] | None = None,
    ) -> None:
        """Add one responsive toolbar row with stable left / center / right zones.

        Program actions live on the left, editor insert tools live in the center,
        and high-importance settings live on the right.  The two stretches keep
        the editor tool zone visually centered when a row has room, while still
        allowing the row to compress on the phone-dimension script monitor.
        """
        left = left or []
        center = center or []
        right = right or []
        self._add_widgets(layout, left)
        layout.addStretch(1)
        self._add_widgets(layout, center)
        layout.addStretch(1)
        self._add_widgets(layout, right)


    def _make_snippet_button(self, group: str, text: str | None = None) -> QToolButton:
        button = QToolButton()
        button.setText(text or group)
        button.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(button)
        for snippet in self.snippet_groups.get(group, SNIPPET_GROUPS.get(group, [])):
            act = QAction(snippet.label, self)
            act.setToolTip(snippet.description)
            act.triggered.connect(lambda checked=False, snip=snippet: self.insert_snippet(snip))
            menu.addAction(act)
        button.setMenu(menu)
        return button

    def _make_emoji_button(self) -> QToolButton:
        button = QToolButton()
        button.setText("Emoji")
        button.setPopupMode(QToolButton.InstantPopup)
        self.emoji_menu = QMenu(button)
        self._emoji_menu_action = None
        self._emoji_list = None
        self._emoji_filter = None
        self._rebuild_emoji_menu()
        button.setMenu(self.emoji_menu)
        return button

    def _rebuild_emoji_menu(self) -> None:
        entries, path = load_current_emoji()
        self.emoji_entries = entries
        self.emoji_source_path = path
        if not hasattr(self, "emoji_menu"):
            return
        self.emoji_menu.clear()
        if not entries:
            act = QAction("No current.emoji found", self)
            act.setEnabled(False)
            self.emoji_menu.addAction(act)
            reload_act = QAction("Reload Emoji", self)
            reload_act.triggered.connect(self._reload_emoji_menu)
            self.emoji_menu.addAction(reload_act)
            return

        container = QWidget()
        box = QVBoxLayout(container)
        box.setContentsMargins(6, 6, 6, 6)
        box.setSpacing(4)
        self._emoji_filter = QLineEdit()
        self._emoji_filter.setPlaceholderText("Filter emoji by icon, name, or group...")
        self._emoji_list = QListWidget()
        self._emoji_list.setMinimumWidth(310)
        self._emoji_list.setMinimumHeight(220)
        self._emoji_list.setMaximumHeight(280)
        box.addWidget(self._emoji_filter)
        box.addWidget(self._emoji_list)

        widget_action = QWidgetAction(self.emoji_menu)
        widget_action.setDefaultWidget(container)
        self.emoji_menu.addAction(widget_action)
        self._populate_emoji_list("")
        self._emoji_filter.textChanged.connect(self._populate_emoji_list)
        self._emoji_list.itemActivated.connect(self._emoji_item_chosen)
        self._emoji_list.itemClicked.connect(self._emoji_item_chosen)

        source_label = f"Loaded: {path.name}" if path else "Loaded emoji list"
        source_act = QAction(source_label, self)
        source_act.setEnabled(False)
        self.emoji_menu.addAction(source_act)
        reload_act = QAction("Reload Emoji", self)
        reload_act.triggered.connect(self._reload_emoji_menu)
        self.emoji_menu.addAction(reload_act)

    def _populate_emoji_list(self, query: str = "") -> None:
        if self._emoji_list is None:
            return
        self._emoji_list.clear()
        needle = (query or "").strip().lower()
        shown = 0
        for idx, entry in enumerate(getattr(self, "emoji_entries", [])):
            if needle and needle not in entry.search_text:
                continue
            item = QListWidgetItem(entry.display_text)
            item.setToolTip(f"{entry.label} | {entry.category}")
            item.setData(Qt.UserRole, idx)
            self._emoji_list.addItem(item)
            shown += 1
            if shown >= 250:
                break

    def _emoji_item_chosen(self, item: QListWidgetItem) -> None:
        idx = item.data(Qt.UserRole)
        try:
            entry = self.emoji_entries[int(idx)]
        except Exception:
            return
        self.insert_emoji(entry)
        if hasattr(self, "emoji_menu"):
            self.emoji_menu.hide()

    def _reload_emoji_menu(self) -> None:
        self._rebuild_emoji_menu()
        count = len(getattr(self, "emoji_entries", []))
        self.statusBar().showMessage(f"Reloaded {count} emoji from current.emoji.", 1800)

    def _merged_snippet_groups(self) -> dict[str, list[Snippet]]:
        groups = {name: list(snips) for name, snips in SNIPPET_GROUPS.items()}
        for group, snippet in self.udata.custom_snippets():
            target = group if group in groups else "Template"
            groups.setdefault(target, [])
            groups[target].append(snippet)
        return groups

    def _build_editor_tools(self) -> None:
        self.snippet_groups = self._merged_snippet_groups()
        self.sections_button = self._make_snippet_button("Sections", "Sections")
        self.subsections_button = self._make_snippet_button("Sub-Sections", "Sub-Sect")
        self.endsect_button = self._make_snippet_button("End-Sect", "End-Sect")
        self.source_button = self._make_snippet_button("Source", "Source")
        self.emoji_button = self._make_emoji_button()
        self.markdown_button = self._make_snippet_button("Markdown", "MD")
        self.template_button = self._make_snippet_button("Template", "Template")
        self.editor_tool_buttons = [
            self.sections_button, self.subsections_button, self.endsect_button,
            self.source_button, self.emoji_button, self.markdown_button, self.template_button,
        ]

    def _reflow_toolbar(self) -> None:
        if not hasattr(self, "toolbar_row_layouts"):
            return
        width = max(0, self.width())
        for layout in self.toolbar_row_layouts:
            _clear_layout(layout)
            layout.setSpacing(3)
        for row in self.toolbar_rows:
            row.hide()

        # Phase 3A-R3 toolbar policy:
        #   left   = program actions
        #   center = editor-specific insert tools
        #   right  = important settings
        # Sections and Source are protected editor controls and remain on the
        # top row for every width.  The other editor tools wrap down first.
        #
        # The previous R2 thresholds were tuned too close to the edge on a
        # fractionally-scaled KDE desktop, which caused odd early wrapping on
        # larger screens and late text squeezing on phone-width monitors.  These
        # thresholds intentionally keep one row longer, then add rows before
        # allowing button text to squeeze.
        settings_full = [self.theme_box, self.sep_theme_mode, self.mode_box, self.sep_mode_network, self.network_box]
        settings_compact = [self.theme_box, self.sep_theme_network, self.network_box]
        editor_primary = [self.sections_button, self.source_button]
        editor_secondary = [self.subsections_button, self.endsect_button, self.emoji_button, self.markdown_button, self.template_button]
        program_full = [self.open_button, self.new_button, self.reload_button, self.refresh_button, self.tools_button, self.save_button, self.outline_button]
        program_core = [self.open_button, self.save_button]
        program_extra = [self.new_button, self.reload_button, self.refresh_button, self.tools_button, self.outline_button]

        if width >= 1080:
            self._add_aligned_toolbar_row(
                self.toolbar_row_layouts[0],
                left=program_full,
                center=[self.sections_button, self.subsections_button, self.endsect_button, self.source_button, self.emoji_button, self.markdown_button, self.template_button],
                right=settings_full,
            )
            self.toolbar_rows[0].show()
        elif width >= 820:
            self._add_aligned_toolbar_row(
                self.toolbar_row_layouts[0],
                left=program_full,
                center=editor_primary,
                right=settings_full,
            )
            self._add_aligned_toolbar_row(
                self.toolbar_row_layouts[1],
                left=[],
                center=editor_secondary,
                right=[],
            )
            self.toolbar_rows[0].show()
            self.toolbar_rows[1].show()
        elif width >= 620:
            self._add_aligned_toolbar_row(
                self.toolbar_row_layouts[0],
                left=program_core,
                center=editor_primary,
                right=settings_full,
            )
            self._add_aligned_toolbar_row(
                self.toolbar_row_layouts[1],
                left=program_extra,
                center=editor_secondary,
                right=[],
            )
            self.toolbar_rows[0].show()
            self.toolbar_rows[1].show()
        elif width >= 500:
            self._add_aligned_toolbar_row(
                self.toolbar_row_layouts[0],
                left=program_core,
                center=editor_primary,
                right=[self.mode_box],
            )
            self._add_aligned_toolbar_row(
                self.toolbar_row_layouts[1],
                left=program_extra,
                center=editor_secondary,
                right=settings_compact,
            )
            self.toolbar_rows[0].show()
            self.toolbar_rows[1].show()
        elif width >= 360:
            self._add_aligned_toolbar_row(
                self.toolbar_row_layouts[0],
                left=program_core,
                center=editor_primary,
                right=[self.mode_box],
            )
            self._add_aligned_toolbar_row(
                self.toolbar_row_layouts[1],
                left=[self.new_button, self.reload_button],
                center=[self.subsections_button, self.endsect_button],
                right=[self.network_box],
            )
            self._add_aligned_toolbar_row(
                self.toolbar_row_layouts[2],
                left=[self.refresh_button, self.outline_button],
                center=[self.emoji_button, self.markdown_button, self.template_button],
                right=[self.theme_box],
            )
            self.toolbar_rows[0].show()
            self.toolbar_rows[1].show()
            self.toolbar_rows[2].show()
        else:
            self._add_aligned_toolbar_row(
                self.toolbar_row_layouts[0],
                left=program_core,
                center=[],
                right=[self.mode_box],
            )
            self._add_aligned_toolbar_row(
                self.toolbar_row_layouts[1],
                left=[self.new_button, self.reload_button],
                center=editor_primary,
                right=[self.network_box],
            )
            self._add_aligned_toolbar_row(
                self.toolbar_row_layouts[2],
                left=[self.refresh_button, self.outline_button],
                center=[self.subsections_button, self.endsect_button],
                right=[self.theme_box],
            )
            self._add_aligned_toolbar_row(
                self.toolbar_row_layouts[3],
                left=[],
                center=[self.emoji_button, self.markdown_button, self.template_button],
                right=[],
            )
            self.toolbar_rows[0].show()
            self.toolbar_rows[1].show()
            self.toolbar_rows[2].show()
            self.toolbar_rows[3].show()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reflow_toolbar()

    def new_tab(self) -> None:
        text = '3D Changes Perspectives:: New SWAR Script: Draft\n\n"Start writing here."\n'
        tab = SwarTab(self, TabState(path=None, text=text, mode="reader" if self.reader_only else "split"))
        tab.set_theme()
        idx = self.tabs.addTab(tab, "Untitled.script")
        self.tabs.setCurrentIndex(idx)
        self.refresh_tab_title(tab)
        self.update_toolbar_state()

    def open_file_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Open SWAR files", "", "Scripts (*.script *.md *.txt);;All Files (*)")
        for path in paths:
            self.open_path(path)

    def open_path(self, path: str) -> None:
        p = Path(path)
        text = p.read_text(encoding="utf-8", errors="replace")
        tab = SwarTab(self, TabState(path=str(p), text=text, mode="reader"))
        tab.set_theme()
        idx = self.tabs.addTab(tab, p.name)
        self.tabs.setCurrentIndex(idx)
        self.udata.set("last_file", str(p), section="HEADER")
        self.udata.save()
        self.refresh_tab_title(tab)
        self.update_toolbar_state()

    def active_tab(self) -> SwarTab | None:
        widget = self.tabs.currentWidget()
        return widget if isinstance(widget, SwarTab) else None

    def _active_tab_changed(self, index: int) -> None:
        self.udata.set("last_tab_index", str(max(0, index)), section="HEADER")
        self.udata.save()
        self.update_toolbar_state()
        self.update_footer()

    def close_tab(self, index: int) -> None:
        tab = self.tabs.widget(index)
        if isinstance(tab, SwarTab) and tab.state.dirty:
            choice = QMessageBox.question(self, "SWAR", "This tab has unsaved changes. Close anyway?")
            if choice != QMessageBox.Yes:
                return
        self.tabs.removeTab(index)
        if self.tabs.count() == 0:
            self.new_tab()

    def refresh_tab_title(self, tab: SwarTab) -> None:
        idx = self.tabs.indexOf(tab)
        if idx < 0:
            return
        name = Path(tab.state.path).name if tab.state.path else "Untitled.script"
        if tab.state.dirty:
            name = "*" + name
        self.tabs.setTabText(idx, name)

    def reload_file(self) -> None:
        tab = self.active_tab()
        if not tab or not tab.state.path:
            self.statusBar().showMessage("No saved file path to reload.", 1800)
            return
        p = Path(tab.state.path)
        tab.set_text(p.read_text(encoding="utf-8", errors="replace"), from_file=True)
        self.refresh_tab_title(tab)
        self.statusBar().showMessage("Reloaded from disk.", 1800)

    def refresh_preview(self) -> None:
        tab = self.active_tab()
        if not tab:
            return
        tab.parse_and_render()
        self.statusBar().showMessage("Reader preview refreshed.", 1600)

    def debounce_preview_refresh(self, tab: SwarTab) -> None:
        self._preview_tab = tab
        self._preview_timer.start(650)

    def _run_debounced_preview(self) -> None:
        if self._preview_tab is not None:
            self._preview_tab.parse_and_render()

    def save_action(self, action_key: str) -> None:
        tab = self.active_tab()
        if not tab:
            return
        text = tab.current_text()
        current = tab.state.path
        extension = None
        dialog = False
        if action_key == "save_as":
            dialog = True
        elif action_key == "save_script":
            extension = "script"
        elif action_key == "save_marked":
            extension = "md"
        elif action_key == "save_text":
            extension = "txt"

        path: Path
        if dialog:
            suggested = str(resolve_save_path(current, extension or "script")) if current else str(auto_save_path("script"))
            selected, _ = QFileDialog.getSaveFileName(self, "Save SWAR file", suggested, "SWAR Script (*.script);;Markdown (*.md);;Text (*.txt);;All Files (*)")
            path = Path(selected) if selected else auto_save_path("script")
        else:
            path = resolve_save_path(current, extension)

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        tab.state.path = str(path)
        tab.state.dirty = False
        tab.parse_and_render()
        self.refresh_tab_title(tab)
        self.udata.bump_counter("save_count")
        self.udata.set("last_file", str(path), section="HEADER")
        self.udata.save()
        self.statusBar().showMessage(f"Saved: {path}", 2600)

    def export_outline(self) -> None:
        tab = self.active_tab()
        if not tab:
            return
        tab.parse_and_render()
        if not tab.state.doc:
            return
        if tab.state.path:
            out = export_outline(tab.state.doc, tab.state.path)
        else:
            out = auto_save_path("txt").with_name("untitled_outline.txt")
            out.write_text("\n\n" + tab.state.doc.header_first_line + "\n\n" + "\n".join(tab.state.doc.source_links) + "\n\n", encoding="utf-8")
        self.statusBar().showMessage(f"Outline exported: {out}", 3200)

    def insert_snippet(self, snippet: Snippet) -> None:
        tab = self.active_tab()
        if not tab:
            return
        if tab.state.mode == "reader":
            self.statusBar().showMessage("Switch to Editor or Split mode to use editor tools.", 2200)
            return
        tab.insert_snippet(snippet)
        if tab.state.mode == "split":
            tab.parse_and_render()
        self.update_toolbar_state()
        self.statusBar().showMessage(f"Inserted: {snippet.label}", 1600)

    def insert_emoji(self, entry: EmojiEntry) -> None:
        tab = self.active_tab()
        if not tab:
            return
        if tab.state.mode == "reader":
            self.statusBar().showMessage("Switch to Editor or Split mode to use emoji tools.", 2200)
            return
        tab.insert_snippet(Snippet(label=entry.label, text=entry.symbol, cursor_back=0, description=entry.category))
        if tab.state.mode == "split":
            tab.parse_and_render()
        self.update_toolbar_state()
        self.statusBar().showMessage(f"Inserted emoji: {entry.symbol} {entry.label}", 1600)

    def change_theme_display(self, label: str) -> None:
        self.change_theme(THEME_FROM_DISPLAY.get(label, label))

    def change_theme(self, name: str) -> None:
        self.theme_name = name
        self.udata.set("current_theme", name, section="HEADER")
        self.udata.save()
        self.apply_theme()
        for i in range(self.tabs.count()):
            tab = self.tabs.widget(i)
            if isinstance(tab, SwarTab):
                tab.set_theme()
        if hasattr(self, "theme_box"):
            self.theme_box.blockSignals(True)
            self.theme_box.setCurrentText(THEME_DISPLAY.get(name, name))
            self.theme_box.blockSignals(False)
        self.statusBar().showMessage(f"Theme changed to {name}.", 1800)

    def apply_theme(self) -> None:
        theme = get_theme(self.theme_name)
        self.setStyleSheet(
            f"QMainWindow, QWidget {{ background: {theme.bg}; color: {theme.text}; }}"
            f"QToolBar {{ background: {theme.panel}; border-bottom: 1px solid {theme.border}; spacing: 4px; }}"
            f"QTabWidget::pane {{ border: 1px solid {theme.border}; }}"
            f"QTabBar::tab {{ background: {theme.panel}; color: {theme.text}; padding: 6px 10px; }}"
            f"QTabBar::tab:selected {{ color: {theme.highlight}; border-bottom: 2px solid {theme.highlight}; }}"
            f"QLabel {{ color: {theme.text}; }}"
            f"QComboBox, QToolButton, QPushButton {{ background: {theme.panel}; color: {theme.text}; border: 1px solid {theme.border}; padding: 3px; }}"
            f"QMenu {{ background: {theme.panel}; color: {theme.text}; border: 1px solid {theme.border}; }}"
            f"QMenu::item:selected {{ background: {theme.highlight}; color: {theme.bg}; }}"
            f"QStatusBar {{ background: {theme.panel}; color: {theme.text}; }}"
        )
        self.footer.setStyleSheet(f"color:{theme.text}; background:{theme.panel}; padding: 3px;")

    def change_mode(self, label: str) -> None:
        tab = self.active_tab()
        if not tab:
            return
        requested = label.lower()
        if requested == "reader":
            tab.set_mode("reader")
        elif requested in {"editor", "split"}:
            if self.reader_only:
                decision = self._reader_edit_prompt()
                if decision == "cancel":
                    self.mode_box.blockSignals(True)
                    self.mode_box.setCurrentText("Reader")
                    self.mode_box.blockSignals(False)
                    return
                tab.state.network_mode = "online" if decision == "online" else "local"
                self.reader_only = False
            tab.set_mode("editor" if requested == "editor" else "split")
        self.update_toolbar_state()
        self.update_footer()

    def _reader_edit_prompt(self) -> str:
        box = QMessageBox(self)
        box.setWindowTitle("SWAR Reader Mode")
        box.setText("Do you want to activate editing for this reader session?")
        online = box.addButton("Edit Online", QMessageBox.AcceptRole)
        local = box.addButton("Local Edit", QMessageBox.AcceptRole)
        cancel = box.addButton("Cancel Edit", QMessageBox.RejectRole)
        box.exec()
        clicked = box.clickedButton()
        if clicked == online:
            return "online"
        if clicked == local:
            return "local"
        return "cancel"

    def change_network(self, label: str) -> None:
        tab = self.active_tab()
        if not tab:
            return
        requested = NETWORK_FROM_DISPLAY.get(label, "local")
        if self.reader_only and requested == "online":
            self.network_box.blockSignals(True)
            self.network_box.setCurrentText("LOCAL")
            self.network_box.blockSignals(False)
            self.statusBar().showMessage("Reader mode stays local-only until editing is activated.", 2400)
            return
        tab.state.network_mode = requested
        tab.parse_and_render()
        self.update_toolbar_state()

    def update_toolbar_state(self) -> None:
        tab = self.active_tab()
        if not tab:
            return
        self.mode_box.blockSignals(True)
        self.mode_box.setCurrentText({"reader": "Reader", "editor": "Editor", "split": "Split"}.get(tab.state.mode, "Reader"))
        self.mode_box.blockSignals(False)
        self.network_box.blockSignals(True)
        self.network_box.setCurrentText(NETWORK_DISPLAY.get(tab.state.network_mode, "LOCAL"))
        self.network_box.blockSignals(False)
        if hasattr(self, "theme_box"):
            self.theme_box.blockSignals(True)
            self.theme_box.setCurrentText(THEME_DISPLAY.get(self.theme_name, "NIGHT"))
            self.theme_box.blockSignals(False)
        tools_enabled = tab.state.mode in {"editor", "split"}
        for button in getattr(self, "editor_tool_buttons", []):
            button.setEnabled(tools_enabled)

    def handle_anchor(self, url: QUrl) -> None:
        value = url.toString()
        if value.startswith("copy:"):
            text = unquote(value[5:])
            QGuiApplication.clipboard().setText(text)
            self.statusBar().showMessage("Copied to clipboard.", 1800)
            try:
                QToolTip.showText(QGuiApplication.cursor().pos(), "Copied to clipboard.", self, msecShowTime=900)
            except Exception:
                pass

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt method name
        self.udata.set("last_window_width", str(max(0, self.width())), section="POST-BODY")
        self.udata.set("last_window_height", str(max(0, self.height())), section="POST-BODY")
        tab = self.active_tab()
        if tab and tab.state.path:
            self.udata.set("last_file", tab.state.path, section="HEADER")
        self.udata.save()
        super().closeEvent(event)

    def update_footer(self) -> None:
        tab = self.active_tab()
        if not tab:
            self.footer.setText("Lines: 0    Section: none    0% through file    type: UTF-8    ext: none    size: 0 bytes :: 0 B    sections: 0")
            return
        bar = tab.active_scrollbar()
        maxv = max(1, bar.maximum())
        pct = int((bar.value() / maxv) * 100) if maxv else 0
        text = tab.current_text()
        total_lines = len(text.splitlines())
        if tab.state.path and Path(tab.state.path).exists():
            size = Path(tab.state.path).stat().st_size
            ext = Path(tab.state.path).suffix.lstrip(".") or "none"
        else:
            size = len(text.encode("utf-8"))
            ext = "script"
        doc = tab.state.doc
        section = section_for_scroll(doc, pct)
        sections = doc.section_count if doc else 0
        dirty = "unsaved" if tab.state.dirty else "saved"
        cursor_segment = ""
        block_segment = ""
        if tab.state.mode in {"editor", "split"}:
            line_no, col_no = tab.cursor_line_col()
            cursor_segment = f"cursor: L{line_no}:C{col_no}"
            block = tab.block_for_line(line_no)
            if block is not None:
                block_segment = f"block: {block.kind}"
                if block.text:
                    block_segment += f"[{block.line_start}-{block.line_end}]"
        segments = [
            f"Lines: {total_lines}",
            f"Section: {section}",
        ]
        if cursor_segment:
            segments.append(cursor_segment)
        if block_segment:
            segments.append(block_segment)
        segments.extend([
            f"{pct}% through file",
            "type: len-us + UTF-8",
            f"ext: {ext}",
            f"size: {size} bytes :: {short_bytes(size).replace(' ', ' ')}",
            f"sections: {sections}",
            f"tab: {self.tabs.currentIndex() + 1}/{self.tabs.count()}",
            dirty,
        ])
        self.footer.setText("    ".join(segments))


def run_shell(file_path: str | None = None, udata_path: str = "SWAR.udata", reader_only: bool = False) -> int:
    if _PYSIDE_IMPORT_ERROR is not None:
        print("PySide6 is required for the SWAR shell.", file=sys.stderr)
        print("Install on Kubuntu with: python3 -m pip install PySide6", file=sys.stderr)
        print(f"Import error: {_PYSIDE_IMPORT_ERROR}", file=sys.stderr)
        return 2
    app = QApplication(sys.argv)
    win = SwarShellWindow(file_path=file_path, udata_path=udata_path, reader_only=reader_only)
    win.show()
    return app.exec()
