"""Transcript pane: renders the chat, streams answers in, shows image thumbs."""
import os
import traceback

from PyQt5 import QtCore, QtGui, QtWidgets

from .. import markdown
from . import backdrop, theme


class TranscriptView(QtWidgets.QTextBrowser):
    """QTextBrowser that can paint a wallpaper behind the text."""

    def __init__(self, parent=None):
        super(TranscriptView, self).__init__(parent)
        self.setFrameStyle(0)
        self._wallpaper = None
        self._base = QtGui.QColor(theme.BG)
        self._apply_palette()

    def _apply_palette(self):
        colours = self.palette()
        colours.setColor(QtGui.QPalette.Base, QtGui.QColor(QtCore.Qt.transparent))
        colours.setColor(QtGui.QPalette.Text, QtGui.QColor(theme.FG))
        colours.setColor(QtGui.QPalette.Window, QtGui.QColor(QtCore.Qt.transparent))
        self.setPalette(colours)
        self.viewport().setAutoFillBackground(False)

    def set_backdrop(self, pixmap, base):
        self._wallpaper = pixmap
        self._base = QtGui.QColor(base)
        self._apply_palette()
        self.viewport().update()

    def paintEvent(self, event):
        # never let anything escape into Qt: an exception here aborts the app
        try:
            self._paint_backdrop()
        except Exception:  # noqa: BLE001
            traceback.print_exc()
        super(TranscriptView, self).paintEvent(event)

    def _paint_backdrop(self):
        if self._wallpaper is None or self._wallpaper.isNull():
            return
        painter = QtGui.QPainter(self.viewport())
        try:
            painter.fillRect(self.viewport().rect(), self._base)
            backdrop.paint(painter, self.viewport().rect(), self._wallpaper)
        finally:
            painter.end()


class ChatView(QtWidgets.QWidget):
    sendRequested = QtCore.pyqtSignal()
    stopRequested = QtCore.pyqtSignal()
    modeChanged = QtCore.pyqtSignal(str)
    chatApiChanged = QtCore.pyqtSignal(str)
    strategyChanged = QtCore.pyqtSignal(str)

    MODES = [("chat", "Chat"), ("team", "Team"), ("image", "Image")]

    def __init__(self, store, parent=None):
        super(ChatView, self).__init__(parent)
        self.store = store
        self._stream_buffer = []
        self._build()

    # ---------- layout ----------
    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar = QtWidgets.QFrame()
        bar.setObjectName("Topbar")
        bar_layout = QtWidgets.QHBoxLayout(bar)
        bar_layout.setContentsMargins(12, 8, 12, 8)
        bar_layout.setSpacing(8)

        self.mode_buttons = {}
        for key, label in self.MODES:
            button = QtWidgets.QPushButton(label)
            button.setObjectName("Ghost")
            button.setCheckable(True)
            button.setCursor(QtCore.Qt.PointingHandCursor)
            button.clicked.connect(
                lambda _checked, k=key: self._pick_mode(k))
            bar_layout.addWidget(button)
            self.mode_buttons[key] = button

        self.strategy = QtWidgets.QComboBox()
        self.strategy.addItems(["Sequential", "Review Loop", "Debate", "Panel"])
        self.strategy.setToolTip("How the team works together")
        self.strategy.currentTextChanged.connect(self.strategyChanged)
        bar_layout.addWidget(QtWidgets.QLabel("Strategy"))
        bar_layout.addWidget(self.strategy)

        self.rounds = QtWidgets.QSpinBox()
        self.rounds.setRange(1, 6)
        self.rounds.setValue(int(self.store.settings.get("max_rounds", 2)))
        self.rounds.setPrefix("rounds ")
        self.rounds.setToolTip("Debate rounds")
        bar_layout.addWidget(self.rounds)

        bar_layout.addStretch(1)

        bar_layout.addWidget(QtWidgets.QLabel("API"))
        self.api = QtWidgets.QComboBox()
        self.api.setMinimumWidth(230)
        self.api.currentIndexChanged.connect(
            lambda _i: self.chatApiChanged.emit(self.api.currentData() or ""))
        bar_layout.addWidget(self.api)

        self.team_note = QtWidgets.QLabel()
        self.team_note.setStyleSheet("color:#89b4fa; font-size:11px;")
        bar_layout.addWidget(self.team_note)

        root.addWidget(bar)

        self.transcript = TranscriptView()
        self.transcript.setOpenExternalLinks(True)
        self.transcript.setMinimumHeight(120)
        root.addWidget(self.transcript, 1)

        self.hint = QtWidgets.QLabel(
            "Enter sends  -  Shift+Enter makes a new line")
        self.hint.setStyleSheet("color:#6c7086; font-size:10px; padding:0 12px;")
        root.addWidget(self.hint)

        composer = QtWidgets.QFrame()
        composer.setStyleSheet("border-top:1px solid #45475a;")
        composer_layout = QtWidgets.QVBoxLayout(composer)
        composer_layout.setContentsMargins(12, 10, 12, 12)
        composer_layout.setSpacing(8)

        self.input = QtWidgets.QPlainTextEdit()
        self.input.setPlaceholderText(
            "Ask anything, give the team a task, or describe a picture...")
        self.input.setMinimumHeight(74)
        self.input.setMaximumHeight(170)
        self.input.installEventFilter(self)
        composer_layout.addWidget(self.input)

        row = QtWidgets.QHBoxLayout()
        row.setSpacing(8)
        self.attachment_note = QtWidgets.QLabel()
        self.attachment_note.setStyleSheet("color:#a6e3a1; font-size:11px;")
        row.addWidget(self.attachment_note)
        row.addStretch(1)

        self.stop_button = QtWidgets.QPushButton("Stop")
        self.stop_button.setObjectName("Ghost")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stopRequested.emit)
        row.addWidget(self.stop_button)

        self.clear_button = QtWidgets.QPushButton("Clear")
        self.clear_button.setObjectName("Ghost")
        self.clear_button.clicked.connect(self._confirm_clear)
        row.addWidget(self.clear_button)

        self.send_button = QtWidgets.QPushButton("Send")
        self.send_button.setObjectName("Primary")
        self.send_button.setMinimumWidth(104)
        self.send_button.setDefault(True)
        self.send_button.clicked.connect(self.sendRequested.emit)
        row.addWidget(self.send_button)
        composer_layout.addLayout(row)

        root.addWidget(composer)

    # ---------- mode ----------
    def _pick_mode(self, key):
        for mode_key, _label in self.MODES:
            self.mode_buttons[mode_key].setChecked(mode_key == key)
        self.modeChanged.emit(key)

    def current_mode(self):
        for mode_key, _label in self.MODES:
            if self.mode_buttons[mode_key].isChecked():
                return mode_key
        return "chat"

    def set_mode(self, key):
        self._pick_mode(key)

    # ---------- combo refresh ----------
    def refresh_apis(self):
        current = self.api.currentData()
        self.api.blockSignals(True)
        self.api.clear()
        profiles = self.store.chat_apis()
        if not profiles:
            self.api.addItem("(no chat API yet - add one in the APIs tab)", "")
        for profile in profiles:
            self.api.addItem(profile.label(), profile.id)
        index = self.api.findData(current)
        if index < 0 and profiles:
            index = 0
        if index >= 0:
            self.api.setCurrentIndex(index)
        self.api.blockSignals(False)

    def set_backdrop(self, pixmap):
        self.transcript.set_backdrop(pixmap, theme.BG)
        self.transcript.viewport().update()

    def set_busy(self, busy):
        self.send_button.setEnabled(not busy)
        self.send_button.setText("Working..." if busy else "Send")
        self.stop_button.setEnabled(busy)
        self.input.setReadOnly(busy)

    def set_note(self, text):
        self.team_note.setText(text)

    def set_placeholder(self, text):
        self.input.setPlaceholderText(text)

    # ---------- rendering ----------
    def _doc(self):
        return self.transcript.document()

    def _cursor(self):
        """A cursor parked at the very end of the transcript."""
        cursor = self.transcript.textCursor()
        cursor.movePosition(QtGui.QTextCursor.End)
        return cursor

    def _html(self):
        return ('<html><head><style>{0}</style></head><body></body></html>'
                .format(theme.body_css()))

    def render(self, chat):
        self.transcript.clear()
        self.transcript.setHtml(self._html())
        if not chat.messages:
            self._append_notice(
                "New chat. Pick a mode above and type below.", "info")
            return
        for message in chat.messages:
            self._append_message(message, scroll=False)
        self._scroll()

    def _meta_text(self, message):
        meta = message.get("meta") or {}
        usage = message.get("usage") or {}
        bits = []
        if meta.get("step"):
            bits.append(str(meta["step"]))
        if meta.get("round"):
            bits.append("round {0}".format(meta["round"]))
        if meta.get("parallel"):
            bits.append("parallel")
        if meta.get("model"):
            bits.append(str(meta["model"]))
        if meta.get("elapsed"):
            bits.append("{0}s".format(meta["elapsed"]))
        total = _usage_total(usage)
        if total:
            bits.append("{0} tokens".format(total))
        return " &nbsp; ".join(bits)

    def _images_html(self, paths):
        clean = [p for p in (paths or []) if p and os.path.exists(p)]
        if not clean:
            return ""
        cells = []
        for path in clean:
            url = QtCore.QUrl.fromLocalFile(path).toString()
            cells.append(
                '<td style="border:1px solid {edge}; padding:4px;">'
                '<a href="{url}"><img src="{url}" width="200"></a></td>'
                .format(url=url, edge=theme.BUBBLE_EDGE))
        return ('<table cellspacing="4" cellpadding="0" '
                'style="margin-top:4px;"><tr>{0}</tr></table>'
                .format("".join(cells)))

    def _append_message(self, message, scroll=True):
        body = markdown.to_html(message.get("content", ""))
        html = theme.bubble_html(
            message.get("role", "assistant"),
            message.get("agent", ""),
            body,
            message.get("time", ""),
            self._meta_text(message),
            message.get("color"),
            self._images_html(message.get("images")),
        )
        cursor = self._cursor()
        if not cursor.atBlockStart():
            cursor.insertBlock()
        cursor.insertHtml(html)
        if scroll:
            self._scroll()

    def _append_notice(self, text, kind="info"):
        cursor = self._cursor()
        cursor.insertHtml(theme.notice_html(text, kind))
        self._scroll()

    def _scroll(self):
        bar = self.transcript.verticalScrollBar()
        bar.setValue(bar.maximum())

    # ---------- streaming ----------
    # While an answer streams in we draw plain paragraphs. When the turn ends
    # the whole chat is re-rendered as proper bubbles, so this stays simple.
    def begin_stream(self, agent, color):
        cursor = self._cursor()
        cursor.insertHtml(
            '<p style="margin:8px 0 2px 0;">'
            '<span style="font-size:9pt; font-weight:700; color:{0};">{1}'
            '</span> <span style="font-size:8pt; color:{2};">typing...</span>'
            '</p>'.format(color or theme.ACCENT, agent or "Assistant",
                          theme.MUTED))
        self._stream_buffer = []

    def append_delta(self, text):
        escaped = (text.replace("&", "&amp;").replace("<", "&lt;")
                   .replace(">", "&gt;"))
        cursor = self._cursor()
        cursor.insertHtml('<p style="margin:2px 0;">{0}</p>'
                          .format(escaped.replace("\n", "<br>")))
        self._stream_buffer.append(text)
        self._scroll()

    def end_stream(self):
        self._stream_buffer = []

    # ---------- misc ----------
    def _confirm_clear(self):
        chat = self.store.active_chat
        if not chat.messages:
            return
        answer = QtWidgets.QMessageBox.question(
            self, "Clear chat",
            "Delete all {0} messages in '{1}'?"
            .format(len(chat.messages), chat.title),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if answer == QtWidgets.QMessageBox.Yes:
            chat.messages = []
            self.store.save()
            self.render(chat)
            self.cleared.emit()

    cleared = QtCore.pyqtSignal()

    def eventFilter(self, obj, event):
        from PyQt5 import QtCore as _c
        if obj is self.input and event.type() == _c.QEvent.KeyPress:
            enter = event.key() in (_c.Qt.Key_Return, _c.Qt.Key_Enter)
            if enter and not event.modifiers() & _c.Qt.ShiftModifier:
                self.sendRequested.emit()
                return True
        return super(ChatView, self).eventFilter(obj, event)


def _usage_total(usage):
    if not isinstance(usage, dict):
        return 0
    if usage.get("total_tokens"):
        return int(usage["total_tokens"])
    return int(usage.get("prompt_tokens") or 0) + int(
        usage.get("completion_tokens") or 0)