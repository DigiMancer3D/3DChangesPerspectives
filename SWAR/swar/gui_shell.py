from __future__ import annotations

from dataclasses import dataclass
from bisect import bisect_right
from pathlib import Path
import re
import sys
import time
from urllib.parse import unquote

from .parser import SwarParser, ScriptDoc
from .renderer_html import render_doc_html
from .outline import export_outline
from .themes import THEMES, get_theme
from .udata import UData
from .save_ops import resolve_save_path, auto_save_path, short_bytes, section_for_scroll
from .editor_tools import SNIPPET_GROUPS, Snippet
from .emoji_tools import EmojiEntry, load_current_emoji
from .local_tools import SimpleSpellChecker, find_matches, word_bounds_at
from .arc_tools import ARC_SNIPPET_GROUPS, new_arc_template

try:
    from PySide6.QtCore import Qt, QUrl, QTimer, QSize, QEvent
    from PySide6.QtGui import QAction, QGuiApplication, QFont, QTextOption, QSyntaxHighlighter, QTextCharFormat, QColor, QTextCursor, QPainter, QTextDocument, QKeySequence
    from PySide6.QtWidgets import (
        QApplication, QComboBox, QFileDialog, QHBoxLayout, QLabel, QMainWindow,
        QCheckBox, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QMenu, QPlainTextEdit, QPushButton, QScrollBar, QSplitter,
        QTabWidget, QTextBrowser, QToolBar, QToolButton, QToolTip, QVBoxLayout, QSlider,
        QWidget, QWidgetAction, QDialog, QDialogButtonBox, QAbstractItemView,
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

# Split/Story linked scrolling is editor-led.  Reader positions are calculated
# from source-line anchors embedded in the rendered document, so tall fancy
# boxes and deliberate vertical-gap marks are included instead of guessed.
SHARED_SCROLL_STEPS = 10000
LINKED_READER_LOOKAHEAD_LINES = 0.35
TOOLBAR_EDGE_PADDING = 18


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
    mode: str = "reader"  # reader | editor | split | story
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
            self.f_heading_levels = []
            for point_size in (20, 18, 16, 15, 14, 13):
                heading_fmt = self._fmt(theme.markdown_heading, bold=True)
                heading_fmt.setFontPointSize(point_size)
                self.f_heading_levels.append(heading_fmt)
            self.f_markdown2 = self._fmt(theme.fade_green1, bold=True)
            self.f_color_profile = self._fmt(theme.highlight3, bold=True)
            self.f_color_escape = self._fmt(theme.muted, italic=True)
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
            heading_match = re.match(r"^\s{0,3}(#{1,6})\s+", text)
            heading_applied = False
            if heading_match:
                level = min(6, len(heading_match.group(1)))
                self.setFormat(0, len(text), self.f_heading_levels[level - 1])
                heading_applied = True
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
                arrow_match = re.match(r"^(>+)", stripped)
            if arrow_match and "<<" in stripped:
                self.setFormat(0, len(text), self._arrow_format(len(arrow_match.group(1))))
            if stripped.startswith(">>") and "!!" in stripped:
                self.setFormat(0, len(text), self.f_important)
            if stripped.startswith("!!") or stripped.endswith("!!<<") or stripped.endswith("!!<<<"):
                self.setFormat(0, len(text), self.f_important)
            if stripped.startswith("```"):
                self.setFormat(0, len(text), self.f_important)
            if stripped.startswith('"') or stripped.endswith('"'):
                if "!!" not in stripped and not stripped.startswith(">"):
                    self.setFormat(0, len(text), self.f_quote)
            if not heading_applied:
                for marker in ("```", "~~", "`", "[", "](", "-# ", "***", "**", "___", "__", "#", "|", "- [ ]", "- [x]", "- [#]", "- [$]", "- [%", "> ", ">>"):
                    pos = text.find(marker)
                    if pos >= 0 and not (pos > 0 and text[pos - 1] == "\\"):
                        self.setFormat(pos, min(len(text) - pos, max(2, len(marker) + 80)), self.f_markdown)
                        break
            color_token = r"(?:\[#[0-9A-Fa-f]{3,8}\]|\((?:rgba?)\([^()\n]*\)\))"
            escaped_color = re.search(r"\\`!\s*" + color_token + r"\s*$", text, re.IGNORECASE)
            active_color = re.search(color_token + r"\s*$", text, re.IGNORECASE)
            if escaped_color:
                self.setFormat(escaped_color.start(), len(text) - escaped_color.start(), self.f_color_escape)
            elif active_color:
                self.setFormat(active_color.start(), len(text) - active_color.start(), self.f_color_profile)

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
            self.swar_tab: "SwarTab | None" = None
            self._context_menu: QMenu | None = None
            self._context_click_position = 0
            self._right_press_global = None
            self._right_press_pending = False
            self._right_gesture_used = False
            self.line_number_area = LineNumberArea(self)
            self.blockCountChanged.connect(self.update_line_number_area_width)
            self.updateRequest.connect(self.update_line_number_area)
            self.cursorPositionChanged.connect(self.highlight_current_line)
            self.update_line_number_area_width(0)
            app = QApplication.instance()
            if app is not None:
                app.installEventFilter(self)

        @staticmethod
        def _event_point(event):
            try:
                return event.position().toPoint()
            except Exception:
                return event.pos()

        @staticmethod
        def _event_global_point(event):
            try:
                return event.globalPosition().toPoint()
            except Exception:
                try:
                    return event.globalPos()
                except Exception:
                    return None

        @staticmethod
        def _editor_at_global(global_point):
            app = QApplication.instance()
            if app is None or global_point is None:
                return None
            for widget in app.allWidgets():
                if isinstance(widget, SwarPlainTextEdit) and widget.isVisible():
                    local = widget.viewport().mapFromGlobal(global_point)
                    if widget.viewport().rect().contains(local):
                        return widget
            return None

        def eventFilter(self, watched, event):  # noqa: N802 - Qt method name
            menu = self._context_menu
            if menu is not None and menu.isVisible() and event.type() == QEvent.Type.MouseButtonPress:
                global_point = self._event_global_point(event)
                if global_point is not None and not menu.geometry().contains(global_point):
                    if event.button() == Qt.MouseButton.RightButton:
                        replacement_editor = self._editor_at_global(global_point)
                        menu.close()
                        if replacement_editor is not None:
                            QTimer.singleShot(0, lambda ed=replacement_editor, gp=global_point: ed._show_context_menu(gp))
                        return True
                    if event.button() == Qt.MouseButton.LeftButton:
                        menu.close()
            return super().eventFilter(watched, event)

        def _prepare_context_position(self, global_point) -> None:
            local_point = self.viewport().mapFromGlobal(global_point)
            clicked_cursor = self.cursorForPosition(local_point)
            self._context_click_position = clicked_cursor.position()
            active_cursor = self.textCursor()
            # Preserve a user selection for Copy/Cut.  With no selection, the
            # press immediately moves the caret to the right-clicked location.
            if not active_cursor.hasSelection():
                self.setTextCursor(clicked_cursor)

        def cancel_pending_context_menu(self) -> None:
            self._right_gesture_used = True

        def mousePressEvent(self, event) -> None:  # noqa: N802 - Qt method name
            if event.button() == Qt.MouseButton.RightButton:
                global_point = self._event_global_point(event)
                if global_point is not None:
                    self._prepare_context_position(global_point)
                    self._right_press_global = global_point
                    self._right_press_pending = True
                    self._right_gesture_used = False
                event.accept()
                return
            super().mousePressEvent(event)

        def mouseReleaseEvent(self, event) -> None:  # noqa: N802 - Qt method name
            if event.button() == Qt.MouseButton.RightButton and self._right_press_pending:
                global_point = self._event_global_point(event) or self._right_press_global
                should_open = not self._right_gesture_used
                self._right_press_pending = False
                self._right_press_global = None
                self._right_gesture_used = False
                if should_open and global_point is not None:
                    self._show_context_menu(global_point, position_prepared=True)
                event.accept()
                return
            super().mouseReleaseEvent(event)

        def contextMenuEvent(self, event) -> None:  # noqa: N802 - Qt method name
            # Mouse context menus are opened from mouseReleaseEvent so a held
            # right-click can remain available for Linked Scrolling.  Keyboard
            # context-menu requests still use the normal event path.
            if self._right_press_pending or (self._context_menu is not None and self._context_menu.isVisible()):
                event.accept()
                return
            self._show_context_menu(event.globalPos())
            event.accept()

        def _show_context_menu(self, global_point, *, position_prepared: bool = False) -> None:
            if global_point is None:
                return
            if self._context_menu is not None:
                self._context_menu.close()
                self._context_menu.deleteLater()
                self._context_menu = None

            if not position_prepared:
                self._prepare_context_position(global_point)

            menu = self.createStandardContextMenu()
            self._context_menu = menu
            tab = self.swar_tab
            shell = getattr(tab, "shell", None)
            checker = getattr(shell, "spell_checker", None)
            if getattr(shell, "spell_enabled", False) and checker is not None:
                plain = self.toPlainText()
                bounds = word_bounds_at(plain, self._context_click_position)
                if bounds is not None:
                    start, end, word = bounds
                    if not checker.is_known(word):
                        suggestions = checker.suggestions(word)
                        menu.addSeparator()
                        title = QAction(f"Spelling: {word}", menu)
                        title.setEnabled(False)
                        menu.addAction(title)
                        if suggestions:
                            for suggestion in suggestions:
                                action = QAction(suggestion, menu)
                                action.triggered.connect(
                                    lambda checked=False, a=start, b=end, value=suggestion:
                                    self._replace_text_range(a, b, value)
                                )
                                menu.addAction(action)
                        else:
                            empty = QAction("No local suggestions", menu)
                            empty.setEnabled(False)
                            menu.addAction(empty)
            menu.aboutToHide.connect(self._context_menu_hidden)
            menu.popup(global_point)

        def _context_menu_hidden(self) -> None:
            menu = self._context_menu
            self._context_menu = None
            if menu is not None:
                menu.deleteLater()

        def _replace_text_range(self, start: int, end: int, value: str) -> None:
            cursor = self.textCursor()
            cursor.setPosition(max(0, start))
            cursor.setPosition(max(start, end), QTextCursor.MoveMode.KeepAnchor)
            cursor.insertText(value)
            self.setTextCursor(cursor)
            self.setFocus()

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
        # GUI-only Story section state. Empty means every Story layer is open,
        # so conversations and nested markup are never hidden on first render.
        self.story_collapsed_sections: set[str] = set()
        self._syncing_scroll = False
        self._right_scroll_held = False
        self._last_render_key: tuple[str, str, bool, str, str, str] | None = None
        self._teleprompter_fraction = 0.0
        # Some Qt/PySide6 builds emit textChanged while a syntax highlighter is
        # attached or rehighlighted, even before file text has been loaded.
        self._suppress_editor_change = True
        self._build_ui()
        self.set_text(state.text, from_file=True)
        self.set_mode(state.mode)
        self._suppress_editor_change = False

    def _build_ui(self) -> None:
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.editor = SwarPlainTextEdit()
        self.editor.swar_tab = self
        self.editor.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.editor.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.editor.setTabChangesFocus(False)
        self.editor.setUndoRedoEnabled(True)
        self.editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
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
        self.reader.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.reader.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.reader.anchorClicked.connect(self.shell.handle_anchor)

        self.editor_scroll = QScrollBar(Qt.Orientation.Horizontal)
        self.reader_scroll = QScrollBar(Qt.Orientation.Horizontal)
        self.editor_scroll.setToolTip("Editor vertical position")
        self.reader_scroll.setToolTip("Reader vertical position")
        self.editor_scroll.valueChanged.connect(lambda value: self._pane_proxy_changed("editor", value))
        self.reader_scroll.valueChanged.connect(lambda value: self._pane_proxy_changed("reader", value))

        self.editor_host = QWidget()
        editor_layout = QVBoxLayout(self.editor_host)
        editor_layout.setContentsMargins(0, 0, 0, 0)
        editor_layout.setSpacing(1)
        editor_layout.addWidget(self.editor, 1)
        editor_layout.addWidget(self.editor_scroll)

        self.reader_host = QWidget()
        reader_layout = QVBoxLayout(self.reader_host)
        reader_layout.setContentsMargins(0, 0, 0, 0)
        reader_layout.setSpacing(1)
        reader_layout.addWidget(self.reader, 1)
        reader_layout.addWidget(self.reader_scroll)

        self.splitter.addWidget(self.editor_host)
        self.splitter.addWidget(self.reader_host)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)

        # Shared Split/Story scroller.  It is always editor-led and uses the
        # source-line anchor map to place the Reader.  The two pane-specific
        # bars above remain independent for fine adjustment.
        self.bottom_scroll = QScrollBar(Qt.Orientation.Horizontal)
        self.bottom_scroll.setRange(0, SHARED_SCROLL_STEPS)
        self.bottom_scroll.setSingleStep(100)
        self.bottom_scroll.setPageStep(500)
        self.bottom_scroll.setToolTip("Shared editor-led Split/Story position")
        self.bottom_scroll.valueChanged.connect(self._bottom_scroll_changed)

        editor_bar = self.editor.verticalScrollBar()
        reader_bar = self.reader.verticalScrollBar()
        editor_bar.rangeChanged.connect(self.sync_scroll_range)
        reader_bar.rangeChanged.connect(self.sync_scroll_range)
        editor_bar.valueChanged.connect(lambda value: self._pane_scroll_changed("editor", value))
        reader_bar.valueChanged.connect(lambda value: self._pane_scroll_changed("reader", value))

        self._pane_proxy_source: str | None = None
        self._reader_line_positions: list[tuple[float, float]] = []
        for watched in (
            self.editor, self.reader,
            self.editor.viewport(), self.reader.viewport(), self.editor.line_number_area,
            self.editor_scroll, self.reader_scroll, self.bottom_scroll,
        ):
            watched.installEventFilter(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 0)
        layout.addWidget(self.splitter, 1)
        layout.addWidget(self.bottom_scroll)

    def eventFilter(self, watched, event):  # noqa: N802 - Qt method name
        event_type = event.type()
        if event_type == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.RightButton:
            self._right_scroll_held = True
        elif event_type == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.RightButton:
            self._right_scroll_held = False

        linked_gesture = self.state.mode in {"split", "story"} and (
            self.shell.linked_scroll_enabled or self._right_scroll_held
        )
        if linked_gesture and event_type == QEvent.Type.Wheel:
            amount = event.angleDelta().y()
            if amount:
                self.editor.cancel_pending_context_menu()
                units = max(1, round(abs(amount) / 120.0 * 3))
                self.scroll_both_by(-units if amount > 0 else units)
                return True
        if linked_gesture and event_type == QEvent.Type.KeyPress:
            editor_bar = self.editor.verticalScrollBar()
            mapping = {
                Qt.Key.Key_Up: -1,
                Qt.Key.Key_Down: 1,
                Qt.Key.Key_PageUp: -max(1, editor_bar.pageStep()),
                Qt.Key.Key_PageDown: max(1, editor_bar.pageStep()),
            }
            if event.key() in mapping:
                self.editor.cancel_pending_context_menu()
                self.scroll_both_by(mapping[event.key()])
                return True
        return super().eventFilter(watched, event)

    @staticmethod
    def _bar_ratio(bar) -> float:
        span = max(0, bar.maximum() - bar.minimum())
        if span <= 0:
            return 0.0
        return (bar.value() - bar.minimum()) / span

    @staticmethod
    def _set_bar_ratio(bar, ratio: float) -> None:
        span = max(0, bar.maximum() - bar.minimum())
        bar.setValue(bar.minimum() + round(max(0.0, min(1.0, ratio)) * span))

    def _editor_source_position(self) -> float:
        """Return the source-line position currently at the top of the editor."""
        block = self.editor.firstVisibleBlock()
        if not block.isValid():
            count = max(1, self.editor.blockCount())
            return 1.0 + self._bar_ratio(self.editor.verticalScrollBar()) * max(0, count - 1)
        top = float(self.editor.blockBoundingGeometry(block).translated(self.editor.contentOffset()).top())
        height = max(1.0, float(self.editor.blockBoundingRect(block).height()))
        fraction = max(0.0, min(1.0, -top / height))
        return float(block.blockNumber() + 1) + fraction

    def _editor_position_ratio(self) -> float:
        count = max(1, self.editor.blockCount())
        if count <= 1:
            return 0.0
        return max(0.0, min(1.0, (self._editor_source_position() - 1.0) / (count - 1)))

    def rebuild_reader_line_map(self) -> None:
        """Collect rendered Y positions for the source-line HTML anchors."""
        positions: dict[float, float] = {}
        document = self.reader.document()
        layout = document.documentLayout()
        block = document.begin()
        while block.isValid():
            try:
                top = float(layout.blockBoundingRect(block).top())
            except Exception:
                top = 0.0
            iterator = block.begin()
            while not iterator.atEnd():
                fragment = iterator.fragment()
                if fragment.isValid():
                    try:
                        names = fragment.charFormat().anchorNames()
                    except Exception:
                        names = []
                    for name in names:
                        match = re.fullmatch(r"swar-line-(\d+)", str(name))
                        if match:
                            positions[float(match.group(1))] = top
                iterator += 1
            block = block.next()
        self._reader_line_positions = sorted(positions.items())

    def _reader_y_for_source_position(self, source_position: float) -> float:
        points = self._reader_line_positions
        reader_bar = self.reader.verticalScrollBar()
        if not points:
            count = max(1, self.editor.blockCount())
            ratio = 0.0 if count <= 1 else (source_position - 1.0) / (count - 1)
            return max(reader_bar.minimum(), min(reader_bar.maximum(), ratio * reader_bar.maximum()))
        source_position = max(points[0][0], min(points[-1][0], float(source_position)))
        lines = [item[0] for item in points]
        index = bisect_right(lines, source_position) - 1
        if index < 0:
            return points[0][1]
        if index >= len(points) - 1:
            return points[-1][1]
        line0, y0 = points[index]
        line1, y1 = points[index + 1]
        if line1 <= line0:
            return y0
        fraction = (source_position - line0) / (line1 - line0)
        return y0 + (y1 - y0) * fraction

    def capture_view_position(self) -> dict[str, float | int]:
        cursor = self.editor.textCursor()
        return {
            "cursor": cursor.position(),
            "editor_ratio": self._bar_ratio(self.editor.verticalScrollBar()),
            "reader_ratio": self._bar_ratio(self.reader.verticalScrollBar()),
            "source_position": self._editor_source_position(),
        }

    def restore_view_position(self, state: dict[str, float | int] | None) -> None:
        if not state:
            return
        cursor = self.editor.textCursor()
        cursor.setPosition(max(0, min(int(state.get("cursor", 0)), len(self.editor.toPlainText()))))
        self.editor.setTextCursor(cursor)
        self._syncing_scroll = True
        self._set_bar_ratio(self.editor.verticalScrollBar(), float(state.get("editor_ratio", 0.0)))
        if self.state.mode in {"split", "story"}:
            self.sync_reader_to_editor_scroll()
        else:
            self._set_bar_ratio(self.reader.verticalScrollBar(), float(state.get("reader_ratio", 0.0)))
        self._syncing_scroll = False
        self.sync_scroll_range()

    def sync_reader_to_editor_scroll(self) -> None:
        source_position = self._editor_source_position()
        count = max(1, self.editor.blockCount())
        ratio = 0.0 if count <= 1 else max(0.0, min(1.0, (source_position - 1.0) / (count - 1)))
        # A very small middle-document lookahead keeps the Reader fractionally
        # ahead without breaking exact top/bottom alignment.  Source anchors
        # make this safe even beside seven- and thirteen-line gap marks.
        envelope = 4.0 * ratio * (1.0 - ratio)
        source_position += LINKED_READER_LOOKAHEAD_LINES * envelope
        target = round(self._reader_y_for_source_position(source_position))
        reader_bar = self.reader.verticalScrollBar()
        reader_bar.setValue(max(reader_bar.minimum(), min(reader_bar.maximum(), target)))

    def sync_reader_to_editor_cursor(self, cursor_y: float | None = None) -> None:
        # Compatibility entry point retained for older calls; scrolling is now
        # based on the top visible editor source line, not caret placement.
        self.sync_reader_to_editor_scroll()

    def set_text(self, text: str, from_file: bool = False) -> None:
        view = self.capture_view_position()
        self.state.text = text
        self._last_render_key = None
        self.editor.blockSignals(True)
        self.editor.setPlainText(text)
        self.editor.blockSignals(False)
        self.parse_and_render(force=True, restore_state=view)
        if from_file:
            self.state.dirty = False

    def current_text(self) -> str:
        if self.editor.toPlainText() != self.state.text:
            self.state.text = self.editor.toPlainText()
        return self.state.text

    def parse_and_render(self, *, force: bool = False, restore_state: dict[str, float | int] | None = None) -> None:
        text = self.current_text()
        parse_path = self.state.path or ""
        if self.state.mode == "story" and Path(parse_path).suffix.lower() != ".arcs":
            parse_path = str(Path(parse_path).with_suffix(".arcs")) if parse_path else "untitled.arcs"
        story_state_key = "|".join(sorted(self.story_collapsed_sections))
        render_key = (
            text,
            self.shell.theme_name,
            self.state.network_mode == "online",
            parse_path,
            self.state.mode,
            story_state_key,
        )
        if not force and render_key == self._last_render_key and self.state.doc is not None:
            self.shell.update_footer()
            return
        view = restore_state if restore_state is not None else self.capture_view_position()
        self.state.doc = self.parser.parse(text, path=parse_path)
        html = render_doc_html(
            self.state.doc,
            self.shell.theme_name,
            allow_online_links=self.state.network_mode == "online",
            story_collapsed=self.story_collapsed_sections,
        )
        self.reader.setHtml(html)
        self._last_render_key = render_key
        QTimer.singleShot(0, lambda state=view: self._finish_render_layout(state))
        self.shell.update_footer()

    def _finish_render_layout(self, state: dict[str, float | int] | None) -> None:
        self.rebuild_reader_line_map()
        self.restore_view_position(state)

    def set_mode(self, mode: str) -> None:
        view = self.capture_view_position()
        self.state.mode = mode
        if mode == "reader":
            self.editor_host.hide()
            self.reader_host.show()
            self.bottom_scroll.hide()
            self.parse_and_render(force=True, restore_state=view)
        elif mode == "editor":
            self.reader_host.hide()
            self.editor_host.show()
            self.bottom_scroll.hide()
        else:  # Split and Story both use the two-pane working view.
            self.editor_host.show()
            self.reader_host.show()
            self.bottom_scroll.show()
            self.parse_and_render(force=True, restore_state=view)
        QTimer.singleShot(0, self.sync_scroll_range)

    _STORY_SECTION_NAMES = ("opening", "flow", "data", "completion")

    def _rerender_story_sections(self, message: str) -> None:
        view = self.capture_view_position()
        self._last_render_key = None
        self.parse_and_render(force=True, restore_state=view)
        self.shell.statusBar().showMessage(message, 1600)

    def toggle_story_section(self, line: int, section: str) -> None:
        section = str(section or "").strip().lower()
        if section not in self._STORY_SECTION_NAMES:
            return
        key = f"{max(1, int(line))}:{section}"
        if key in self.story_collapsed_sections:
            self.story_collapsed_sections.remove(key)
            state = "expanded"
        else:
            self.story_collapsed_sections.add(key)
            state = "collapsed"
        self._rerender_story_sections(f"Story section {section} {state}.")

    def expand_story_arc(self, line: int) -> None:
        prefix = f"{max(1, int(line))}:"
        self.story_collapsed_sections = {
            key for key in self.story_collapsed_sections if not key.startswith(prefix)
        }
        self._rerender_story_sections("Expanded all Story sections for this Arc.")

    def collapse_story_arc(self, line: int) -> None:
        line = max(1, int(line))
        for section in self._STORY_SECTION_NAMES:
            self.story_collapsed_sections.add(f"{line}:{section}")
        self._rerender_story_sections("Collapsed all Story sections for this Arc.")

    def set_theme(self) -> None:
        theme = get_theme(self.shell.theme_name)
        self.editor.setStyleSheet(
            f"QPlainTextEdit {{ background: {theme.bg}; color: {theme.text}; "
            f"selection-background-color: {theme.highlight}; border: 2px solid {theme.border}; }}"
        )
        if self.highlighter is not None:
            self.highlighter.set_theme(self.shell.theme_name)
            self.highlighter.set_spell_enabled(self.shell.spell_enabled, self.shell.spell_checker)
        self.parse_and_render(force=True)

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
        widget = self.editor if self.state.mode in {"editor", "split", "story"} else self.reader
        found = widget.find(query, flags)
        if not found:
            cursor = widget.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start if forward else QTextCursor.MoveOperation.End)
            widget.setTextCursor(cursor)
            widget.find(query, flags)
        try:
            pos = widget.textCursor().selectionStart()
        except Exception:
            pos = 0
        current = 1
        for index, match in enumerate(matches, start=1):
            if match.start <= pos < match.end or pos <= match.start:
                current = index
                break
        return current, total

    def search_count(self, query: str, *, case_sensitive: bool = False) -> int:
        return len(find_matches(self.current_text(), query, case_sensitive=case_sensitive))

    def _editor_changed(self) -> None:
        text = self.editor.toPlainText()
        if getattr(self, "_suppress_editor_change", False):
            return
        if text == self.state.text:
            self.shell.update_footer()
            return
        self.state.text = text
        self.state.dirty = True
        self.shell.refresh_tab_title(self)
        if self.state.mode in {"split", "story"}:
            self.shell.debounce_preview_refresh(self)
        self.shell.update_footer()

    def _cursor_changed(self) -> None:
        if self.shell.linked_scroll_enabled and self.state.mode in {"split", "story"} and not self._syncing_scroll:
            self._syncing_scroll = True
            height = max(1, self.editor.viewport().height())
            self.sync_reader_to_editor_cursor(self.editor.cursorRect().top() / height)
            self._syncing_scroll = False
        self.shell.update_footer()

    def cursor_line_col(self) -> tuple[int, int]:
        cursor = self.editor.textCursor()
        return cursor.blockNumber() + 1, cursor.positionInBlock() + 1

    def block_for_line(self, line_no: int):
        doc = self.state.doc
        if doc is None or self.state.text != self.editor.toPlainText():
            parse_path = self.state.path or ""
            if self.state.mode == "story" and Path(parse_path).suffix.lower() != ".arcs":
                parse_path = str(Path(parse_path).with_suffix(".arcs")) if parse_path else "untitled.arcs"
            self.state.doc = self.parser.parse(self.current_text(), path=parse_path)
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
            cursor.movePosition(
                QTextCursor.MoveOperation.Left,
                QTextCursor.MoveMode.MoveAnchor,
                min(snippet.cursor_back, len(snippet.text)),
            )
            self.editor.setTextCursor(cursor)
        self.state.dirty = True
        self.shell.refresh_tab_title(self)
        self.shell.update_footer()

    def insert_inline_text(self, text: str) -> None:
        """Insert exactly at the caret; used by emoji and other inline tools."""
        if self.state.mode == "reader":
            return
        self.editor.setFocus()
        cursor = self.editor.textCursor()
        cursor.insertText(text)
        self.editor.setTextCursor(cursor)
        self.state.dirty = True
        self.shell.refresh_tab_title(self)
        self.shell.update_footer()

    def active_scrollbar(self):
        if self.state.mode in {"editor", "split", "story"}:
            return self.editor.verticalScrollBar()
        return self.reader.verticalScrollBar()

    def _pane_proxy_changed(self, source: str, value: int) -> None:
        if self._syncing_scroll:
            return
        bar = self.editor.verticalScrollBar() if source == "editor" else self.reader.verticalScrollBar()
        self._pane_proxy_source = source
        bar.setValue(value)
        self._pane_proxy_source = None
        self.sync_scroll_value()

    def _pane_scroll_changed(self, source: str, value: int) -> None:
        if self._syncing_scroll:
            return
        # Pane-specific bottom bars are intentionally independent for fine
        # adjustment.  Linked wheel/key/caret movement remains editor-led.
        independent_proxy = self._pane_proxy_source == source
        if (
            not independent_proxy
            and source == "editor"
            and self.state.mode in {"split", "story"}
            and self.shell.linked_scroll_enabled
        ):
            self._syncing_scroll = True
            self.sync_reader_to_editor_scroll()
            self._syncing_scroll = False
        self.sync_scroll_value()

    def scroll_both_by(self, amount: int) -> None:
        """Move both panes from editor source lines, independent of mouse side."""
        editor_bar = self.editor.verticalScrollBar()
        self._syncing_scroll = True
        editor_bar.setValue(max(editor_bar.minimum(), min(editor_bar.maximum(), editor_bar.value() + int(amount))))
        self.sync_reader_to_editor_scroll()
        self._syncing_scroll = False
        self.sync_scroll_value()

    def teleprompter_step(self, amount: float) -> None:
        self._teleprompter_fraction += amount
        whole = int(self._teleprompter_fraction)
        if whole == 0:
            return
        self._teleprompter_fraction -= whole
        if self.state.mode in {"split", "story"}:
            self.scroll_both_by(whole)
        else:
            bar = self.active_scrollbar()
            bar.setValue(max(bar.minimum(), min(bar.maximum(), bar.value() + whole)))

    @staticmethod
    def _mirror_bar(source_bar, proxy_bar) -> None:
        proxy_bar.blockSignals(True)
        proxy_bar.setMinimum(source_bar.minimum())
        proxy_bar.setMaximum(source_bar.maximum())
        proxy_bar.setPageStep(source_bar.pageStep())
        proxy_bar.setSingleStep(source_bar.singleStep())
        proxy_bar.setValue(source_bar.value())
        proxy_bar.blockSignals(False)

    def sync_scroll_range(self, *_args) -> None:
        if self._syncing_scroll:
            return
        editor_bar = self.editor.verticalScrollBar()
        self._mirror_bar(editor_bar, self.editor_scroll)
        self._mirror_bar(self.reader.verticalScrollBar(), self.reader_scroll)
        editor_span = max(1, editor_bar.maximum() - editor_bar.minimum())
        shared_single = max(1, round(SHARED_SCROLL_STEPS / editor_span))
        shared_page = max(
            shared_single,
            round(SHARED_SCROLL_STEPS * max(1, editor_bar.pageStep()) / editor_span),
        )
        self.bottom_scroll.blockSignals(True)
        self.bottom_scroll.setRange(0, SHARED_SCROLL_STEPS)
        self.bottom_scroll.setSingleStep(min(SHARED_SCROLL_STEPS, shared_single))
        self.bottom_scroll.setPageStep(min(SHARED_SCROLL_STEPS, shared_page))
        self.bottom_scroll.setValue(round(self._editor_position_ratio() * SHARED_SCROLL_STEPS))
        self.bottom_scroll.blockSignals(False)
        self.shell.update_footer()

    def sync_scroll_value(self) -> None:
        if self._syncing_scroll:
            return
        self._mirror_bar(self.editor.verticalScrollBar(), self.editor_scroll)
        self._mirror_bar(self.reader.verticalScrollBar(), self.reader_scroll)
        self.bottom_scroll.blockSignals(True)
        self.bottom_scroll.setValue(round(self._editor_position_ratio() * SHARED_SCROLL_STEPS))
        self.bottom_scroll.blockSignals(False)
        self.shell.update_footer()

    def _bottom_scroll_changed(self, value: int) -> None:
        if self.state.mode not in {"split", "story"}:
            return
        ratio = max(0.0, min(1.0, value / float(SHARED_SCROLL_STEPS)))
        self._syncing_scroll = True
        self._set_bar_ratio(self.editor.verticalScrollBar(), ratio)
        self.sync_reader_to_editor_scroll()
        self._syncing_scroll = False
        self.sync_scroll_value()

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
        truthy = {"1", "true", "TRUE", "yes", "YES", "on", "ON"}
        self.spell_enabled = self.udata.get("spellcheck_enabled", "0").strip() in truthy
        self.linked_scroll_enabled = self.udata.get("linked_scrolling_enabled", "0").strip() in truthy
        self.clean_start_enabled = self.udata.get("clean_start_enabled", "0").strip() in truthy
        self.teleprompter_enabled = self.udata.get("teleprompter_enabled", "0").strip() in truthy
        try:
            self.teleprompter_speed = int(self.udata.get("teleprompter_speed", "0"))
        except (TypeError, ValueError):
            self.teleprompter_speed = 0
        self.teleprompter_speed = max(-200, min(200, self.teleprompter_speed))
        self.teleprompter_paused = self.udata.get("teleprompter_paused", "1").strip() in truthy
        self._teleprompter_pause_until = 0.0
        self.spell_checker: SimpleSpellChecker | None = None
        if self.spell_enabled:
            self.spell_checker = SimpleSpellChecker.from_system()
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self._run_debounced_preview)
        self._preview_tab: SwarTab | None = None
        self._teleprompter_timer = QTimer(self)
        self._teleprompter_timer.setInterval(30)
        self._teleprompter_timer.timeout.connect(self._teleprompter_tick)
        self._teleprompter_timer.start()

        self.setWindowTitle("SWAR v0.7.1-rc1-r4 - Script Writer and Reader")
        self.resize(1040, 720)
        self.setMinimumSize(240, 260)
        self._build_ui()
        self.apply_theme()

        if file_path:
            self.open_path(file_path)
        else:
            self.new_tab(clean=self.clean_start_enabled)
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
        self._dynamic_toolbar_separators: list[QLabel] = []

        self.open_button = QPushButton("Open")
        self.open_button.clicked.connect(self.open_file_dialog)

        self.new_button = QPushButton("+TAB")
        self.new_button.clicked.connect(lambda: self.new_tab(clean=False))

        self.reload_button = QPushButton("Reload")
        self.reload_button.clicked.connect(self.reload_file)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_preview)

        self.save_button = QToolButton()
        self.save_button.setObjectName("saveMenuButton")
        self.save_button.setText("Save")
        self.save_button.setMinimumWidth(86)
        self.save_button.setPopupMode(QToolButton.MenuButtonPopup)
        self.save_button.clicked.connect(lambda: self.save_action("save_now"))
        save_menu = QMenu(self.save_button)
        for key, label in [
            ("save_now", "SAVE NOW"),
            ("save_as", "SAVE AS"),
            ("save_script", "SAVE SCRIPT (*.script)"),
            ("save_marked", "SAVE MARKED (*.md)"),
            ("save_text", "SAVE TEXT (*.txt)"),
            ("save_arcs", "SAVE STORY (*.arcs)"),
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
        self.tools_menu = QMenu(self.tools_button)
        tools_menu = self.tools_menu
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
        tools_menu.addSeparator()
        self.linked_scroll_action = QAction("Linked Scrolling", self)
        self.linked_scroll_action.setCheckable(True)
        self.linked_scroll_action.setChecked(self.linked_scroll_enabled)
        self.linked_scroll_action.triggered.connect(self.toggle_linked_scrolling)
        tools_menu.addAction(self.linked_scroll_action)
        self.teleprompter_action = QAction("Teleprompter", self)
        self.teleprompter_action.setCheckable(True)
        self.teleprompter_action.setChecked(self.teleprompter_enabled)
        self.teleprompter_action.triggered.connect(self.toggle_teleprompter)
        tools_menu.addAction(self.teleprompter_action)
        self.clean_start_action = QAction("Clean Start", self)
        self.clean_start_action.setCheckable(True)
        self.clean_start_action.setChecked(self.clean_start_enabled)
        self.clean_start_action.triggered.connect(self.toggle_clean_start)
        tools_menu.addAction(self.clean_start_action)
        tools_menu.addSeparator()
        self.help_action = QAction("Help", self)
        self.help_action.triggered.connect(self.show_help_dialog)
        tools_menu.addAction(self.help_action)
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
        self.mode_box.addItems(["Reader", "Editor", "Split", "Story"])
        self.mode_box.currentTextChanged.connect(self.change_mode)

        self.network_box = QComboBox()
        self.network_box.setMaximumWidth(82)
        self.network_box.addItems(["LOCAL", "HTTPS"])
        self.network_box.currentTextChanged.connect(self.change_network)

        self.sep_theme_mode = QLabel("|")
        self.sep_mode_network = QLabel("|")
        self.sep_theme_network = QLabel("|")

        self._build_editor_tools()
        self._build_teleprompter_bar()
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

    def _build_teleprompter_bar(self) -> None:
        self.teleprompter_bar = QWidget()
        self.teleprompter_bar.setObjectName("teleprompterBar")
        outer = QVBoxLayout(self.teleprompter_bar)
        outer.setContentsMargins(4, 2, 4, 2)
        outer.setSpacing(2)
        self.teleprompter_control_row = QWidget()
        self.teleprompter_control_layout = QHBoxLayout(self.teleprompter_control_row)
        self.teleprompter_control_layout.setContentsMargins(0, 0, 0, 0)
        self.teleprompter_control_layout.setSpacing(4)
        self.teleprompter_slider_row = QWidget()
        self.teleprompter_slider_layout = QHBoxLayout(self.teleprompter_slider_row)
        self.teleprompter_slider_layout.setContentsMargins(0, 0, 0, 0)
        self.teleprompter_slider_layout.setSpacing(4)
        outer.addWidget(self.teleprompter_control_row)
        outer.addWidget(self.teleprompter_slider_row)

        self.teleprompter_pause_left = QCheckBox("Pause")
        self.teleprompter_pause_right = QCheckBox("Pause")
        self.teleprompter_pause_left.stateChanged.connect(
            lambda state: self.set_teleprompter_paused(bool(state))
        )
        self.teleprompter_pause_right.stateChanged.connect(
            lambda state: self.set_teleprompter_paused(bool(state))
        )
        self.teleprompter_slider = QSlider(Qt.Orientation.Horizontal)
        self.teleprompter_slider.setRange(-200, 200)
        self.teleprompter_slider.setSingleStep(1)
        self.teleprompter_slider.setPageStep(10)
        self.teleprompter_slider.setValue(self.teleprompter_speed)
        self.teleprompter_slider.setToolTip("Negative scrolls backward; 0 stops; positive scrolls forward.")
        self.teleprompter_slider.valueChanged.connect(self.set_teleprompter_speed)
        self.teleprompter_quick_buttons: list[QPushButton] = []
        for value, label in ((50, "0.5x"), (100, "1x"), (150, "1.5x"), (200, "2x")):
            button = QPushButton(label)
            button.clicked.connect(lambda checked=False, speed=value: self.teleprompter_slider.setValue(speed))
            self.teleprompter_quick_buttons.append(button)
        self.set_teleprompter_paused(self.teleprompter_paused, persist=False)
        self.toolbar_vbox.addWidget(self.teleprompter_bar)
        self.teleprompter_bar.setVisible(self.teleprompter_enabled)
        self._reflow_teleprompter_bar()

    def _reflow_teleprompter_bar(self) -> None:
        if not hasattr(self, "teleprompter_control_layout"):
            return
        _clear_layout(self.teleprompter_control_layout)
        _clear_layout(self.teleprompter_slider_layout)
        width = max(240, self.width())
        controls_width = 290
        slider_would_be = max(0, width - controls_width)
        slider_needs_own_row = slider_would_be < width * 0.35
        quick = list(self.teleprompter_quick_buttons)
        if slider_needs_own_row:
            self.teleprompter_control_layout.addWidget(self.teleprompter_pause_left)
            self.teleprompter_control_layout.addStretch(1)
            for button in quick:
                self.teleprompter_control_layout.addWidget(button)
            self.teleprompter_control_layout.addStretch(1)
            self.teleprompter_control_layout.addWidget(self.teleprompter_pause_right)
            self.teleprompter_slider.setMinimumWidth(max(120, int(width * 0.50)))
            self.teleprompter_slider.setMaximumWidth(max(120, int(width * 0.50)))
            self.teleprompter_slider_layout.addStretch(1)
            self.teleprompter_slider_layout.addWidget(self.teleprompter_slider)
            self.teleprompter_slider_layout.addStretch(1)
            self.teleprompter_slider_row.show()
        else:
            self.teleprompter_slider.setMinimumWidth(120)
            self.teleprompter_slider.setMaximumWidth(16777215)
            self.teleprompter_control_layout.addWidget(self.teleprompter_pause_left)
            self.teleprompter_control_layout.addWidget(self.teleprompter_slider, 1)
            for button in quick:
                self.teleprompter_control_layout.addWidget(button)
            self.teleprompter_control_layout.addWidget(self.teleprompter_pause_right)
            self.teleprompter_slider_row.hide()

    def toggle_linked_scrolling(self, checked: bool | None = None) -> None:
        self.linked_scroll_enabled = bool(
            self.linked_scroll_action.isChecked() if checked is None else checked
        )
        self.linked_scroll_action.setChecked(self.linked_scroll_enabled)
        self.udata.set("linked_scrolling_enabled", "1" if self.linked_scroll_enabled else "0", section="HEADER")
        self.udata.save()
        tab = self.active_tab()
        if tab and self.linked_scroll_enabled and tab.state.mode in {"split", "story"}:
            tab._syncing_scroll = True
            tab.sync_reader_to_editor_cursor()
            tab._syncing_scroll = False
        self.statusBar().showMessage(
            f"Linked Scrolling {'enabled' if self.linked_scroll_enabled else 'disabled'}.", 1800
        )

    def toggle_clean_start(self, checked: bool | None = None) -> None:
        self.clean_start_enabled = bool(
            self.clean_start_action.isChecked() if checked is None else checked
        )
        self.clean_start_action.setChecked(self.clean_start_enabled)
        self.udata.set("clean_start_enabled", "1" if self.clean_start_enabled else "0", section="HEADER")
        self.udata.save()
        self.statusBar().showMessage(
            "Clean Start will open one empty tab next launch." if self.clean_start_enabled
            else "Normal starter-tab launch restored.",
            2200,
        )

    def toggle_teleprompter(self, checked: bool | None = None) -> None:
        self.teleprompter_enabled = bool(
            self.teleprompter_action.isChecked() if checked is None else checked
        )
        self.teleprompter_action.setChecked(self.teleprompter_enabled)
        self.teleprompter_bar.setVisible(self.teleprompter_enabled)
        self.udata.set("teleprompter_enabled", "1" if self.teleprompter_enabled else "0", section="HEADER")
        self.udata.save()
        self._reflow_toolbar()
        self.statusBar().showMessage(
            f"Teleprompter {'enabled' if self.teleprompter_enabled else 'disabled'}.", 1800
        )

    def set_teleprompter_speed(self, value: int) -> None:
        self.teleprompter_speed = max(-200, min(200, int(value)))
        if hasattr(self, "teleprompter_slider") and self.teleprompter_slider.value() != self.teleprompter_speed:
            self.teleprompter_slider.blockSignals(True)
            self.teleprompter_slider.setValue(self.teleprompter_speed)
            self.teleprompter_slider.blockSignals(False)
        self.udata.set("teleprompter_speed", str(self.teleprompter_speed), section="HEADER")
        self.udata.save()

    def set_teleprompter_paused(self, paused: bool, *, persist: bool = True) -> None:
        self.teleprompter_paused = bool(paused)
        for box in (
            getattr(self, "teleprompter_pause_left", None),
            getattr(self, "teleprompter_pause_right", None),
        ):
            if box is not None:
                box.blockSignals(True)
                box.setChecked(self.teleprompter_paused)
                box.blockSignals(False)
        if persist:
            self.udata.set("teleprompter_paused", "1" if self.teleprompter_paused else "0", section="HEADER")
            self.udata.save()

    def pause_teleprompter_for(self, seconds: int) -> None:
        self._teleprompter_pause_until = max(self._teleprompter_pause_until, time.monotonic() + seconds)
        self.statusBar().showMessage(f"Teleprompter paused for {seconds} seconds.", 1800)

    def _teleprompter_tick(self) -> None:
        if not self.teleprompter_enabled or self.teleprompter_paused:
            return
        if time.monotonic() < self._teleprompter_pause_until:
            return
        tab = self.active_tab()
        if tab is None or self.teleprompter_speed == 0:
            return
        # Roughly 22 px/second at 1x with a 30 ms timer; low enough for spoken
        # delivery while retaining slider fine tuning and reverse movement.
        tab.teleprompter_step((self.teleprompter_speed / 100.0) * 0.66)

    def _cycle_teleprompter_speed(self, direction: int) -> None:
        stops = [-200, -150, -100, -50, 0, 50, 100, 150, 200]
        current = min(range(len(stops)), key=lambda index: abs(stops[index] - self.teleprompter_speed))
        target = stops[max(0, min(len(stops) - 1, current + direction))]
        self.teleprompter_slider.setValue(target)

    def keyPressEvent(self, event) -> None:  # noqa: N802 - Qt method name
        focus = QApplication.focusWidget()
        # Never steal ordinary typing from the editor, find box, or emoji filter.
        if isinstance(focus, (QPlainTextEdit, QLineEdit)):
            return super().keyPressEvent(event)
        if self.teleprompter_enabled and not event.modifiers():
            key = (event.text() or "").lower()
            if key == "p":
                self.set_teleprompter_paused(not self.teleprompter_paused)
                return
            if key == "o":
                self.teleprompter_slider.setValue(100)
                return
            if key == "l":
                self._cycle_teleprompter_speed(1)
                return
            if key == "k":
                self._cycle_teleprompter_speed(-1)
                return
            delays = {"i": 3, "u": 5, "j": 10, "n": 30}
            if key in delays:
                self.pause_teleprompter_for(delays[key])
                return
        super().keyPressEvent(event)

    def _help_file_candidates(self) -> list[Path]:
        root = Path(__file__).resolve().parents[1]
        help_dir = root / "docs" / "help"
        names = [
            "SWAR_HELP.script", "SCRIPT_HELP.script", "MARKDOWN_HELP.md",
            "TEXT_HELP.txt", "ARCS_HELP.script", "ARCS_EXAMPLE.arcs",
        ]
        return [help_dir / name for name in names if (help_dir / name).is_file()]

    def show_help_dialog(self) -> None:
        paths = self._help_file_candidates()
        if not paths:
            QMessageBox.information(self, "SWAR Help", "No installed help files were found in docs/help.")
            return
        dialog = QDialog(self)
        dialog.setWindowTitle("Load SWAR Help")
        dialog.resize(560, 380)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Choose help files to open as new SWAR tabs:"))
        listing = QListWidget()
        listing.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        for path in paths:
            item = QListWidgetItem(path.name)
            item.setData(Qt.ItemDataRole.UserRole, str(path))
            listing.addItem(item)
        if listing.count():
            listing.item(0).setSelected(True)
        layout.addWidget(listing, 1)
        buttons = QDialogButtonBox()
        selected_button = buttons.addButton("Load Selected", QDialogButtonBox.ButtonRole.AcceptRole)
        all_button = buttons.addButton("Load All", QDialogButtonBox.ButtonRole.ActionRole)
        cancel_button = buttons.addButton(QDialogButtonBox.StandardButton.Cancel)
        layout.addWidget(buttons)

        def load_selected() -> None:
            chosen = listing.selectedItems()
            for item in chosen:
                self.open_path(str(item.data(Qt.ItemDataRole.UserRole)))
            dialog.accept()

        def load_all() -> None:
            for path in paths:
                self.open_path(str(path))
            dialog.accept()

        selected_button.clicked.connect(load_selected)
        all_button.clicked.connect(load_all)
        cancel_button.clicked.connect(dialog.reject)
        dialog.exec()

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

    def _clear_dynamic_toolbar_separators(self) -> None:
        for label in getattr(self, "_dynamic_toolbar_separators", []):
            label.setParent(None)
            label.deleteLater()
        self._dynamic_toolbar_separators = []

    def _toolbar_separator(self, text: str = "|") -> QLabel:
        label = QLabel(text)
        label.setObjectName("toolbarSeparator")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setMinimumWidth(12 if text == "|" else 24)
        self._dynamic_toolbar_separators.append(label)
        return label

    def _interleave_toolbar(self, widgets: list[QWidget], separator: str = "|") -> list[QWidget]:
        out: list[QWidget] = []
        for index, widget in enumerate(widgets):
            if index:
                out.append(self._toolbar_separator(separator))
            out.append(widget)
        return out

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
        edge_padding: int = 0,
    ) -> None:
        """Add one responsive toolbar row with stable left / center / right zones."""
        left = left or []
        center = center or []
        right = right or []
        layout.setContentsMargins(edge_padding, 0, edge_padding, 0)
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
        for name, snippets in ARC_SNIPPET_GROUPS.items():
            groups[name] = list(snippets)
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
        self.general_editor_tool_buttons = [
            self.sections_button, self.subsections_button, self.endsect_button,
            self.source_button, self.emoji_button, self.markdown_button, self.template_button,
        ]
        self.editor_tool_buttons = list(self.general_editor_tool_buttons)
        self.arc_button = self._make_snippet_button("Arc", "Arcs")
        self.arc_story_button = self._make_snippet_button("Story", "Story")
        self.arc_data_button = self._make_snippet_button("Arc Data", "Arc Data")
        self.arc_phrases_button = self._make_snippet_button("Phrases", "Phrases")
        self.arc_tool_buttons = [
            self.arc_button, self.arc_story_button, self.arc_data_button, self.arc_phrases_button,
        ]

    def _reflow_toolbar(self) -> None:
        if not hasattr(self, "toolbar_row_layouts"):
            return
        width = max(0, self.width())
        self._clear_dynamic_toolbar_separators()
        for layout in self.toolbar_row_layouts:
            _clear_layout(layout)
            layout.setSpacing(3)
            layout.setContentsMargins(0, 0, 0, 0)
        for row in self.toolbar_rows:
            row.hide()

        tab = self.active_tab() if hasattr(self, "tabs") else None
        mode = tab.state.mode if tab is not None else ("reader" if self.reader_only else "split")
        editor_visible = mode in {"editor", "split", "story"}
        story_visible = mode == "story"
        for button in getattr(self, "general_editor_tool_buttons", []):
            button.setVisible(editor_visible)
        for button in getattr(self, "arc_tool_buttons", []):
            button.setVisible(story_visible)

        program_full = [
            self.open_button, self.new_button, self.reload_button, self.refresh_button,
            self.tools_button, self.save_button, self.outline_button,
        ]
        program_core = [self.open_button, self.save_button, self.tools_button]
        program_extra = [self.new_button, self.reload_button, self.refresh_button, self.outline_button]
        settings = [self.theme_box, self.mode_box, self.network_box]

        if width >= 980:
            left = self._interleave_toolbar(program_full)
            right = self._interleave_toolbar(settings)
            self._add_aligned_toolbar_row(
                self.toolbar_row_layouts[0], left=left, center=[], right=right,
                edge_padding=TOOLBAR_EDGE_PADDING,
            )
            self.toolbar_rows[0].show()
        elif width >= 650:
            left = self._interleave_toolbar(program_core)
            right = self._interleave_toolbar(settings)
            self._add_aligned_toolbar_row(
                self.toolbar_row_layouts[0], left=left, center=[], right=right,
                edge_padding=TOOLBAR_EDGE_PADDING,
            )
            self._add_aligned_toolbar_row(
                self.toolbar_row_layouts[2], left=[], center=self._interleave_toolbar(program_extra), right=[],
                edge_padding=TOOLBAR_EDGE_PADDING,
            )
            self.toolbar_rows[0].show()
            self.toolbar_rows[2].show()
        else:
            left = self._interleave_toolbar([self.open_button, self.save_button])
            right = self._interleave_toolbar([self.mode_box, self.network_box])
            self._add_aligned_toolbar_row(
                self.toolbar_row_layouts[0], left=left, center=[], right=right,
                edge_padding=12,
            )
            compact_extra = [self.new_button, self.reload_button, self.refresh_button, self.tools_button, self.outline_button, self.theme_box]
            self._add_aligned_toolbar_row(
                self.toolbar_row_layouts[2], left=[], center=self._interleave_toolbar(compact_extra), right=[],
                edge_padding=12,
            )
            self.toolbar_rows[0].show()
            self.toolbar_rows[2].show()

        # The second toolbar row is reserved exclusively for authoring tools.
        # Reader mode leaves it completely hidden.  Story mode separates normal
        # SWAR inserts from Arc inserts with the requested |:| marker.
        if editor_visible:
            editor_row = self._interleave_toolbar(list(self.general_editor_tool_buttons))
            if story_visible:
                editor_row.append(self._toolbar_separator("|:|"))
                editor_row.extend(self._interleave_toolbar(list(self.arc_tool_buttons)))
            self._add_aligned_toolbar_row(
                self.toolbar_row_layouts[1], left=[], center=editor_row, right=[],
                edge_padding=TOOLBAR_EDGE_PADDING,
            )
            self.toolbar_rows[1].show()

        if hasattr(self, "teleprompter_bar"):
            self.teleprompter_bar.setVisible(self.teleprompter_enabled)
            self._reflow_teleprompter_bar()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reflow_toolbar()

    def new_tab(self, clean: bool = False, story: bool = False) -> None:
        if story:
            text = "" if clean else new_arc_template() + "\n"
            mode = "story"
            title = "Untitled.arcs"
        else:
            text = "" if clean else '3D Changes Perspectives:: New SWAR Script: Draft\n\n"Start writing here."\n'
            mode = "reader" if self.reader_only else "split"
            title = "Untitled.script"
        tab = SwarTab(self, TabState(path=None, text=text, mode=mode))
        tab.set_theme()
        idx = self.tabs.addTab(tab, title)
        self.tabs.setCurrentIndex(idx)
        self.refresh_tab_title(tab)
        self.update_toolbar_state()

    def open_file_dialog(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Open SWAR files",
            "",
            "SWAR Files (*.script *.md *.txt *.arcs);;Story Arcs (*.arcs);;All Files (*)",
        )
        for path in paths:
            self.open_path(path)

    def open_path(self, path: str) -> None:
        p = Path(path)
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            QMessageBox.warning(self, "SWAR Open", f"Could not open {p}:\n{exc}")
            return
        mode = "reader" if self.reader_only else ("story" if p.suffix.lower() == ".arcs" else "reader")
        tab = SwarTab(self, TabState(path=str(p), text=text, mode=mode))
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
            self.new_tab(clean=self.clean_start_enabled)

    def refresh_tab_title(self, tab: SwarTab) -> None:
        idx = self.tabs.indexOf(tab)
        if idx < 0:
            return
        name = Path(tab.state.path).name if tab.state.path else ("Untitled.arcs" if tab.state.mode == "story" else "Untitled.script")
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
        tab.parse_and_render(force=True)
        self.statusBar().showMessage("Reader preview refreshed and position restored.", 1800)

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
        extension = "arcs" if (action_key == "save_now" and not current and tab.state.mode == "story") else None
        dialog = False
        if action_key == "save_as":
            dialog = True
            if tab.state.mode == "story":
                extension = "arcs"
        elif action_key == "save_script":
            extension = "script"
        elif action_key == "save_marked":
            extension = "md"
        elif action_key == "save_text":
            extension = "txt"
        elif action_key == "save_arcs":
            extension = "arcs"

        path: Path
        if dialog:
            default_ext = extension or ("arcs" if tab.state.mode == "story" else "script")
            suggested = str(resolve_save_path(current, default_ext)) if current else str(auto_save_path(default_ext))
            selected, _ = QFileDialog.getSaveFileName(
                self,
                "Save SWAR file",
                suggested,
                "SWAR Script (*.script);;Markdown (*.md);;Text (*.txt);;Story Arcs (*.arcs);;All Files (*)",
            )
            path = Path(selected) if selected else auto_save_path(default_ext)
        else:
            path = resolve_save_path(current, extension)

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        tab.state.path = str(path)
        tab.state.dirty = False
        tab.parse_and_render(force=True)
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
            self.statusBar().showMessage("Switch to Editor, Split, or Story mode to use editor tools.", 2200)
            return
        tab.insert_snippet(snippet)
        if tab.state.mode in {"split", "story"}:
            tab.parse_and_render(force=True)
        self.update_toolbar_state()
        self.statusBar().showMessage(f"Inserted: {snippet.label}", 1600)

    def insert_emoji(self, entry: EmojiEntry) -> None:
        tab = self.active_tab()
        if not tab:
            return
        if tab.state.mode == "reader":
            self.statusBar().showMessage("Switch to Editor, Split, or Story mode to use emoji tools.", 2200)
            return
        tab.insert_inline_text(entry.symbol)
        if tab.state.mode in {"split", "story"}:
            tab.parse_and_render(force=True)
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
            f"QToolButton#saveMenuButton {{ padding: 3px 22px 3px 7px; min-width: 52px; }}"
            f"QToolButton#saveMenuButton::menu-button {{ width: 18px; border-left: 1px solid {theme.border}; }}"
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
        elif requested in {"editor", "split", "story"}:
            if self.reader_only:
                decision = self._reader_edit_prompt()
                if decision == "cancel":
                    self.mode_box.blockSignals(True)
                    self.mode_box.setCurrentText("Reader")
                    self.mode_box.blockSignals(False)
                    return
                tab.state.network_mode = "online" if decision == "online" else "local"
                self.reader_only = False
            tab.set_mode(requested)
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
        tab.parse_and_render(force=True)
        self.update_toolbar_state()

    def update_toolbar_state(self) -> None:
        tab = self.active_tab()
        if not tab:
            return
        self.mode_box.blockSignals(True)
        self.mode_box.setCurrentText({
            "reader": "Reader", "editor": "Editor", "split": "Split", "story": "Story",
        }.get(tab.state.mode, "Reader"))
        self.mode_box.blockSignals(False)
        self.network_box.blockSignals(True)
        self.network_box.setCurrentText(NETWORK_DISPLAY.get(tab.state.network_mode, "LOCAL"))
        self.network_box.blockSignals(False)
        if hasattr(self, "theme_box"):
            self.theme_box.blockSignals(True)
            self.theme_box.setCurrentText(THEME_DISPLAY.get(self.theme_name, "NIGHT"))
            self.theme_box.blockSignals(False)
        tools_enabled = tab.state.mode in {"editor", "split", "story"}
        for button in getattr(self, "general_editor_tool_buttons", []):
            button.setEnabled(tools_enabled)
        for button in getattr(self, "arc_tool_buttons", []):
            button.setEnabled(tab.state.mode == "story")
        self._reflow_toolbar()

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
            return

        tab = self.active_tab()
        if not tab:
            return
        if value.startswith("storytoggle:"):
            payload = value[len("storytoggle:"):]
            try:
                line_text, section = payload.split(":", 1)
                tab.toggle_story_section(int(line_text), unquote(section))
            except (TypeError, ValueError):
                self.statusBar().showMessage("Could not identify that Story section.", 1600)
            return
        if value.startswith("storyexpand:"):
            try:
                tab.expand_story_arc(int(value[len("storyexpand:"):]))
            except (TypeError, ValueError):
                self.statusBar().showMessage("Could not identify that Story Arc.", 1600)
            return
        if value.startswith("storycollapse:"):
            try:
                tab.collapse_story_arc(int(value[len("storycollapse:"):]))
            except (TypeError, ValueError):
                self.statusBar().showMessage("Could not identify that Story Arc.", 1600)
            return

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
            ext = "arcs" if tab.state.mode == "story" else "script"
        doc = tab.state.doc
        section = section_for_scroll(doc, pct)
        sections = doc.section_count if doc else 0
        dirty = "unsaved" if tab.state.dirty else "saved"
        cursor_segment = ""
        block_segment = ""
        if tab.state.mode in {"editor", "split", "story"}:
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
