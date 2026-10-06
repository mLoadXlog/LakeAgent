"""First run wizard: pick a theme, pick a font, add your first API."""
from PyQt5 import QtCore, QtGui, QtWidgets

from . import backdrop, theme as palette
from .theme_dialogs import ThemeEditorDialog, ThemePreview

STEPS = ["Welcome", "Theme", "Font", "API", "Ready"]


class ThemeCard(QtWidgets.QFrame):
    """One clickable theme in the setup menu."""

    chosen = QtCore.pyqtSignal(str)

    def __init__(self, theme, selected=False, parent=None):
        super(ThemeCard, self).__init__(parent)
        self.theme_id = theme.id
        self.setObjectName("ThemeCard")
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self.setFrameShape(QtWidgets.QFrame.NoFrame)
        self._selected = selected

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(5)

        swatches = QtWidgets.QHBoxLayout()
        swatches.setSpacing(0)
        for key in ("bg", "card", "accent", "fg"):
            chip = QtWidgets.QLabel()
            chip.setFixedSize(26, 20)
            chip.setStyleSheet(
                "background:{0}; border:1px solid {1};".format(
                    theme.get(key), theme.get("border")))
            swatches.addWidget(chip)
        layout.addLayout(swatches)

        self.label = QtWidgets.QLabel(theme.name)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.label)

        self.tag = QtWidgets.QLabel("wallpaper" if theme.wallpaper.get("path")
                                    else "{0} pt".format(theme.font_size))
        self.tag.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.tag)

        self._paint()
        self._wallpaper = theme

    def set_selected(self, selected):
        self._selected = selected
        self._paint()

    def _paint(self):
        if self._selected:
            self.setStyleSheet(
                "QFrame#ThemeCard {{ background:{0}; border:2px solid {1};"
                "border-radius:8px; }}"
                "QFrame#ThemeCard QLabel {{ color:{2}; }}"
                .format(palette.CARD_HI, palette.ACCENT, palette.FG))
        else:
            self.setStyleSheet(
                "QFrame#ThemeCard {{ background:{0}; border:1px solid {1};"
                "border-radius:8px; }}"
                "QFrame#ThemeCard QLabel {{ color:{2}; }}"
                .format(palette.CARD, palette.BORDER, palette.FG_DIM))

    def mousePressEvent(self, event):
        self.chosen.emit(self.theme_id)
        super(ThemeCard, self).mousePressEvent(event)


class SetupWizard(QtWidgets.QDialog):
    def __init__(self, store, themes, parent=None):
        super(SetupWizard, self).__init__(parent)
        self.store = store
        self.themes = themes
        self.chose_theme = False
        self.chose_font = False
        self.added_api = False
        self.setWindowTitle("LakeAgent - first setup")
        self.setMinimumSize(720, 560)
        self.resize(760, 620)
        self._build()
        self._goto(0)

    # ---------- layout ----------
    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        top = QtWidgets.QFrame()
        top.setObjectName("Topbar")
        top_layout = QtWidgets.QHBoxLayout(top)
        top_layout.setContentsMargins(20, 16, 20, 12)
        self.title = QtWidgets.QLabel()
        self.title.setObjectName("AppTitle")
        top_layout.addWidget(self.title)
        top_layout.addStretch(1)
        self.step_label = QtWidgets.QLabel()
        self.step_label.setStyleSheet("color:{0};".format(palette.MUTED))
        top_layout.addWidget(self.step_label)
        root.addWidget(top)

        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self._welcome_page())
        self.stack.addWidget(self._theme_page())
        self.stack.addWidget(self._font_page())
        self.stack.addWidget(self._api_page())
        self.stack.addWidget(self._ready_page())
        root.addWidget(self.stack, 1)

        bottom = QtWidgets.QFrame()
        bottom.setObjectName("Topbar")
        bottom_layout = QtWidgets.QHBoxLayout(bottom)
        bottom_layout.setContentsMargins(20, 10, 20, 14)

        self.skip = QtWidgets.QPushButton("Skip setup")
        self.skip.setObjectName("Ghost")
        self.skip.clicked.connect(self.accept)
        bottom_layout.addWidget(self.skip)
        bottom_layout.addStretch(1)

        self.back = QtWidgets.QPushButton("Back")
        self.back.setObjectName("Ghost")
        self.back.clicked.connect(lambda: self._goto(self.page - 1))
        bottom_layout.addWidget(self.back)

        self.next = QtWidgets.QPushButton("Next")
        self.next.setObjectName("Primary")
        self.next.setMinimumWidth(110)
        self.next.clicked.connect(self._advance)
        bottom_layout.addWidget(self.next)
        root.addWidget(bottom)

    def _welcome_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(12)

        head = QtWidgets.QLabel("Welcome to LakeAgent")
        head.setStyleSheet("font-size:20pt; font-weight:700; color:{0};"
                           .format(palette.ACCENT))
        layout.addWidget(head)

        body = QtWidgets.QLabel(
            "Three things to set up, takes a minute.\n\n"
            "1. A theme - five are included, or mix your own colours.\n"
            "2. A font and size - change it any time in Settings.\n"
            "3. An API - as many as you like later, one is enough to start.\n\n"
            "Everything is saved in lakeagent_data/config.json.")
        body.setWordWrap(True)
        body.setStyleSheet("color:{0}; font-size:11pt;".format(palette.FG_DIM))
        layout.addWidget(body)
        layout.addStretch(1)
        return page

    def _theme_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        head = QtWidgets.QLabel("Pick a theme")
        head.setStyleSheet("font-size:14pt; font-weight:700;")
        layout.addWidget(head)

        self.preview = ThemePreview()
        self.preview.setMinimumHeight(120)
        theme = self.themes.current()
        self.preview.set_theme({k: theme.get(k) for k in theme.colors},
                               self.themes.font_family(theme))
        layout.addWidget(self.preview)

        hint = QtWidgets.QLabel(
            "Click a theme to use it straight away. The last card is one you "
            "made; open it to change colours or add a background picture.")
        hint.setStyleSheet("color:{0}; font-size:11px;".format(palette.MUTED))
        layout.addWidget(hint)

        self.theme_grid = QtWidgets.QGridLayout()
        self.theme_grid.setSpacing(8)
        layout.addLayout(self.theme_grid)

        row = QtWidgets.QHBoxLayout()
        self.custom_button = QtWidgets.QPushButton("Make my own theme")
        self.custom_button.setObjectName("Primary")
        self.custom_button.clicked.connect(self._make_theme)
        row.addWidget(self.custom_button)
        row.addStretch(1)
        self.theme_note = QtWidgets.QLabel()
        self.theme_note.setStyleSheet("color:{0}; font-size:11px;"
                                      .format(palette.MUTED))
        row.addWidget(self.theme_note)
        layout.addLayout(row)
        layout.addStretch(1)

        self.rebuild_theme_grid()
        return page

    def rebuild_theme_grid(self):
        while self.theme_grid.count():
            item = self.theme_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        current = self.themes.current()
        for index, theme in enumerate(self.themes.all()):
            card = ThemeCard(theme, theme.id == current.id)
            card.chosen.connect(self._pick_theme)
            self.theme_grid.addWidget(card, index // 4, index % 4)
        for column in range(4):
            self.theme_grid.setColumnStretch(column, 1)
        self.theme_note.setText("{0} themes available".format(
            len(self.themes.all())))

    def _pick_theme(self, theme_id):
        if self.themes.select(theme_id):
            self.chose_theme = True
            theme = self.themes.current()
            self.font_family.setCurrentFont(QtGui.QFont(
                self.themes.font_family(theme)))
            self.font_size.setValue(self.themes.font_size(theme))
            self.font_preview.setText(
                "Aa  Bb  Cc  123  -_{}+=\nLakeAgent preview text")
            palette.use(theme)
            self.app().setStyleSheet(palette.stylesheet(
                self.themes.font_size(theme), self.themes.font_family(theme)))
            self.rebuild_theme_grid()
            self.preview.set_theme(
                {k: theme.get(k) for k in theme.colors},
                self.themes.font_family(theme))
            self.preview.set_wallpaper(backdrop.build(
                theme.wallpaper, theme.get("bg")))

    def _make_theme(self):
        dialog = ThemeEditorDialog(self.themes, None, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            saved = self.themes.save_theme(dialog.result_theme)
            self.chose_theme = True
            self._pick_theme(saved.id)

    def _font_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(12)

        head = QtWidgets.QLabel("Font")
        head.setStyleSheet("font-size:14pt; font-weight:700;")
        layout.addWidget(head)

        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Typeface"))
        self.font_family = QtWidgets.QFontComboBox()
        self.font_family.setEditable(False)
        theme = self.themes.current()
        self.font_family.setCurrentFont(
            QtGui.QFont(self.themes.font_family(theme)))
        self.font_family.currentFontChanged.connect(self._font_changed)
        row.addWidget(self.font_family, 1)
        layout.addLayout(row)

        size_row = QtWidgets.QHBoxLayout()
        size_row.addWidget(QtWidgets.QLabel("Size"))
        self.font_size = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.font_size.setRange(8, 18)
        self.font_size.setValue(self.themes.font_size(theme))
        self.font_size.valueChanged.connect(self._font_changed)
        size_row.addWidget(self.font_size, 1)
        self.font_size_label = QtWidgets.QLabel(
            str(self.font_size.value()))
        self.font_size_label.setFixedWidth(28)
        size_row.addWidget(self.font_size_label)
        layout.addLayout(size_row)

        quick = QtWidgets.QHBoxLayout()
        for value in (9, 10, 11, 12, 14):
            button = QtWidgets.QPushButton("{0} pt".format(value))
            button.setObjectName("Ghost")
            button.clicked.connect(lambda _c, v=value: self._set_size(v))
            quick.addWidget(button)
        quick.addStretch(1)
        layout.addLayout(quick)

        self.font_preview = QtWidgets.QLabel("Aa  Bb  Cc  123  -_{}+=\n"
                                             "LakeAgent preview text")
        self.font_preview.setWordWrap(True)
        self.font_preview.setMinimumHeight(110)
        self.font_preview.setAlignment(QtCore.Qt.AlignCenter)
        self.font_preview.setStyleSheet(
            "background:{0}; border:1px solid {1}; border-radius:8px;"
            .format(palette.BG_DEEP, palette.BORDER))
        layout.addWidget(self.font_preview, 1)
        self._font_changed()
        return page

    def _set_size(self, value):
        self.font_size.setValue(value)

    def _font_changed(self, *_args):
        if not hasattr(self, "font_size"):
            return
        family = self.font_family.currentFont().family()
        size = self.font_size.value()
        self.font_size_label.setText(str(size))
        self.font_preview.setStyleSheet(
            "background:{0}; border:1px solid {1}; border-radius:8px;"
            "color:{2};".format(palette.BG_DEEP, palette.BORDER, palette.FG))
        self.font_preview.setFont(QtGui.QFont(family, size))
        self.app().setStyleSheet(palette.stylesheet(size, family))

    def _api_page(self):
        from .api_dialog import ApiDialog

        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(30, 20, 30, 20)
        layout.setSpacing(12)

        head = QtWidgets.QLabel("Add your first API")
        head.setStyleSheet("font-size:14pt; font-weight:700;")
        layout.addWidget(head)

        self.api_note = QtWidgets.QLabel(
            "Any OpenAI-compatible endpoint works.\n\n"
            "  Base URL   https://api.example.com  (or .../v1)\n"
            "  API Key    sk-...\n"
            "  Model      press Fetch to list them\n\n"
            "You can add as many as you like later in the APIs tab. "
            "You can also skip this and add one there.")
        self.api_note.setWordWrap(True)
        self.api_note.setStyleSheet(
            "color:{0}; font-size:11pt;".format(palette.FG_DIM))
        layout.addWidget(self.api_note)

        row = QtWidgets.QHBoxLayout()
        add = QtWidgets.QPushButton("Add an API")
        add.setObjectName("Primary")
        add.clicked.connect(lambda: self._add_api(ApiDialog))
        row.addWidget(add)
        row.addStretch(1)
        self.api_state = QtWidgets.QLabel()
        self.api_state.setStyleSheet("color:{0};".format(palette.GREEN))
        row.addWidget(self.api_state)
        layout.addLayout(row)
        layout.addStretch(1)
        return page

    def _add_api(self, dialog_class):
        dialog = dialog_class(self.store, None, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            profile = getattr(dialog, "result_profile", None)
            if profile is not None:
                self.store.add_api(profile)
                self.store.save()
                self.added_api = True
                self.api_state.setText(
                    "added: {0} ({1})".format(profile.name, profile.model
                                              or "no model"))

    def _ready_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(30, 24, 30, 24)
        layout.setSpacing(12)

        head = QtWidgets.QLabel("All set")
        head.setStyleSheet("font-size:18pt; font-weight:700; color:{0};"
                           .format(palette.GREEN))
        layout.addWidget(head)

        theme = self.themes.current()
        self.summary = QtWidgets.QLabel()
        self.summary.setWordWrap(True)
        self.summary.setText(
            "Theme    {0}\nFont     {1}, {2} pt\n"
            "APIs     {3}\nAgents   {4} ready in the Team tab\n"
            .format(theme.name,
                    self.themes.font_family(theme),
                    self.themes.font_size(theme),
                    len(self.store.apis),
                    len(self.store.agents)))
        self.summary.setStyleSheet("color:{0}; font-size:11pt;"
                                   .format(palette.FG_DIM))
        layout.addWidget(self.summary)
        layout.addStretch(1)
        return page

    def _refresh_backdrop(self):
        theme = self.themes.current()
        pixmap = backdrop.build(theme.wallpaper, theme.get("bg"))
        self.preview.set_wallpaper(pixmap)
        self.preview.update()

    # ---------- navigation ----------
    def app(self):
        return QtWidgets.QApplication.instance()

    def page(self):
        return self.stack.currentIndex()

    def _goto(self, index):
        index = max(0, min(len(STEPS) - 1, index))
        self.stack.setCurrentIndex(index)
        self.title.setText("LakeAgent  -  {0}".format(STEPS[index]))
        self.step_label.setText("Step {0} of {1}".format(index + 1,
                                                           len(STEPS)))
        self.back.setEnabled(index > 0)
        self.next.setText("Finish" if index == len(STEPS) - 1 else "Next")
        self.skip.setVisible(index < len(STEPS) - 1)
        if index == len(STEPS) - 1:
            theme = self.themes.current()
            self.summary.setText(
                "Theme    {0}\nFont     {1}, {2} pt\n"
                "APIs     {3}\nAgents   {4} ready in the Team tab\n"
                .format(theme.name,
                        self.themes.font_family(theme),
                        self.themes.font_size(theme),
                        len(self.store.apis),
                        len(self.store.agents)))

    def _advance(self):
        if self.page() == 1:
            self._apply_theme_choice()
        elif self.page() == 2:
            self.themes.set_font(
                self.font_family.currentFont().family(),
                self.font_size.value())
            self.chose_font = True
        if self.page() >= len(STEPS) - 1:
            self.accept()
            return
        self._goto(self.page() + 1)

    def _apply_theme_choice(self):
        theme = self.themes.current()
        self.themes.set_font(self.font_family.currentFont().family(),
                             self.font_size.value())
        palette.use(theme)
        self.app().setStyleSheet(palette.stylesheet(
            self.themes.font_size(theme), self.themes.font_family(theme)))

    def accept(self):
        self._apply_theme_choice()
        if getattr(self, "font_size", None) is not None:
            self.themes.set_font(self.font_family.currentFont().family(),
                                 self.font_size.value())
        self.store.settings["setup_done"] = True
        self.store.save()
        super(SetupWizard, self).accept()