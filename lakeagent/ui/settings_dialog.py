"""Settings: theme menu, font, wallpaper, and the runtime toggles."""
from PyQt5 import QtCore, QtGui, QtWidgets

from . import backdrop, theme as palette
from .themes import ThemeManager


class SettingsDialog(QtWidgets.QDialog):
    TABS = ["Look", "Font", "Background", "Behaviour"]

    def __init__(self, store, parent=None):
        super(SettingsDialog, self).__init__(parent)
        self.store = store
        self.themes = ThemeManager(store)
        self.setWindowTitle("Settings")
        self.setMinimumSize(660, 560)
        self.resize(700, 600)
        self._build()
        self._load()

    # ---------- layout ----------
    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self._look_tab(), "Look")
        self.tabs.addTab(self._font_tab(), "Font")
        self.tabs.addTab(self._wallpaper_tab(), "Background")
        self.tabs.addTab(self._behaviour_tab(), "Behaviour")
        root.addWidget(self.tabs, 1)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        buttons.button(QtWidgets.QDialogButtonBox.Save).setText("Save")
        buttons.button(QtWidgets.QDialogButtonBox.Save).setObjectName("Primary")
        buttons.button(QtWidgets.QDialogButtonBox.Cancel).setText("Cancel")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    # ---------- look ----------
    def _look_tab(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)

        self.theme_list = QtWidgets.QListWidget()
        self.theme_list.setIconSize(QtCore.QSize(56, 34))
        self.theme_list.itemSelectionChanged.connect(self._on_theme_picked)
        self.theme_list.setMinimumHeight(190)
        layout.addWidget(self.theme_list, 1)

        row = QtWidgets.QHBoxLayout()
        edit = QtWidgets.QPushButton("Edit this theme")
        edit.clicked.connect(self._edit_theme)
        row.addWidget(edit)
        self.make_theme = QtWidgets.QPushButton("New from colours")
        self.make_theme.setObjectName("Primary")
        self.make_theme.clicked.connect(self._make_theme)
        row.addWidget(self.make_theme)
        self.delete_theme = QtWidgets.QPushButton("Delete")
        self.delete_theme.setObjectName("Danger")
        self.delete_theme.clicked.connect(self._delete_theme)
        row.addWidget(self.delete_theme)
        row.addStretch(1)
        layout.addLayout(row)

        note = QtWidgets.QLabel(
            "Pick a theme on this tab. Pick your typeface and size on the Font "
            "tab, and use a picture as the background on the Background tab.")
        note.setWordWrap(True)
        note.setStyleSheet("color:{0}; font-size:11px;".format(palette.MUTED))
        layout.addWidget(note)
        return page

    def _fill_theme_list(self):
        self.theme_list.blockSignals(True)
        self.theme_list.clear()
        current = self.themes.current()
        for theme in self.themes.all():
            item = QtWidgets.QListWidgetItem(_swatch_icon(theme), theme.name)
            item.setData(QtCore.Qt.UserRole, theme.id)
            item.setToolTip("{0}{1}".format(
                theme.name,
                "  (yours)" if not theme.built_in else ""))
            self.theme_list.addItem(item)
            if theme.id == current.id:
                self.theme_list.setCurrentItem(item)
        self.theme_list.blockSignals(False)
        self.delete_theme.setEnabled(not current.built_in)

    def _selected_theme(self):
        items = self.theme_list.selectedItems()
        if not items:
            return None
        return self.themes.find(items[0].data(QtCore.Qt.UserRole))

    def _on_theme_picked(self):
        theme = self._selected_theme()
        if theme is None:
            return
        self.themes.select(theme.id)
        palette.use(theme)
        QtWidgets.QApplication.instance().setStyleSheet(
            palette.stylesheet(self.themes.font_size(theme),
                               self.themes.font_family(theme)))
        self._fill_theme_list()

    def _edit_theme(self):
        from .theme_dialogs import ThemeEditorDialog
        theme = self._selected_theme()
        dialog = ThemeEditorDialog(self.themes, theme, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.themes.save_theme(dialog.result_theme)
            self._fill_theme_list()
            self._on_theme_picked()

    def _make_theme(self):
        from .theme_dialogs import ThemeEditorDialog
        dialog = ThemeEditorDialog(self.themes, None, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            self.themes.save_theme(dialog.result_theme)
            self._fill_theme_list()
            self._on_theme_picked()

    def _delete_theme(self):
        theme = self._selected_theme()
        if theme is None or theme.built_in:
            return
        answer = QtWidgets.QMessageBox.question(
            self, "Delete theme", "Delete '{0}'?".format(theme.name),
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No)
        if answer == QtWidgets.QMessageBox.Yes:
            self.themes.delete_theme(theme.id)
            self._fill_theme_list()
            self._on_theme_picked()

    # ---------- font ----------
    def _font_tab(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Typeface"))
        self.font_family = QtWidgets.QFontComboBox()
        self.font_family.setEditable(False)
        self.font_family.currentFontChanged.connect(self._font_changed)
        row.addWidget(self.font_family, 1)
        layout.addLayout(row)

        size_row = QtWidgets.QHBoxLayout()
        size_row.addWidget(QtWidgets.QLabel("Size"))
        self.font_size = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.font_size.setRange(8, 18)
        self.font_size.valueChanged.connect(self._font_changed)
        size_row.addWidget(self.font_size, 1)
        self.font_size_label = QtWidgets.QLabel("10")
        self.font_size_label.setFixedWidth(30)
        size_row.addWidget(self.font_size_label)
        layout.addLayout(size_row)

        quick = QtWidgets.QHBoxLayout()
        for value in (9, 10, 11, 12, 14, 16):
            button = QtWidgets.QPushButton("{0} pt".format(value))
            button.setObjectName("Ghost")
            button.clicked.connect(lambda _c, v=value: self.font_size.setValue(v))
            quick.addWidget(button)
        quick.addStretch(1)
        layout.addLayout(quick)

        self.font_preview = QtWidgets.QLabel(
            "Aa  Bb  Cc  123  -_{}+=\nThe quick brown fox jumps over the lazy "
            "dog. 0123456789")
        self.font_preview.setWordWrap(True)
        self.font_preview.setAlignment(QtCore.Qt.AlignCenter)
        self.font_preview.setMinimumHeight(130)
        self.font_preview.setStyleSheet(
            "background:{0}; border:1px solid {1}; border-radius:8px;"
            "color:{2};".format(palette.BG_DEEP, palette.BORDER, palette.FG))
        layout.addWidget(self.font_preview, 1)
        return page

    def _font_changed(self, *_args):
        if not hasattr(self, "font_size"):
            return
        family = self.font_family.currentFont().family()
        size = self.font_size.value()
        self.font_size_label.setText(str(size))
        self.font_preview.setFont(QtGui.QFont(family, size))
        QtWidgets.QApplication.instance().setStyleSheet(
            palette.stylesheet(size, family))

    # ---------- background ----------
    def _wallpaper_tab(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)

        self.wall_label = QtWidgets.QLineEdit()
        self.wall_label.setReadOnly(True)
        layout.addWidget(self.wall_label)

        row = QtWidgets.QHBoxLayout()
        pick = QtWidgets.QPushButton("Choose picture...")
        pick.clicked.connect(self._pick_wallpaper)
        row.addWidget(pick)
        clear = QtWidgets.QPushButton("No picture")
        clear.setObjectName("Ghost")
        clear.clicked.connect(self._clear_wallpaper)
        row.addWidget(clear)
        layout.addLayout(row)

        def slider(label, minimum, maximum, value, suffix=""):
            holder = QtWidgets.QHBoxLayout()
            holder.addWidget(QtWidgets.QLabel(label))
            control = QtWidgets.QSlider(QtCore.Qt.Horizontal)
            control.setRange(minimum, maximum)
            control.setValue(value)
            readout = QtWidgets.QLabel("{0}{1}".format(value, suffix))
            readout.setFixedWidth(50)
            control.valueChanged.connect(
                lambda v: readout.setText("{0}{1}".format(v, suffix)))
            control.valueChanged.connect(self._preview_wall)
            holder.addWidget(control, 1)
            holder.addWidget(readout)
            layout.addLayout(holder)
            return control

        self.wall_blur = slider("Blur", 0, 40, 6)
        self.wall_opacity = slider("Strength", 0, 100, 35, "%")
        self.wall_dim = slider("Dim", 0, 100, 0, "%")
        self.wall_zoom = slider("Zoom", 100, 250, 100, "%")

        blend_row = QtWidgets.QHBoxLayout()
        blend_row.addWidget(QtWidgets.QLabel("Blend"))
        self.wall_blend = QtWidgets.QComboBox()
        from .themes import BLEND_MODES
        for label, value in BLEND_MODES:
            self.wall_blend.addItem(label, value)
        self.wall_blend.currentIndexChanged.connect(self._preview_wall)
        blend_row.addWidget(self.wall_blend, 1)
        layout.addLayout(blend_row)

        self.wall_preview = _WallPreview()
        self.wall_preview.setMinimumHeight(140)
        layout.addWidget(self.wall_preview, 1)

        note = QtWidgets.QLabel(
            "The picture sits behind the chat and behind the image preview. "
            "Use Overlap or Multiply with a low strength so text stays "
            "readable.")
        note.setWordWrap(True)
        note.setStyleSheet("color:{0}; font-size:11px;".format(palette.MUTED))
        layout.addWidget(note)
        return page

    def _wall_spec(self):
        theme = self.themes.current()
        spec = dict(theme.wallpaper)
        spec["path"] = self.wall_label.text()
        spec["blur"] = self.wall_blur.value()
        spec["opacity"] = self.wall_opacity.value()
        spec["dim"] = self.wall_dim.value()
        spec["zoom"] = self.wall_zoom.value()
        spec["blend"] = self.wall_blend.currentData() or "over"
        return spec

    def _pick_wallpaper(self):
        path, _filter = QtWidgets.QFileDialog.getOpenFileName(
            self, "Choose a background picture", "",
            "Pictures (*.png *.jpg *.jpeg *.bmp *.webp);;All files (*.*)")
        if path:
            self._show_wallpaper_path(path)
            self._preview_wall()

    def _show_wallpaper_path(self, path):
        self.wall_label.setText(path)
        self.wall_label.setToolTip(path)
        self.wall_label.setCursorPosition(0)

    def _clear_wallpaper(self):
        self._show_wallpaper_path("")
        self._preview_wall()

    def _preview_wall(self):
        theme = self.themes.current()
        self.wall_preview.set_colors(theme.colors)
        self.wall_preview.set_wallpaper(
            backdrop.build(self._wall_spec(), theme.get("bg")))

    # ---------- behaviour ----------
    def _behaviour_tab(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)

        self.stream = QtWidgets.QCheckBox("Stream answers token by token")
        self.exec_code = QtWidgets.QCheckBox(
            "Let the text agent run generated Python code")
        self.exec_code.setToolTip(
            "Needed for the Text Agent + Python image mode.")
        self.save_images = QtWidgets.QCheckBox(
            "Save generated images to disk")
        for widget in (self.stream, self.exec_code, self.save_images):
            layout.addWidget(widget)

        from ..config import data_dir_summary
        box = QtWidgets.QGroupBox("Where your data lives")
        box_layout = QtWidgets.QVBoxLayout(box)
        self.paths_label = QtWidgets.QLabel(data_dir_summary())
        self.paths_label.setWordWrap(True)
        self.paths_label.setTextInteractionFlags(
            QtCore.Qt.TextSelectableByMouse)
        box_layout.addWidget(self.paths_label)
        row = QtWidgets.QHBoxLayout()
        row.addStretch(1)
        open_folder = QtWidgets.QPushButton("Open folder")
        open_folder.setObjectName("Ghost")
        open_folder.clicked.connect(self._open_data_folder)
        row.addWidget(open_folder)
        box_layout.addLayout(row)
        layout.addWidget(box)
        layout.addStretch(1)
        return page

    def _open_data_folder(self):
        import os

        from PyQt5 import QtGui

        from ..config import DATA_DIR
        if not os.path.isdir(DATA_DIR):
            os.makedirs(DATA_DIR)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(DATA_DIR))

    # ---------- state ----------
    def _load(self):
        self._fill_theme_list()
        theme = self.themes.current()
        self.font_family.setCurrentFont(
            QtGui.QFont(self.themes.font_family(theme)))
        self.font_size.setValue(self.themes.font_size(theme))
        self._font_changed()

        self._show_wallpaper_path(theme.wallpaper.get("path", ""))
        self.wall_blur.setValue(int(theme.wallpaper.get("blur", 6)))
        self.wall_opacity.setValue(int(theme.wallpaper.get("opacity", 35)))
        self.wall_dim.setValue(int(theme.wallpaper.get("dim", 0)))
        self.wall_zoom.setValue(int(theme.wallpaper.get("zoom", 100)))
        index = self.wall_blend.findData(theme.wallpaper.get("blend", "over"))
        self.wall_blend.setCurrentIndex(index if index >= 0 else 0)
        self._preview_wall()

        settings = self.store.settings
        self.stream.setChecked(bool(settings.get("stream", True)))
        self.exec_code.setChecked(
            bool(settings.get("allow_code_exec", False)))
        self.save_images.setChecked(
            bool(settings.get("save_images", True)))

    def _save(self):
        self.themes.set_font(self.font_family.currentFont().family(),
                             self.font_size.value())
        theme = self.themes.current()
        for index, item in enumerate(self.store.settings.get("user_themes")
                                     or []):
            if item.get("id") == theme.id:
                item["wallpaper"] = self._wall_spec()
                self.store.settings["user_themes"][index] = item
        if theme.built_in:
            self.store.settings.setdefault("wallpapers", {})
            self.store.settings["wallpapers"][theme.id] = self._wall_spec()

        self.store.settings["stream"] = self.stream.isChecked()
        self.store.settings["allow_code_exec"] = self.exec_code.isChecked()
        self.store.settings["save_images"] = self.save_images.isChecked()

        if not self.store.save():
            QtWidgets.QMessageBox.critical(
                self, "Cannot save",
                "Your settings could not be written to:\n{0}\n\n"
                "Check the folder is not read only, or set LAKEAGENT_HOME to "
                "a folder you can write to."
                .format(self.store.folder))
            return
        self.accept()


class _WallPreview(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super(_WallPreview, self).__init__(parent)
        self.setMinimumHeight(120)
        self._pixmap = None
        self._colors = {}

    def set_wallpaper(self, pixmap):
        self._pixmap = pixmap
        self.update()

    def set_colors(self, colors):
        self._colors = dict(colors)
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.fillRect(self.rect(),
                         QtGui.QColor(self._colors.get("bg", palette.BG)))
        backdrop.paint(painter, self.rect(), self._pixmap)
        bubble = self.rect().adjusted(14, 14, -14, -30)
        painter.setPen(QtGui.QColor(self._colors.get("border", palette.BORDER)))
        painter.setBrush(QtGui.QColor(self._colors.get("card",
                                                       palette.CARD)))
        painter.drawRoundedRect(bubble, 7, 7)
        painter.setPen(QtGui.QColor(self._colors.get("fg", palette.FG)))
        font = QtGui.QFont()
        font.setPointSize(10)
        painter.setFont(font)
        painter.drawText(bubble.adjusted(12, 8, -12, 0), QtCore.Qt.AlignLeft
                         | QtCore.Qt.AlignTop,
                         "Text stays readable on top of the picture")
        painter.end()


def _swatch_icon(theme):
    """Three stacked colour bars, used as the list icon."""
    pixmap = QtGui.QPixmap(56, 34)
    pixmap.fill(QtGui.QColor(theme.get("bg")))
    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
    rect = pixmap.rect().adjusted(2, 2, -2, -2)
    painter.setPen(QtGui.QColor(theme.get("border")))
    painter.setBrush(QtGui.QColor(theme.get("card")))
    painter.drawRoundedRect(rect.adjusted(0, 0, 0, -12), 4, 4)
    painter.setBrush(QtGui.QColor(theme.get("accent")))
    painter.drawRoundedRect(rect.adjusted(6, 6, -6, -3), 3, 3)
    painter.end()
    return QtGui.QIcon(pixmap)