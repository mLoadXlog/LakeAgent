"""Wallpaper support: turn a picture into a ready-to-paint background.

Processing happens once at a fixed working size and is cached; painting then
just scales it, so dragging the window edge stays smooth.
"""
import io
import os

from PIL import Image, ImageChops, ImageFilter
from PyQt5 import QtCore, QtGui

from .themes import to_rgb

WORK_SIZE = (2400, 1500)
BLEND_LABELS = ["Over", "Overlap", "Multiply", "Screen", "Darken", "Lighten"]

_cache = {}


def pil_to_pixmap(image):
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    pixmap = QtGui.QPixmap()
    pixmap.loadFromData(buffer.getvalue(), "PNG")
    return pixmap


def _blend(base, photo, mode):
    if mode == "overlay":
        return ImageChops.overlay(base, photo)
    if mode == "multiply":
        return ImageChops.multiply(base, photo)
    if mode == "screen":
        return ImageChops.screen(base, photo)
    if mode == "darken":
        return ImageChops.darker(base, photo)
    if mode == "lighten":
        return ImageChops.lighter(base, photo)
    return photo


def _cover(image, width, height, zoom=100):
    image = image.convert("RGB")
    scale = max(width / image.width, height / image.height)
    if zoom and zoom != 100:
        scale *= float(zoom) / 100.0
    new_w = max(width, int(image.width * scale))
    new_h = max(height, int(image.height * scale))
    image = image.resize((new_w, new_h), Image.LANCZOS)
    left = (image.width - width) // 2
    top = (image.height - height) // 2
    return image.crop((left, top, left + width, top + height))


def cache_key(spec, base_color):
    path = spec.get("path", "")
    try:
        stamp = os.path.getmtime(path)
    except OSError:
        stamp = 0
    return (path, round(stamp, 3), WORK_SIZE, base_color,
            int(spec.get("blur", 0)), int(spec.get("opacity", 0)),
            spec.get("blend", "over"), int(spec.get("dim", 0)),
            int(spec.get("zoom", 100)))


def build(spec, base_color="#1e1e2e"):
    """Return a QPixmap for this wallpaper spec, or None when disabled."""
    path = (spec or {}).get("path", "")
    if not path or not os.path.isfile(path):
        return None

    key = cache_key(spec, base_color)
    if key in _cache:
        return _cache[key]

    try:
        source = Image.open(path)
    except Exception:  # noqa: BLE001
        return None

    width, height = WORK_SIZE
    photo = _cover(source, width, height, int(spec.get("zoom", 100)))

    blur = max(0.0, float(spec.get("blur", 0)))
    if blur > 0:
        photo = photo.filter(ImageFilter.GaussianBlur(blur * WORK_SIZE[0]
                                                      / 1920.0 * 2.0))

    base = Image.new("RGB", (width, height), to_rgb(base_color))
    mixed = _blend(base, photo, spec.get("blend", "over"))

    opacity = max(0.0, min(100.0, float(spec.get("opacity", 35)))) / 100.0
    if opacity <= 0:
        return None
    result = Image.blend(base, mixed, opacity)

    dim = max(0.0, min(100.0, float(spec.get("dim", 0)))) / 100.0
    if dim > 0:
        factor = 1.0 - 0.65 * dim
        result = Image.eval(result, lambda v: int(v * factor))

    pixmap = pil_to_pixmap(result)
    _cache[key] = pixmap
    if len(_cache) > 12:
        for stale in list(_cache)[:-12]:
            _cache.pop(stale, None)
    return pixmap


def clear_cache():
    _cache.clear()


def scaled(pixmap, size):
    """Scale a cached pixmap so it covers `size` (Qt caches the result)."""
    if pixmap is None or pixmap.isNull():
        return None
    if size.width() <= 0 or size.height() <= 0:
        # a zero dimension makes QPixmap.scaled divide by zero and abort
        return None
    if pixmap.size() == size:
        return pixmap
    return pixmap.scaled(size, QtCore.Qt.KeepAspectRatioByExpanding,
                         QtCore.Qt.SmoothTransformation)


def paint(painter, rect, pixmap):
    """Draw a wallpaper pixmap over `rect`, cropped to fill it.

    PyQt5 will not mix QRect and QRectF in drawPixmap, and a TypeError raised
    inside a paintEvent aborts the process, so everything is QRectF here.
    """
    if pixmap is None or pixmap.isNull():
        return
    if rect.width() <= 0 or rect.height() <= 0:
        return
    sized = scaled(pixmap, QtCore.QSize(rect.width(), rect.height()))
    if sized is None:
        return
    left = (sized.width() - rect.width()) / 2.0
    top = (sized.height() - rect.height()) / 2.0
    painter.drawPixmap(
        QtCore.QRectF(rect),
        sized,
        QtCore.QRectF(left, top, float(rect.width()), float(rect.height())))