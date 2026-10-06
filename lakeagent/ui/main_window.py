"""Main window: wires the sidebar, chat view, image studio and the workers."""
import os
import traceback

from PyQt5 import QtCore, QtWidgets

from ..agents import image_job
from ..agents import team
from ..models import TEAM_STRATEGIES
from . import backdrop, theme
from .chat_view import ChatView
from .image_view import ImageView
from .settings_dialog import SettingsDialog
from .sidebar import Sidebar
from .theme_dialogs import ThemeEditorDialog
from .themes import ThemeManager
from .worker import Job


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, store):
        super(MainWindow, self).__init__()
        self.store = store
        self.job = None
        self._streaming = False
        self._elapsed = 0.0
        self.themes = ThemeManager(store)
        self.setWindowTitle("LakeAgent  -  multi-agent desk")
        self.setMinimumSize(1040, 660)
        self.resize(1280, 800)

        self._build()
        self._restore()

    # ---------------- layout ----------------
    def _build(self):
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.sidebar = Sidebar(self.store)
        self.sidebar.chatSelected.connect(self._open_chat)
        self.sidebar.chatChanged.connect(self._reload_all)
        self.sidebar.apiFocusRequested.connect(self._on_api_focus)
        self.sidebar.settings_button.clicked.connect(self._open_settings)
        self.sidebar.theme_button.clicked.connect(self._open_settings)
        self.sidebar.about_button.clicked.connect(self._open_about)
        root.addWidget(self.sidebar)

        right = QtWidgets.QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)

        self.stack = QtWidgets.QStackedWidget()
        right.addWidget(self.stack, 1)
        root.addLayout(right, 1)

        self.chat_view = ChatView(self.store)
        self.chat_view.sendRequested.connect(self._on_send)
        self.chat_view.stopRequested.connect(self._on_stop)
        self.chat_view.modeChanged.connect(self._on_mode_changed)
        self.chat_view.chatApiChanged.connect(self._on_chat_api_changed)
        self.chat_view.strategyChanged.connect(self._on_strategy_changed)
        self.chat_view.cleared.connect(self._reload_transcript)
        self.stack.addWidget(self.chat_view)

        self.image_view = ImageView(self.store)
        self.image_view.generateRequested.connect(self._on_generate_image)
        self.image_view.modeChanged.connect(self._on_image_mode_changed)
        self.image_view.apiChanged.connect(self._on_image_api_changed)
        self.image_view.backRequested.connect(self._leave_image_mode)
        self.stack.addWidget(self.image_view)

        self.status_left = QtWidgets.QLabel("Ready")
        self.status_right = QtWidgets.QLabel("")
        self.status_right.setAlignment(QtCore.Qt.AlignRight)
        bar = self.statusBar()
        bar.addWidget(self.status_left, 1)
        bar.addPermanentWidget(self.status_right)

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setFixedWidth(150)
        self.progress.setVisible(False)
        bar.addPermanentWidget(self.progress)

    def _restore(self):
        self.apply_theme()

        self.sidebar.refresh_chats()
        self.sidebar.refresh_apis()
        self.sidebar.refresh_agents()
        self.chat_view.refresh_apis()
        self.image_view.refresh_apis()
        self.image_view.refresh_gallery()

        strategy = self.store.settings.get("team_strategy", "Sequential")
        if strategy in TEAM_STRATEGIES:
            self.chat_view.strategy.setCurrentText(strategy)
        self._on_strategy_changed(strategy)

        chat = self.store.active_chat
        if chat.mode:
            self.chat_view.set_mode(chat.mode)
        self._apply_mode(chat.mode or "chat")
        self._on_chat_api_changed(chat.api_id)
        self.chat_view.render(chat)
        self.image_view.restore(chat.image_prompt, chat.image_mode)

        if not self.store.chat_apis():
            self._warn_no_apis()

    # ---------------- helpers ----------------
    @property
    def app(self):
        return QtWidgets.QApplication.instance()

    # ---------------- theme / font / wallpaper ----------------
    def apply_theme(self):
        """Push the live theme, font and wallpaper into every view."""
        theme.use(self.themes.current())
        backdrop.clear_cache()
        self.app.setStyleSheet(theme.stylesheet(
            self.themes.font_size(), self.themes.font_family()))

        live = self.themes.current()
        pixmap = backdrop.build(live.wallpaper, live.get("bg"))
        self.chat_view.set_backdrop(pixmap)
        self.image_view.set_backdrop(pixmap)
        self.image_view.refresh_styles()
        self.sidebar.refresh_agents()
        # bubble colours are baked into the transcript html, so redraw it
        self.chat_view.render(self.store.active_chat)

    def open_theme_editor(self, theme_obj=None):
        dialog = ThemeEditorDialog(self.themes, theme_obj, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            saved = self.themes.save_theme(dialog.result_theme)
            self.store.save()
            self.apply_theme()
            self._status("Theme saved: {0}".format(saved.name))
            return saved
        return None

    def _leave_image_mode(self):
        self._on_mode_changed("chat")
        self._status("Back to the chat")

    def _warn_no_apis(self):
        QtWidgets.QMessageBox.information(
            self, "Add an API first",
            "LakeAgent needs at least one API to work.\n\n"
            "Open the APIs tab and press '+ Add':\n"
            "  Name    - anything you like\n"
            "  Kind    - chat (for text) or image (for pictures)\n"
            "  Base URL- https://api.example.com  or  .../v1\n"
            "  Key     - your sk-... key\n"
            "  Model   - press Fetch to list the models")

    def _status(self, text, right=None):
        self.status_left.setText(text)
        if right is not None:
            self.status_right.setText(right)

    def _reload_all(self):
        self.chat_view.refresh_apis()
        self.image_view.refresh_apis()
        self.sidebar.refresh_agents()

    def _reload_transcript(self):
        chat = self.store.active_chat
        self.chat_view.render(chat)
        self.sidebar.refresh_chats()

    # ---------------- navigation ----------------
    def _open_chat(self, chat_id):
        if self.job is not None and self.job.isRunning():
            return
        self.store.set_active_chat(chat_id)
        chat = self.store.active_chat
        self._apply_mode(chat.mode or "chat")
        self._on_chat_api_changed(chat.api_id)
        self.chat_view.render(chat)
        self.image_view.restore(chat.image_prompt, chat.image_mode)
        self._status("Chat: {0}".format(chat.title))

    def _apply_mode(self, mode):
        if mode == "image":
            self.stack.setCurrentWidget(self.image_view)
        else:
            self.stack.setCurrentWidget(self.chat_view)
        self.sidebar.tabs.setCurrentIndex(0 if mode != "image" else 0)

    def _on_mode_changed(self, mode):
        chat = self.store.active_chat
        chat.mode = mode
        self.store.save()
        # keep the toolbar buttons honest even when the mode is set in code
        for key, button in self.chat_view.mode_buttons.items():
            if button.isChecked() != (key == mode):
                button.setChecked(key == mode)
        self._apply_mode(mode)
        self._refresh_mode_notes(mode)

    def _refresh_mode_notes(self, mode):
        if mode == "image":
            self.chat_view.set_note("")
            return
        enabled = self.store.enabled_agents()
        leader = self.store.leader()
        if mode == "team":
            if not enabled:
                self.chat_view.set_note("no agents enabled - Team tab")
            else:
                self.chat_view.set_note(
                    "{0} agents, leader {1}".format(
                        len(enabled), leader.name if leader else "-"))
        else:
            self.chat_view.set_note("")

    def _on_strategy_changed(self, strategy):
        self.store.settings["team_strategy"] = strategy
        self.store.save()
        self._refresh_mode_notes(self.chat_view.current_mode())

    def _on_chat_api_changed(self, api_id):
        chat = self.store.active_chat
        chat.api_id = api_id
        self.store.save()

    def _on_image_api_changed(self, api_id):
        chat = self.store.active_chat
        chat.image_api_id = api_id
        self.store.save()

    def _on_image_mode_changed(self, mode):
        chat = self.store.active_chat
        chat.image_mode = mode
        self.store.save()

    def _on_api_focus(self, _reason):
        self._reload_all()

    # ---------------- chat jobs ----------------
    def _on_send(self):
        if self.job is not None and self.job.isRunning():
            return
        prompt = self.chat_view.input.toPlainText().strip()
        if not prompt:
            return
        if not self.store.chat_apis():
            self._warn_no_apis()
            return

        self.chat_view.input.clear()
        chat = self.store.active_chat
        mode = self.chat_view.current_mode()

        if mode == "team":
            if not self.store.enabled_agents():
                QtWidgets.QMessageBox.warning(
                    self, "No agents",
                    "Tick at least one agent in the Team tab first.")
                return
            self.store.settings["max_rounds"] = self.chat_view.rounds.value()
            strategy = self.chat_view.strategy.currentText()
            runner = team.run_team
            args = (self.store, chat, prompt, strategy,
                    self.chat_view.rounds.value())
        else:
            runner = team.run_chat
            args = (self.store, chat, prompt)

        self._start_job(runner, args, streaming=(mode != "team"))
        if mode != "team":
            self._streaming = True
            leader = self.store.leader()
            self.chat_view.begin_stream(
                leader.name if leader else "Assistant",
                leader.color if leader else theme.ACCENT)
        self._status("{0} is thinking...".format(
            "The team" if mode == "team" else "Assistant"))
        self.sidebar.refresh_chats()

    def _start_job(self, runner, args, streaming=False):
        self.job = Job(runner, args)
        self.job.event.connect(self._on_event)
        self.job.finished.connect(self._on_finished)
        self.job.start()

    def _on_event(self, kind, payload):
        """Slot for job events. Never let an exception escape into Qt."""
        try:
            self._dispatch(kind, payload)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._status("UI error: {0}".format(exc))
            if getattr(self, "_streaming", False):
                self.chat_view.end_stream()
                self._streaming = False

    def _dispatch(self, kind, payload):
        if kind == "status":
            self._status(str(payload))
        elif kind == "delta":
            if getattr(self, "_streaming", False):
                self.chat_view.append_delta(payload.get("text", ""))
            return
        elif kind == "message":
            if getattr(self, "_streaming", False):
                # the streamed text is already on screen; the full re-render
                # in _on_finished will draw it as a proper bubble
                self.chat_view.end_stream()
                self._streaming = False
                return
            self.chat_view._append_message(payload)
        elif kind == "image":
            self.image_view.show_image(path=payload.get("path") or None)
            self.image_view.refresh_gallery()
            self.image_view.note(
                "{0} - {1:.1f}s".format(payload.get("label", "Image"),
                                        self._elapsed), "ok")
        elif kind == "error":
            self.image_view.note(str(payload), "error")
            if getattr(self, "_streaming", False):
                self.chat_view.end_stream()
                self._streaming = False
                self.chat_view._append_notice(str(payload), "error")
            else:
                self._status("Error: {0}".format(payload))
                self.chat_view._append_notice(str(payload), "error")
        elif kind == "done":
            self._elapsed = payload.get("elapsed", 0)

    def _on_finished(self, summary):
        if getattr(self, "_streaming", False):
            self.chat_view.end_stream()
            self._streaming = False

        bits = []
        if summary.get("elapsed") is not None:
            bits.append("{0:.1f}s".format(summary["elapsed"]))
        if summary.get("tokens"):
            bits.append("{0} tokens".format(summary["tokens"]))
        if summary.get("turns"):
            bits.append("{0} agent turns".format(summary["turns"]))
        self.chat_view.set_busy(False)
        self.image_view.set_busy(False)
        self.progress.setVisible(False)
        if not self.store.save():
            self._status("Could not save settings - see error.log in "
                         "{0}".format(self.store.folder))
        else:
            self._status("Done" if summary.get("ok") else "Stopped",
                         "  |  ".join(bits))
        self._reload_transcript()
        self.sidebar.refresh_agents()

    def _on_stop(self):
        if self.job is not None and self.job.isRunning():
            self._status("Stopping...")
            self.job.stop()
            self.job = None
            self.chat_view.set_busy(False)
            self.image_view.set_busy(False)
            self.progress.setVisible(False)

    # ---------------- image jobs ----------------
    def _on_generate_image(self):
        if self.job is not None and self.job.isRunning():
            return
        prompt = self.image_view.current_prompt()
        if not prompt:
            QtWidgets.QMessageBox.warning(self, "No prompt",
                                          "Describe the picture first.")
            return

        chat = self.store.active_chat
        chat.image_prompt = prompt
        chat.image_mode = self.image_view.current_mode()
        chat.image_api_id = self.image_view.api.currentData() or ""
        self.store.save()

        profile = self.store.api_by_id(chat.image_api_id)
        mode = chat.image_mode
        runner = image_job.run_image
        args = (self.store, chat, profile, mode, prompt,
                self.image_view.current_size())

        self.image_view.set_busy(True)
        self.image_view.note("Working...", "info")
        self._status("Image: {0}".format(
            image_job.MODE_LABELS.get(mode, mode)))
        self.progress.setVisible(True)
        self._start_job(runner, args)

    # ---------------- dialogs ----------------
    def _open_settings(self):
        dialog = SettingsDialog(self.store, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.apply_theme()
            self.image_view.exec_note.setChecked(
                bool(self.store.settings.get("allow_code_exec", False)))
            self._status("Settings saved")

    def open_setup_wizard(self):
        """First run: theme, font, first API."""
        from .setup_wizard import SetupWizard
        before = self.store.settings.get("theme_id")
        wizard = SetupWizard(self.store, self.themes, self)
        result = wizard.exec_()
        self.apply_theme()
        self.sidebar.refresh_apis()
        self.chat_view.refresh_apis()
        self.image_view.refresh_apis()
        self.sidebar.refresh_agents()
        self._reload_transcript()
        if result == QtWidgets.QDialog.Accepted:
            changed = self.store.settings.get("theme_id") != before
            self._status("Setup done" if not changed else "Setup done")
        return result

    def _open_about(self):
        from .. import __version__
        data_dir = self.store.path
        QtWidgets.QMessageBox.about(
            self, "About LakeAgent",
            "<h3>LakeAgent {0}</h3>"
            "<p>Multi-agent desktop desk.<br>"
            "Built with Python + PyQt5.</p>"
            "<p><b>Chats</b> - many conversations side by side<br>"
            "<b>APIs</b> - add as many models as you like<br>"
            "<b>Team</b> - several agents working on one task<br>"
            "<b>Image</b> - an image API, or a text agent writing Python</p>"
            "<p style='color:#6c7086; font-size:11px;'>Config: {1}</p>"
            .format(__version__, os.path.dirname(data_dir)))

    # ---------------- window events ----------------
    def closeEvent(self, event):
        if self.job is not None and self.job.isRunning():
            answer = QtWidgets.QMessageBox.question(
                self, "Still working",
                "A job is still running. Quit anyway?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
            if answer != QtWidgets.QMessageBox.Yes:
                event.ignore()
                return
            self.job.stop()
        if not self.store.save():
            answer = QtWidgets.QMessageBox.warning(
                self, "Could not save",
                "Settings could not be written to:\n{0}\n\n"
                "Your work from this session will be lost."
                .format(self.store.folder),
                QtWidgets.QMessageBox.Ok)
        event.accept()