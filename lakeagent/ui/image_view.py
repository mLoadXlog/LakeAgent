"""Image studio. Two modes, one switch:

  Image API         -> call an image model
  Text Agent + Python-> a text agent writes Pillow code, we run it
"""
import io
import os
import traceback

from PyQt5 import QtCore, QtGui, QtWidgets
from PIL import Image as PilImage

from ..agents import image_job
from ..config import OUTPUT_DIR
from . import backdrop, theme

try:
    RESAMPLE = PilImage.Resampling.LANCZOS
except AttributeError:  # Pillow < 9.1
    RESAMPLE = PilImage.LANCZOS


def pil_to_pixmap(image, max_size=None):
    """PIL image -> QPixmap. Goes through PNG bytes so it works on any Pillow."""
    if max_size:
        image = image.copy()
        image.thumbnail(max_size, RESAMPLE)
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    pixmap = QtGui.QPixmap()
    pixmap.loadFromData(buffer.getvalue(), "PNG")
    return pixmap


class PreviewView(QtWidgets.QLabel):
    """Shows the generated picture on top of the theme / wallpaper."""

    def __init__(self, parent=None):
        super(PreviewView, self).__init__(parent)
        self.setAlignment(QtCore.Qt.AlignCenter)
        self._wallpaper = None
        self._base = QtGui.QColor(theme.BG_DEEP)
        self._empty = "No image yet"

    def set_backdrop(self, pixmap, base):
        self._wallpaper = pixmap
        self._base = QtGui.QColor(base)
        self.update()

    def paintEvent(self, event):
        # an exception inside a paintEvent aborts the whole process
        try:
            self._paint_mat()
        except Exception:  # noqa: BLE001
            traceback.print_exc()

    def _paint_mat(self):
        painter = QtGui.QPainter(self)
        try:
            painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
            painter.fillRect(self.rect(), self._base)
            backdrop.paint(painter, self.rect(), self._wallpaper)
            pixmap = self.pixmap()
            if pixmap is not None and not pixmap.isNull():
                self._draw_photo(painter, pixmap)
            else:
                painter.setPen(QtGui.QColor(theme.MUTED))
                painter.drawText(self.rect(), QtCore.Qt.AlignCenter,
                                 self._empty)
        finally:
            painter.end()

    def _draw_photo(self, painter, pixmap):
        frame = pixmap.size() + QtCore.QSize(16, 16)
        target = QtCore.QRect(
            QtCore.QPoint((self.width() - frame.width()) // 2,
                          (self.height() - frame.height()) // 2), frame)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(0, 0, 0, 120))
        painter.drawRoundedRect(target.adjusted(2, 4, 2, 6), 8, 8)
        painter.setBrush(QtGui.QColor(theme.BORDER))
        painter.drawRoundedRect(target, 8, 8)
        painter.drawPixmap(target.adjusted(8, 8, -8, -8), pixmap)


class ImageView(QtWidgets.QWidget):
    generateRequested = QtCore.pyqtSignal()
    modeChanged = QtCore.pyqtSignal(str)
    apiChanged = QtCore.pyqtSignal(str)
    backRequested = QtCore.pyqtSignal()

    MODE_ITEMS = [
        (image_job.MODE_API, "Image API"),
        (image_job.MODE_PAINTER, "Text Agent + Python"),
    ]

    def __init__(self, store, parent=None):
        super(ImageView, self).__init__(parent)
        self.store = store
        self._refs = []
        self._busy = False
        self._build()
        self.refresh_apis()

    def _build(self):
        root = QtWidgets.QHBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(12)

        # ---------------- left: controls ----------------
        left = QtWidgets.QFrame()
        left.setObjectName("StudioPanel")
        left.setFixedWidth(330)
        self._style_panel(left)
        left_layout = QtWidgets.QVBoxLayout(left)
        left_layout.setContentsMargins(14, 14, 14, 14)
        left_layout.setSpacing(9)

        head = QtWidgets.QHBoxLayout()
        head.setSpacing(8)
        self.back_button = QtWidgets.QPushButton("←  Back")
        self.back_button.setObjectName("Ghost")
        self.back_button.setToolTip("Back to the chat")
        self.back_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.back_button.clicked.connect(self.backRequested.emit)
        head.addWidget(self.back_button)

        title = QtWidgets.QLabel("Image Studio")
        title.setStyleSheet(
            "font-size:15pt; font-weight:700; color:{0};"
            "background:transparent; border:none;".format(theme.ACCENT))
        head.addWidget(title)
        head.addStretch(1)
        left_layout.addLayout(head)

        def caption(text):
            label = QtWidgets.QLabel(text)
            label.setStyleSheet(
                "color:{0}; font-size:10pt; font-weight:600;"
                "background:transparent; border:none;".format(theme.MUTED))
            return label

        left_layout.addWidget(caption("Mode"))
        self.mode = QtWidgets.QComboBox()
        for key, label in self.MODE_ITEMS:
            self.mode.addItem(label, key)
        self.mode.currentIndexChanged.connect(self._on_mode)
        left_layout.addWidget(self.mode)

        left_layout.addWidget(caption("Image API"))
        self.api = QtWidgets.QComboBox()
        self.api.currentIndexChanged.connect(
            lambda _i: self.apiChanged.emit(self.api.currentData() or ""))
        left_layout.addWidget(self.api)

        left_layout.addWidget(caption("Size"))
        self.size = QtWidgets.QComboBox()
        self.size.setEditable(True)
        self.size.addItems(image_job.DEFAULT_SIZES)
        self.size.setCurrentText(self.store.settings.get("image_size", "768x768"))
        left_layout.addWidget(self.size)

        left_layout.addWidget(caption("Negative prompt"))
        self.negative = QtWidgets.QLineEdit()
        self.negative.setPlaceholderText("blurry, watermark, extra fingers")
        left_layout.addWidget(self.negative)

        left_layout.addWidget(caption("Prompt"))
        self.prompt = QtWidgets.QPlainTextEdit()
        self.prompt.setPlaceholderText(
            "a small cabin on a snowy lake at dusk, warm window light")
        self.prompt.setMinimumHeight(120)
        left_layout.addWidget(self.prompt, 1)

        self.mode_note = QtWidgets.QLabel()
        self.mode_note.setWordWrap(True)
        self.mode_note.setStyleSheet(
            "color:{0}; font-size:11px; background:transparent;"
            .format(theme.MUTED))
        left_layout.addWidget(self.mode_note)

        self.exec_note = QtWidgets.QCheckBox("Let the text agent run Python code")
        self.exec_note.setChecked(
            bool(self.store.settings.get("allow_code_exec", False)))
        self.exec_note.toggled.connect(self._on_exec_toggle)
        self.exec_note.setStyleSheet("background:transparent; border:none;")
        left_layout.addWidget(self.exec_note)

        row = QtWidgets.QHBoxLayout()
        self.generate = QtWidgets.QPushButton("Generate")
        self.generate.setObjectName("Primary")
        self.generate.setMinimumHeight(34)
        self.generate.clicked.connect(self.generateRequested.emit)
        row.addWidget(self.generate)

        self.stop = QtWidgets.QPushButton("Stop")
        self.stop.setObjectName("Ghost")
        self.stop.setEnabled(False)
        self.stop.clicked.connect(self._emit_stop)
        row.addWidget(self.stop)
        left_layout.addLayout(row)

        self.status = QtWidgets.QLabel("Ready")
        self.status.setWordWrap(True)
        self.status.setStyleSheet(
            "color:{0}; font-size:11px; background:transparent;".format(
                theme.FG_DIM))
        left_layout.addWidget(self.status)

        root.addWidget(left)

        # ---------------- right: preview + gallery ----------------
        right = QtWidgets.QVBoxLayout()
        right.setSpacing(10)

        self.preview = PreviewView()
        self.preview.setMinimumSize(360, 300)
        self.preview.setStyleSheet(
            "QFrame#StudioMat {{ border:1px solid {0}; border-radius:10px; }}"
            .format(theme.BORDER))
        right.addWidget(self.preview, 1)

        gallery_bar = QtWidgets.QHBoxLayout()
        gallery_bar.setSpacing(8)
        gallery_bar.addWidget(caption("Gallery"))
        self.gallery_count = QtWidgets.QLabel("0")
        self.gallery_count.setStyleSheet(
            "color:{0}; background:transparent; border:none;"
            .format(theme.ACCENT))
        gallery_bar.addWidget(self.gallery_count)
        gallery_bar.addStretch(1)

        self.open_folder = QtWidgets.QPushButton("Open folder")
        self.open_folder.setObjectName("Ghost")
        self.open_folder.clicked.connect(self._open_folder)
        gallery_bar.addWidget(self.open_folder)

        self.save_as = QtWidgets.QPushButton("Save as...")
        self.save_as.setObjectName("Ghost")
        self.save_as.clicked.connect(self._save_as)
        gallery_bar.addWidget(self.save_as)
        right.addLayout(gallery_bar)

        self.gallery = QtWidgets.QListWidget()
        self.gallery.setViewMode(QtWidgets.QListView.IconMode)
        self.gallery.setIconSize(QtCore.QSize(96, 96))
        self.gallery.setGridSize(QtCore.QSize(120, 118))
        self.gallery.setResizeMode(QtWidgets.QListView.Adjust)
        self.gallery.setFixedHeight(132)
        self.gallery.setFlow(QtWidgets.QListView.LeftToRight)
        self.gallery.itemClicked.connect(self._on_gallery_click)
        right.addWidget(self.gallery)

        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right)
        root.addWidget(right_widget, 1)

        self._on_mode()

    @staticmethod
    def _style_panel(frame):
        frame.setStyleSheet(
            "QFrame#StudioPanel {{ background:{0}; border:1px solid {1};"
            "border-radius:10px; }}".format(theme.CARD, theme.BORDER))

    def refresh_styles(self):
        """Re-apply the inline colours this view owns."""
        for frame in self.findChildren(QtWidgets.QFrame):
            if frame.objectName() == "StudioPanel":
                self._style_panel(frame)

    # ---------- state ----------
    def refresh_apis(self):
        current = self.api.currentData()
        self.api.blockSignals(True)
        self.api.clear()
        profiles = self.store.image_apis()
        if not profiles:
            self.api.addItem("(no image API - use Text Agent mode)", "")
        for profile in profiles:
            self.api.addItem(profile.label(), profile.id)
        index = self.api.findData(current)
        if index >= 0:
            self.api.setCurrentIndex(index)
        elif profiles:
            self.api.setCurrentIndex(0)
        self.api.blockSignals(False)

    def current_mode(self):
        return self.mode.currentData() or image_job.MODE_API

    def set_mode(self, mode):
        index = self.mode.findData(mode)
        if index >= 0 and index != self.mode.currentIndex():
            self.mode.setCurrentIndex(index)
        else:
            self._on_mode()

    def _on_mode(self):
        mode = self.current_mode()
        self.api.setEnabled(mode == image_job.MODE_API)
        self.negative.setEnabled(mode == image_job.MODE_API)
        self.exec_note.setEnabled(mode == image_job.MODE_PAINTER)
        if mode == image_job.MODE_API:
            self.mode_note.setText(
                "Sends the prompt straight to the selected image model.")
        else:
            self.mode_note.setText(
                "No image API? A text agent writes a Pillow script and "
                "LakeAgent runs it. If the code fails, LakeAgent draws the "
                "scene itself.")
        self.modeChanged.emit(mode)

    def _on_exec_toggle(self, on):
        self.store.settings["allow_code_exec"] = bool(on)
        self.store.save()

    def set_busy(self, busy):
        self._busy = busy
        self.generate.setEnabled(not busy)
        self.generate.setText("Working..." if busy else "Generate")
        self.stop.setEnabled(busy)
        self.prompt.setReadOnly(busy)

    def _emit_stop(self):
        if self._busy:
            self.set_busy(False)
            self.status.setText("Stopped.")

    # ---------- prompt state ----------
    def current_prompt(self):
        return self.prompt.toPlainText().strip()

    def current_size(self):
        return self.size.currentText().strip() or "768x768"

    def restore(self, prompt, mode=None):
        if mode:
            self.set_mode(mode)
        if prompt:
            self.prompt.setPlainText(prompt)

    # ---------- results ----------
    def set_backdrop(self, pixmap):
        self.preview.set_backdrop(pixmap, theme.BG_DEEP)
        self.preview.update()

    def show_image(self, path=None, pil=None):
        image = pil
        if image is None and path and os.path.exists(path):
            image = PilImage.open(path)
        if image is None:
            return
        target = self.preview.size() - QtCore.QSize(56, 56)
        max_size = (max(target.width(), 120), max(target.height(), 120))
        pixmap = pil_to_pixmap(image, max_size)
        if pixmap.isNull():
            return
        self.preview.setPixmap(pixmap)
        self._refs.append(pixmap)
        self.preview.update()

    def note(self, text, kind="info"):
        colors = {"info": theme.FG_DIM, "warn": theme.YELLOW,
                  "error": theme.RED, "ok": theme.GREEN}
        self.status.setStyleSheet(
            "color:{0}; font-size:11px; background:transparent;".format(
                colors.get(kind, theme.FG_DIM)))
        self.status.setText(text)

    # ---------- gallery ----------
    def refresh_gallery(self):
        self.gallery.clear()
        if not os.path.isdir(OUTPUT_DIR):
            self.gallery_count.setText("0")
            return
        names = sorted(
            (n for n in os.listdir(OUTPUT_DIR)
             if n.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))),
            key=lambda n: os.path.getmtime(os.path.join(OUTPUT_DIR, n)),
            reverse=True)
        self.gallery_count.setText(str(len(names)))
        for name in names[:60]:
            path = os.path.join(OUTPUT_DIR, name)
            try:
                icon = QtGui.QIcon(path)
            except Exception:  # noqa: BLE001
                continue
            item = QtWidgets.QListWidgetItem(icon, os.path.splitext(name)[0])
            item.setData(QtCore.Qt.UserRole, path)
            item.setToolTip(path)
            self.gallery.addItem(item)

    def _on_gallery_click(self, item):
        path = item.data(QtCore.Qt.UserRole)
        if path:
            self.show_image(path=path)

    def _open_folder(self):
        if not os.path.isdir(OUTPUT_DIR):
            os.makedirs(OUTPUT_DIR)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(OUTPUT_DIR))

    def _save_as(self):
        pixmap = self.preview.pixmap()
        if pixmap is None or pixmap.isNull():
            self.note("Generate something first.", "warn")
            return
        path, _ext = QtWidgets.QFileDialog.getSaveFileName(
            self, "Save image",
            os.path.join(OUTPUT_DIR, "lakeagent_image.png"),
            "PNG (*.png);;JPEG (*.jpg);;All files (*.*)")
        if path:
            if pixmap.save(path):
                self.note("Saved to {0}".format(path), "ok")
            else:
                self.note("Could not write that file.", "error")