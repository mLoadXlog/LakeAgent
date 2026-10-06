"""Tools used by the agents: code execution and the local Python painter.

The painter is what makes "no image API" mode work: a text agent writes a
Pillow script, we run it and get a real image back.
"""
import builtins
import hashlib
import io
import math
import os
import random
import re
import sys
import traceback

from PIL import (Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter,
                   ImageFont)

PAINTER_GUIDE = """You draw an image with Python + Pillow.

Rules:
1. Output ONE python code block, nothing else.
2. Start from `img = Image.new("RGB", (WIDTH, HEIGHT), (r, g, b))`.
3. Use `draw = ImageDraw.Draw(img)` for shapes and lines.
4. Use `ImageDraw.Draw(img).text(...)` for any text.
5. Allowed imports: `from PIL import Image, ImageDraw, ImageFilter, ImageFont`
   plus `math`, `random`, `time`.
6. The last line must not be required; the variable `img` is what gets saved.
7. Keep it under 60 lines. Make it look good: layers, gradients, soft shadows.
"""


class ToolError(Exception):
    pass


# ---------------------------------------------------------------- code runner
SAFE_BUILTIN_NAMES = [
    "abs", "all", "any", "bool", "bytes", "callable", "chr", "dict", "divmod",
    "enumerate", "filter", "float", "format", "frozenset", "hash", "hex",
    "int", "isinstance", "issubclass", "iter", "len", "list", "map", "max",
    "min", "next", "oct", "ord", "pow", "print", "range", "repr", "reversed",
    "round", "set", "slice", "sorted", "str", "sum", "tuple", "type", "zip",
    "True", "False", "None", "Exception", "ValueError", "TypeError", "KeyError",
    "IndexError", "RuntimeError", "ArithmeticError", "ZeroDivisionError",
]


def _safe_builtins():
    import builtins as _b
    allowed = {}
    for name in SAFE_BUILTIN_NAMES:
        if hasattr(_b, name):
            allowed[name] = getattr(_b, name)
    allowed["__import__"] = _guarded_import
    return allowed


ALLOWED_MODULES = {
    "math", "random", "time", "string", "itertools", "functools", "datetime",
    "PIL", "Image", "ImageDraw", "ImageFilter", "ImageFont", "json", "re",
}


def _guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
    root = (name or "").split(".")[0]
    if root not in ALLOWED_MODULES:
        raise ImportError("Module '{0}' is not allowed".format(name))
    return builtins.__import__(name, globals, locals, fromlist, level)


def run_python(code, timeout_note="", extra=None):
    """Run code in a restricted namespace. Returns (result_obj, stdout)."""
    buffer = io.StringIO()
    old_stdout = sys.stdout
    namespace = {
        "__builtins__": _safe_builtins(),
        "__name__": "lakeagent_sandbox",
        "Image": Image,
        "ImageDraw": ImageDraw,
        "ImageFilter": ImageFilter,
        "ImageFont": ImageFont,
    }
    if extra:
        namespace.update(extra)
    sys.stdout = buffer
    try:
        exec(compile(code, "<lakeagent>", "exec"), namespace)  # noqa: S102
    except Exception as exc:
        sys.stdout = old_stdout
        detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        raise ToolError("{0}\n{1}".format(detail, timeout_note).strip())
    finally:
        sys.stdout = old_stdout
    return namespace, buffer.getvalue()


# ---------------------------------------------------------------- painter
RESULT_NAMES = ["img", "image", "result", "out", "canvas", "picture", "photo"]


def run_painter(code, width, height):
    """Execute painter code and return the resulting PIL image."""
    header = (
        "WIDTH = {0}\nHEIGHT = {1}\n".format(int(width), int(height))
    )
    if not re.search(r"\bImage\.new\b", code):
        header += 'img = Image.new("RGB", (WIDTH, HEIGHT), (18, 20, 32))\n'
        header += "draw = ImageDraw.Draw(img)\n"

    namespace, _out = run_python(header + code)
    for name in RESULT_NAMES:
        value = namespace.get(name)
        if isinstance(value, Image.Image):
            return value.convert("RGB")
    raise ToolError(
        "The script did not create an image. "
        "Assign your picture to a variable named `img`.")


# ---------------------------------------------------------------- fallback art
THEMES = {
    "sunset": ((250, 168, 92), (108, 62, 140), (40, 26, 62)),
    "sunrise": ((255, 214, 165), (226, 122, 96), (58, 46, 96)),
    "night": ((10, 14, 38), (28, 34, 84), (3, 5, 16)),
    "ocean": ((18, 78, 140), (10, 40, 78), (4, 18, 38)),
    "sea": ((18, 78, 140), (10, 40, 78), (4, 18, 38)),
    "forest": ((38, 92, 62), (18, 56, 44), (8, 26, 24)),
    "snow": ((214, 226, 245), (150, 172, 210), (86, 104, 140)),
    "winter": ((214, 226, 245), (150, 172, 210), (86, 104, 140)),
    "desert": ((232, 176, 106), (196, 122, 68), (108, 66, 44)),
    "city": ((36, 40, 62), (18, 20, 34), (8, 9, 16)),
    "space": ((8, 6, 30), (34, 18, 66), (2, 2, 10)),
    "aurora": ((8, 20, 44), (14, 60, 72), (4, 10, 24)),
    "dawn": ((255, 226, 190), (140, 158, 214), (44, 52, 92)),
}


def _pick_theme(prompt):
    text = (prompt or "").lower()
    for key, colors in THEMES.items():
        if key in text:
            return colors
    return THEMES["sunset"]


def _seed_from(text):
    digest = hashlib.sha256((text or "lake").encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def _lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _gradient(size, top, bottom):
    """Vertical three stop gradient, built small then stretched."""
    width, height = size
    steps = min(height, 256)
    base = Image.new("RGB", (1, steps))
    pixels = base.load()
    for y in range(steps):
        t = y / max(steps - 1, 1)
        if t < 0.62:
            pixels[0, y] = _lerp(top, mid_of(top, bottom), t / 0.62)
        else:
            pixels[0, y] = _lerp(mid_of(top, bottom), bottom,
                                 (t - 0.62) / 0.38)
    return base.resize((width, height), Image.BILINEAR)


def mid_of(top, bottom):
    return _lerp(top, bottom, 0.5)


def _radial_glow(size, cx, cy, radius, color):
    """Cheap soft radial light, built at 1/6 scale then blurred and upscaled."""
    width, height = size
    scale = 6
    small = Image.new("RGB", (max(width // scale, 8), max(height // scale, 8)),
                      (0, 0, 0))
    sdraw = ImageDraw.Draw(small)
    sx, sy, sr = cx / scale, cy / scale, max(radius / scale, 1.0)
    for i in range(7, 0, -1):
        r = sr * (i / 5.0)
        fade = 1.0 - (i / 8.0)
        c = tuple(int(ch * (0.25 + 0.75 * fade)) for ch in color)
        sdraw.ellipse([sx - r, sy - r, sx + r, sy + r], fill=c)
    small = small.filter(ImageFilter.GaussianBlur(sr * 0.9))
    return small.resize((width, height), Image.BICUBIC)


def _ridge(width, height, base_y, amp, phase, freq, seed_layer):
    points = [(0, height)]
    for x in range(0, width + 1, 3):
        t = x / width
        y = (base_y
             - int(amp * math.sin(phase + freq * t * math.tau))
             - int(amp * 0.45 * math.sin(phase * 1.7 + freq * 2.3 * t * math.tau
                                         + seed_layer)))
        points.append((x, y))
    points.append((width, height))
    return points


def procedural_art(prompt, width=768, height=768):
    """Deterministic scenery built from the prompt. Always succeeds."""
    width = max(int(width), 64)
    height = max(int(height), 64)
    rng = random.Random(_seed_from(prompt))
    top, mid, bottom = _pick_theme(prompt)
    text = (prompt or "").lower()

    horizon = int(height * (0.58 + rng.random() * 0.12))
    glow_x = int(width * (0.22 + rng.random() * 0.56))
    glow_y = int(horizon * (0.34 + rng.random() * 0.38))
    glow_r = max(int(min(width, height) * (0.055 + rng.random() * 0.05)), 6)

    img = _gradient((width, height), top, bottom)

    night = any(w in text for w in ("night", "star", "space", "galaxy", "moon",
                                    "aurora"))
    glow_color = _lerp(top, (255, 255, 255), 0.85)

    if night:
        sky = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        sdraw = ImageDraw.Draw(sky)
        for _ in range(int(width * height / 4200)):
            sx = rng.randrange(width)
            sy = rng.randrange(max(int(horizon * 0.85), 2))
            dot = rng.choice((1, 1, 1, 2, 2, 3))
            sdraw.ellipse([sx, sy, sx + dot, sy + dot],
                          fill=(255, 255, 255, rng.randint(110, 255)))
        img = Image.alpha_composite(img.convert("RGBA"), sky).convert("RGB")

    img = ImageChops.screen(
        img, _radial_glow((width, height), glow_x, glow_y,
                          glow_r * 5.5, glow_color))
    draw = ImageDraw.Draw(img, "RGBA")
    draw.ellipse([glow_x - glow_r, glow_y - glow_r,
                  glow_x + glow_r, glow_y + glow_r],
                 fill=(255, 250, 226, 240))

    water = img.crop((0, horizon, width, height))
    layers = 4
    for layer in range(layers):
        depth = layer / (layers - 1)
        color = _lerp(mid, bottom, depth * 0.9)
        if night:
            color = _lerp(color, (255, 255, 255), 0.04 * (1 - depth))
        amp = int(height * (0.085 - 0.048 * depth))
        points = _ridge(width, height, horizon + int(depth * height * 0.012),
                        amp, rng.random() * math.tau,
                        1.3 + rng.random() * 2.0, layer)
        draw.polygon(points, fill=color + (255,))

    reflect = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    rdraw = ImageDraw.Draw(reflect)
    water_h = height - horizon
    if water_h > 10:
        row = max(water_h / 90.0, 2.0)
        for i in range(int(water_h / row) + 1):
            t = min(i * row / water_h, 1.0)
            y = horizon + i * row
            spread = glow_r * (0.6 + t * 3.2)
            segments = 1 + int(t * 3)
            for _ in range(segments):
                if rng.random() < 0.18:
                    continue
                seg_w = spread * (0.35 + rng.random() * 0.8)
                cx = glow_x + rng.uniform(-0.55, 0.55) * spread
                alpha = int(165 * (1.0 - t) ** 1.7
                            * (0.35 + 0.65 * rng.random())) + 10
                rdraw.line([(cx - seg_w / 2.0, y), (cx + seg_w / 2.0, y)],
                           fill=(255, 246, 220, min(alpha, 255)),
                           width=2 if t < 0.6 else 3)
        img = Image.alpha_composite(
            img.convert("RGBA"),
            reflect.filter(ImageFilter.GaussianBlur(1.6))).convert("RGB")

    haze = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ImageDraw.Draw(haze).rectangle(
        [0, horizon - int(height * 0.09), width, horizon + int(height * 0.05)],
        fill=_lerp(top, (255, 255, 255), 0.35) + (85,))
    img = Image.alpha_composite(img.convert("RGBA"),
                                haze.filter(ImageFilter.GaussianBlur(
                                    max(height // 40, 4)))).convert("RGB")

    vignette = Image.new("L", (width, height), 0)
    vdraw = ImageDraw.Draw(vignette)
    edge = int(min(width, height) * 0.18)
    vdraw.ellipse([-edge, -edge, width + edge, height + edge], fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(edge * 0.9))
    img = Image.composite(img, ImageEnhance.Brightness(img).enhance(0.72),
                          vignette)

    if any(word in text for word in ("star", "photo", "pic", "image", "wallpaper")):
        banner_h = max(30, int(height * 0.08))
        banner = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        bd = ImageDraw.Draw(banner)
        top_y = height - banner_h
        for y in range(top_y, height):
            bd.line([(0, y), (width, y)],
                    fill=(8, 10, 18, int(160 * ((y - top_y) / banner_h) ** 0.5)))
        img = Image.alpha_composite(img.convert("RGBA"), banner).convert("RGB")
        label = " ".join((prompt or "LakeAgent").split())[:64]
        font = _load_font(max(12, int(banner_h * 0.40)))
        ImageDraw.Draw(img).text(
            (int(width * 0.035), height - banner_h // 2),
            label, fill=(238, 242, 255), font=font, anchor="lm")

    return img


def _load_font(size):
    for name in ("segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


# ---------------------------------------------------------------- text helpers
def prompt_for_painter(prompt, width, height, extra_notes=""):
    return (
        "{guide}\n"
        "Draw this: {prompt}\n"
        "Canvas size: {w} x {h} pixels.\n"
        "{extra}\n"
    ).format(guide=PAINTER_GUIDE, prompt=prompt, w=width, h=height,
             extra=extra_notes).strip()


def extract_code(text):
    """Pull python code out of an agent answer."""
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text or "",
                        re.DOTALL | re.IGNORECASE)
    if blocks:
        return blocks[0]
    if "```" in (text or ""):
        chunks = (text or "").split("```")
        if len(chunks) >= 2:
            body = chunks[1]
            return body.split("\n", 1)[-1] if body.startswith("python") else body
    return None


def save_png(image, folder, name):
    if not os.path.isdir(folder):
        os.makedirs(folder)
    index = 1
    while True:
        path = os.path.join(folder, "{0}_{1:02d}.png".format(name, index))
        if not os.path.exists(path):
            break
        index += 1
    image.save(path)
    return path