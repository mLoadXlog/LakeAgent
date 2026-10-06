"""Theme editor: mix colours, or drop a picture in as the background."""
from PyQt5 import QtCore, QtGui, QtWidgets

from . import backdrop, theme as palette
from .themes import (BASE_KEYS, BLEND_MODES, COLOR_KEYS, COLOR_LABELS,
                     Theme, derive_palette, to_rgb)


class ColorButton(QtWidgets.QPushButton):
    """A swatch that opens a colour picker."""

    colorPicked = QtCore.pyqtSignal(str)

    def __init__(self, value, parent=None):
        super(ColorButton, self).__init__(parent)
        self.value = value
        self.setFixedHeight(26)
        self.setMinimumWidth(74)
        self.clicked.connect(self._pick)
        self._paint()

    def set_value(self, value):
        self.value = value
        self._paint()

    def _paint(self):
        text = self.value
        red, green, blue = to_rgb(self.value)
        # relative luminance decides whether we need light or dark lettering
        brightness = (0.299 * red + 0.587 * green + 0.114 * blue) / 255.0
        label = "#11111b" if brightness > 0.55 else "#f4f4f8"
        self.setText(text)
        self.setStyleSheet(
            "QPushButton {{ background:{0}; color:{1}; border:1px solid {2};"
            "border-radius:5px; font-family:Consolas,monospace;"
            "font-size:9pt; }}"
            "QPushButton:hover {{ border-color:{3}; }}"
            .format(text, label, palette.BORDER, palette.ACCENT))

    def _pick(self):
        chosen = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(self.value), self, "Pick a colour")
        if chosen.isValid():
            self.set_value(chosen.name())
            self.colorPicked.emit(self.value)


class ThemePreview(QtWidgets.QWidget):
    """Tiny mock of the app so the user can see what they are choosing."""

    def __init__(self, parent=None):
        super(ThemePreview, self).__init__(parent)
        self.setMinimumHeight(104)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                           QtWidgets.QSizePolicy.Fixed)
        self._colors = {}
        self._wallpaper = None
        self._font = "Segoe UI"

    def set_theme(self, colors, font_family="Segoe UI"):
        self._colors = dict(colors)
        self._font = font_family
        self.update()

    def set_wallpaper(self, pixmap):
        self._wallpaper = pixmap
        self.update()

    def _c(self, key, fallback="#888888"):
        return QtGui.QColor(self._colors.get(key, fallback))

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        rect = self.rect().adjusted(0, 0, -1, -1)
        painter.fillRect(rect, self._c("bg"))

        if self._wallpaper is not None and not self._wallpaper.isNull():
            from . import backdrop as _bd
            _bd.paint(painter, rect, self._wallpaper)

        font = QtGui.QFont(self._font)
        font.setPointSize(9)

        side_w = int(rect.width() * 0.22)
        side = QtCore.QRect(rect.left(), rect.top(), side_w, rect.height())
        painter.fillRect(side, self._c("card"))
        painter.setPen(self._c("border"))
        painter.drawLine(side.topRight(), side.bottomRight())

        painter.setFont(font)
        painter.setPen(self._c("accent"))
        title_font = QtGui.QFont(self._font)
        title_font.setPointSize(10)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(QtCore.QRectF(side).adjusted(9, 8, -6, 0),
                         QtCore.Qt.AlignLeft | QtCore.Qt.AlignTop, "LakeAgent")

        painter.setFont(font)
        painter.setPen(self._c("fg_dim"))
        for index, width in enumerate((0.8, 0.6, 0.75)):
            top = rect.top() + 40 + index * 20
            row = QtCore.QRect(side.left() + 9, top,
                               int(side_w * 0.85 * width), 13)
            painter.setBrush(self._c("card_hi")
                             if index == 0 else self._c("bg_deep"))
            painter.setPen(self._c("border"))
            painter.drawRoundedRect(row, 4, 4)

        body_left = side.right() + 10
        body_w = rect.width() - side_w - 22

        painter.setPen(self._c("accent"))
        user_w = int(body_w * 0.55)
        user_bubble = QtCore.QRect(body_left + body_w - user_w,
                                   rect.top() + 10, user_w, 17)
        painter.setBrush(self._c("card_hi"))
        painter.setPen(self._c("border"))
        painter.drawRoundedRect(user_bubble, 5, 5)

        agent_w = int(body_w * 0.72)
        for index, top in enumerate((rect.top() + 36, rect.top() + 60)):
            height = 17 if index == 0 else 11
            bubble = QtCore.QRect(body_left, top, agent_w, height)
            painter.setBrush(self._c("card"))
            painter.setPen(self._c("border"))
            painter.drawRoundedRect(bubble, 5, 5)

        button_w = int(body_w * 0.18)
        button = QtCore.QRect(body_left + body_w - button_w,
                              rect.bottom() - 26, button_w, 17)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(self._c("accent"))
        painter.drawRoundedRect(button, 5, 5)
        painter.end()


class ThemeEditorDialog(QtWidgets.QDialog):
    """Build a theme from four base colours or by hand, plus a wallpaper."""

    def __init__(self, themes, theme=None, parent=None):
        super(ThemeEditorDialog, self).__init__(parent)
        self.themes = themes
        self.source = theme.copy() if theme else themes.current()
        self.is_new = theme is None
        self.setWindowTitle("New theme" if self.is_new else "Edit theme")
        self.setMinimumSize(660, 640)
        self._build()
        self._load()

    # ---------- layout ----------
    def _build(self):
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        head = QtWidgets.QVBoxLayout()
        head.setSpacing(8)
        self.preview = ThemePreview()
        head.addWidget(self.preview)

        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel("Name"))
        self.name = QtWidgets.QLineEdit()
        self.name.setPlaceholderText("Theme name")
        self.name.textChanged.connect(lambda _t: self._refresh_preview())
        row.addWidget(self.name, 1)

        row.addWidget(QtWidgets.QLabel("Start from"))
        self.start_from = QtWidgets.QComboBox()
        self.start_from.addItems(["This theme"]
                                  + [t.name for t in self.themes.all()])
        self.start_from.currentIndexChanged.connect(self._on_start_from)
        row.addWidget(self.start_from, 1)
        head.addLayout(row)

        font_row = QtWidgets.QHBoxLayout()
        font_row.addWidget(QtWidgets.QLabel("Font"))
        self.font_family = QtWidgets.QFontComboBox()
        self.font_family.setEditable(False)
        self.font_family.currentFontChanged.connect(self._font_changed)
        font_row.addWidget(self.font_family, 1)

        font_row.addWidget(QtWidgets.QLabel("Size"))
        self.font_size = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.font_size.setRange(8, 18)
        self.font_size.setMaximumWidth(190)
        self.font_size.valueChanged.connect(self._font_changed)
        font_row.addWidget(self.font_size)
        self.font_size_label = QtWidgets.QLabel("10")
        self.font_size_label.setFixedWidth(24)
        font_row.addWidget(self.font_size_label)
        head.addLayout(font_row)

        root.addLayout(head)

        self.tab_widget = QtWidgets.QTabWidget()
        tabs = self.tab_widget
        root.addWidget(tabs, 1)

        tabs.addTab(self._mix_tab(), "Mix colours")
        tabs.addTab(self._all_tab(), "Every colour")
        self.wallpaper_tab = self._wallpaper_tab()
        tabs.addTab(self.wallpaper_tab, "Background picture")

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        buttons.button(QtWidgets.QDialogButtonBox.Save).setText("Save theme")
        buttons.button(QtWidgets.QDialogButtonBox.Save).setObjectName("Primary")
        buttons.button(QtWidgets.QDialogButtonBox.Cancel).setText("Cancel")
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _mix_tab(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(9)

        hint = QtWidgets.QLabel(
            "Pick four colours. LakeAgent works out the other nine so the "
            "theme always looks right - on a light or a dark background.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color:{0};".format(palette.MUTED))
        layout.addWidget(hint)

        self.base_buttons = {}
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(7)
        for row, key in enumerate(BASE_KEYS):
            grid.addWidget(QtWidgets.QLabel(COLOR_LABELS[key]), row, 0)
            button = ColorButton("#888888")
            button.colorPicked.connect(self._on_base_picked)
            self.base_buttons[key] = button
            grid.addWidget(button, row, 1)
            grid.addWidget(self._reset_button(key), row, 2)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        derive = QtWidgets.QPushButton("Rebuild the other nine colours")
        derive.setObjectName("Primary")
        derive.clicked.connect(self._derive)
        layout.addWidget(derive)

        layout.addStretch(1)
        return page

    def _reset_button(self, key):
        button = QtWidgets.QPushButton("Reset")
        button.setObjectName("Ghost")
        button.clicked.connect(lambda _c, k=key: self._on_base_picked(
            self.source.get(k)))
        return button

    def _all_tab(self):
        page = QtWidgets.QWidget()
        scroll = QtWidgets.QScrollArea(page)
        scroll.setWidgetResizable(True)
        inner = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(inner)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(7)

        hint = QtWidgets.QLabel("Fine tune any single colour.")
        hint.setStyleSheet("color:{0};".format(palette.MUTED))
        layout.addWidget(hint)

        self.all_buttons = {}
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        for row, key in enumerate(COLOR_KEYS):
            grid.addWidget(QtWidgets.QLabel(COLOR_LABELS[key]), row, 0)
            button = ColorButton("#888888")
            button.colorPicked.connect(self._on_all_picked)
            self.all_buttons[key] = button
            grid.addWidget(button, row, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        layout.addStretch(1)

        scroll.setWidget(inner)
        box = QtWidgets.QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(scroll)
        return page

    def _wallpaper_tab(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        row = QtWidgets.QHBoxLayout()
        self.wall_path = QtWidgets.QLineEdit()
        self.wall_path.setReadOnly(True)
        self.wall_path.setPlaceholderText("No picture chosen")
        row.addWidget(self.wall_path, 1)
        pick = QtWidgets.QPushButton("Choose...")
        pick.clicked.connect(self._pick_wallpaper)
        row.addWidget(pick)
        clear = QtWidgets.QPushButton("Clear")
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
            readout.setFixedWidth(46)
            control.valueChanged.connect(
                lambda v: readout.setText("{0}{1}".format(v, suffix)))
            control.valueChanged.connect(self._refresh_preview)
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
        for label, value in BLEND_MODES:
            self.wall_blend.addItem(label, value)
        self.wall_blend.currentIndexChanged.connect(self._refresh_preview)
        blend_row.addWidget(self.wall_blend, 1)
        layout.addLayout(blend_row)

        note = QtWidgets.QLabel(
            "Overlap multiplies the picture with the theme colour so text stays "
            "readable. Strength decides how much of the picture shows.")
        note.setWordWrap(True)
        note.setStyleSheet("color:{0}; font-size:11px;".format(palette.MUTED))
        layout.addWidget(note)
        layout.addStretch(1)
        return page

    # ---------- state ----------
    def _load(self):
        self.colors = dict(self.source.colors)
        self.wallpaper = dict(self.source.wallpaper)

        if self.is_new:
            self.name.setText("My theme")
            self.start_from.setCurrentIndex(1)
        else:
            self.name.setText(self.source.name)

        self.font_family.setCurrentFont(QtGui.QFont(self.source.font_family))
        self.font_size.setValue(self.source.font_size)

        for key in BASE_KEYS:
            self.base_buttons[key].set_value(self.colors.get(key, "#888888"))
        for key in COLOR_KEYS:
            self.all_buttons[key].set_value(self.colors.get(key, "#888888"))

        self.wall_path.setText(self.wallpaper.get("path", ""))
        self.wall_blur.setValue(int(self.wallpaper.get("blur", 6)))
        self.wall_opacity.setValue(int(self.wallpaper.get("opacity", 35)))
        self.wall_dim.setValue(int(self.wallpaper.get("dim", 0)))
        self.wall_zoom.setValue(int(self.wallpaper.get("zoom", 100)))
        index = self.wall_blend.findData(self.wallpaper.get("blend", "over"))
        self.wall_blend.setCurrentIndex(index if index >= 0 else 0)
        self._refresh_preview()

    def _on_start_from(self, index):
        if index <= 0:
            return
        other = self.themes.all()[index - 1]
        for key in COLOR_KEYS:
            self.colors[key] = other.get(key)
            self.all_buttons[key].set_value(self.colors[key])
        for key in BASE_KEYS:
            self.base_buttons[key].set_value(self.colors[key])
        self._refresh_preview()

    def _on_base_picked(self, _value=None):
        for key in BASE_KEYS:
            self.colors[key] = self.base_buttons[key].value
        self._derive()

    def _on_all_picked(self, _value=None):
        for key in COLOR_KEYS:
            self.colors[key] = self.all_buttons[key].value
        for key in BASE_KEYS:
            self.base_buttons[key].set_value(self.colors[key])
        self._refresh_preview()

    def _derive(self):
        derived = derive_palette(
            self.base_buttons["bg"].value,
            self.base_buttons["card"].value,
            self.base_buttons["fg"].value,
            self.base_buttons["accent"].value)
        self.colors.update(derived)
        for key in COLOR_KEYS:
            if key in BASE_KEYS:
                continue
            self.all_buttons[key].set_value(self.colors[key])
        for key in BASE_KEYS:
            self.base_buttons[key].set_value(self.colors[key])
        self._refresh_preview()

    def _font_changed(self, *_args):
        self.font_size_label.setText(str(self.font_size.value()))
        self._refresh_preview()

    def _pick_wallpaper(self):
        path, _filter = QtWidgets.QFileDialog.getOpenFileName(
            self, "Choose a background picture", "",
            "Pictures (*.png *.jpg *.jpeg *.bmp *.webp);;All files (*.*)")
        if path:
            self.wallpaper["path"] = path
            self._show_wallpaper_path(path)
            self._refresh_preview()

    def _show_wallpaper_path(self, path):
        self.wall_path.setText(path)
        self.wall_path.setToolTip(path)
        self.wall_path.setCursorPosition(0)

    def _clear_wallpaper(self):
        self.wallpaper["path"] = ""
        self._show_wallpaper_path("")
        self._refresh_preview()

    def _current_wallpaper(self):
        spec = dict(self.wallpaper)
        spec["blur"] = self.wall_blur.value()
        spec["opacity"] = self.wall_opacity.value()
        spec["dim"] = self.wall_dim.value()
        spec["zoom"] = self.wall_zoom.value()
        spec["blend"] = self.wall_blend.currentData() or "over"
        return spec

    def _refresh_preview(self):
        family = self.font_family.currentFont().family()
        self.preview.set_theme(self.colors, family)
        pixmap = backdrop.build(self._current_wallpaper(),
                                self.colors.get("bg", palette.BG))
        self.preview.set_wallpaper(pixmap)

    # ---------- save ----------
    def _save(self):
        name = self.name.text().strip() or "My theme"
        spec = self._current_wallpaper()
        new_theme = Theme(
            self.source.id if not self.is_new else "user_new",
            name,
            self.colors,
            self.font_family.currentFont().family(),
            self.font_size.value(),
            spec,
            built_in=False,
        )
        self.result_theme = new_theme
        self.accept()