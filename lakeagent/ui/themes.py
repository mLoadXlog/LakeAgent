"""Themes for LakeAgent.

A theme is 13 colours + a font + an optional wallpaper. Five themes ship with
the app; the user can mix their own colours or drop a picture in as the
background (blur / overlap / dim).
"""
import colorsys
import copy

COLOR_KEYS = ("bg", "bg_deep", "card", "card_hi", "fg", "fg_dim", "muted",
              "accent", "green", "yellow", "red", "pink", "border")

COLOR_LABELS = {
    "bg": "Background",
    "bg_deep": "Input background",
    "card": "Panel",
    "card_hi": "Button / row",
    "fg": "Text",
    "fg_dim": "Dim text",
    "muted": "Faint text",
    "accent": "Accent",
    "green": "Green",
    "yellow": "Yellow",
    "red": "Red",
    "pink": "Pink",
    "border": "Border",
}

# colours the derivation needs from the user
BASE_KEYS = ("bg", "card", "fg", "accent")

BLEND_MODES = [
    ("Over", "over"),
    ("Overlap", "overlay"),
    ("Multiply", "multiply"),
    ("Screen", "screen"),
    ("Darken", "darken"),
    ("Lighten", "lighten"),
]

# hue used for each semantic colour when deriving a palette
SEMANTIC_HUES = {"green": 132, "yellow": 48, "red": 4, "pink": 330}
SEMANTIC_LIGHT = {"green": 0.03, "yellow": 0.04, "red": 0.0, "pink": 0.02}


# ---------------------------------------------------------------- colour math
def to_rgb(value):
    if isinstance(value, (tuple, list)):
        return (int(value[0]), int(value[1]), int(value[2]))
    text = str(value).strip().lstrip("#")
    if len(text) == 3:
        text = "".join(c * 2 for c in text)
    return (int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16))


def to_hex(rgb):
    red, green, blue = to_rgb(rgb)
    return "#{0:02x}{1:02x}{2:02x}".format(
        max(0, min(255, red)), max(0, min(255, green)),
        max(0, min(255, blue)))


def luminance(rgb):
    def channel(c):
        c = c / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    red, green, blue = [channel(c) for c in to_rgb(rgb)]
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def mix(first, second, amount):
    amount = max(0.0, min(1.0, amount))
    return tuple(int(a + (b - a) * amount)
                 for a, b in zip(to_rgb(first), to_rgb(second)))


def shift(rgb, lightness=0.0, saturation=1.0):
    """lightness -1..1 pushes darker/lighter, saturation scales vividness."""
    red, green, blue = [c / 255.0 for c in to_rgb(rgb)]
    hue, lum, sat = colorsys.rgb_to_hls(red, green, blue)
    lum = max(0.0, min(1.0, lum + lightness))
    sat = max(0.0, min(1.0, sat * saturation))
    return tuple(int(round(c * 255))
                 for c in colorsys.hls_to_rgb(hue, lum, sat))


def is_dark(rgb):
    return luminance(rgb) < 0.4


def derive_palette(bg, card, fg, accent):
    """Turn four picked colours into a full, coherent palette."""
    dark = is_dark(bg)
    colours = {}
    colours["bg"] = to_hex(bg)
    colours["fg"] = to_hex(fg)
    colours["accent"] = to_hex(accent)

    if dark:
        colours["bg_deep"] = to_hex(mix(bg, "#000000", 0.30))
        colours["card"] = to_hex(mix(bg, fg, 0.05))
        colours["card_hi"] = to_hex(mix(bg, fg, 0.11))
        colours["border"] = to_hex(mix(bg, fg, 0.20))
        colours["muted"] = to_hex(mix(fg, bg, 0.60))
        colours["fg_dim"] = to_hex(mix(fg, bg, 0.30))
    else:
        colours["bg_deep"] = to_hex(mix(bg, "#000000", 0.07))
        colours["card"] = to_hex(mix(bg, "#ffffff", 0.80))
        colours["card_hi"] = to_hex(mix(bg, "#ffffff", 1.0))
        colours["border"] = to_hex(mix(bg, fg, 0.22))
        colours["muted"] = to_hex(mix(fg, bg, 0.45))
        colours["fg_dim"] = to_hex(mix(fg, bg, 0.22))

    hue, lum, sat = colorsys.rgb_to_hls(
        *[c / 255.0 for c in to_rgb(accent)])
    sat = max(sat, 0.30)
    for name, base_hue in SEMANTIC_HUES.items():
        target = (base_hue / 360.0,
                  min(0.86, max(0.45, lum + SEMANTIC_LIGHT[name])),
                  sat * 0.85)
        colours[name] = to_hex(tuple(
            int(round(c * 255))
            for c in colorsys.hls_to_rgb(*target)))

    tint = 0.03 if dark else 0.015
    colours["card"] = to_hex(mix(to_hex(colours["card"]), accent, tint))
    return colours


def default_wallpaper():
    return {"path": "", "blur": 6, "opacity": 35, "blend": "over",
            "dim": 0, "zoom": 100}


class Theme:
    def __init__(self, theme_id, name, colours, font_family="Segoe UI",
                 font_size=10, wallpaper=None, built_in=False):
        self.id = theme_id
        self.name = name
        self.colors = {k: to_hex(to_rgb(colours.get(k, "#888888")))
                       for k in COLOR_KEYS}
        self.font_family = font_family
        self.font_size = int(font_size)
        self.wallpaper = dict(default_wallpaper())
        if wallpaper:
            self.wallpaper.update({k: v for k, v in wallpaper.items()
                                   if k in self.wallpaper})
        self.built_in = built_in

    def copy(self):
        return Theme(self.id, self.name, dict(self.colors),
                     self.font_family, self.font_size,
                     dict(self.wallpaper), self.built_in)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "colors": dict(self.colors),
            "font_family": self.font_family,
            "font_size": self.font_size,
            "wallpaper": dict(self.wallpaper),
        }

    @classmethod
    def from_dict(cls, raw, built_in=False):
        return cls(raw.get("id", "user"), raw.get("name", "My theme"),
                   raw.get("colors") or {}, raw.get("font_family", "Segoe UI"),
                   raw.get("font_size", 10), raw.get("wallpaper"),
                   built_in)

    def get(self, key, fallback="#888888"):
        return self.colors.get(key, fallback)

    def summary_colours(self):
        return (self.get("accent"), self.get("card"), self.get("bg"))


def _theme(theme_id, name, bg, bg_deep, card, card_hi, fg, fg_dim, muted,
           accent, green, yellow, red, pink, border, font="Segoe UI",
           size=10):
    return Theme(theme_id, name, dict(zip(COLOR_KEYS, (
        bg, bg_deep, card, card_hi, fg, fg_dim, muted, accent, green,
        yellow, red, pink, border))), font, size, built_in=True)


MOCHA = _theme(
    "mocha", "Mocha",
    "#1e1e2e", "#15151f", "#2a2a3e", "#313244", "#cdd6f4", "#a6adc8",
    "#6c7086", "#89b4fa", "#a6e3a1", "#f9e2af", "#f38ba8", "#f5c2e7",
    "#45475a", size=10)

NORD = _theme(
    "nord", "Nord",
    "#2e3440", "#272c36", "#3b4252", "#434c5e", "#eceff4", "#d8dee9",
    "#8f98a8", "#88c0d0", "#a3be8c", "#ebcb8b", "#bf616a", "#b48ead",
    "#4c566a", size=10)

DRACULA = _theme(
    "dracula", "Dracula",
    "#282a36", "#21222c", "#343746", "#44475a", "#f8f8f2", "#c8c4d6",
    "#8b93a7", "#bd93f9", "#50fa7b", "#f1fa8c", "#ff5555", "#ff79c6",
    "#4d5066", size=10)

TOKYO = _theme(
    "tokyo", "Tokyo Night",
    "#1a1b26", "#16161e", "#24283b", "#2f334d", "#c0caf5", "#a9b1d6",
    "#7a8394", "#7aa2f7", "#9ece6a", "#e0af68", "#f7768e", "#bb9af7",
    "#3b4261", size=10)

DAYLIGHT = _theme(
    "daylight", "Daylight",
    "#f4f5f7", "#e6e8ec", "#ffffff", "#eef0f4", "#24292f", "#4a5158",
    "#8b949e", "#0a66c2", "#1a7f37", "#9a6700", "#cf222e", "#a340b9",
    "#d0d7de", size=10)

BUILTIN = [MOCHA, NORD, DRACULA, TOKYO, DAYLIGHT]


class ThemeManager:
    """Holds the built-ins plus whatever the user has made."""

    def __init__(self, store):
        self.store = store

    # ---------- built in ----------
    @staticmethod
    def builtin(id_or_name=None):
        for theme in BUILTIN:
            if id_or_name in (theme.id, theme.name):
                return theme.copy()
        return MOCHA.copy()

    # ---------- user themes ----------
    def user_themes(self):
        raw = self.store.settings.get("user_themes") or []
        return [Theme.from_dict(item) for item in raw
                if isinstance(item, dict)]

    def all(self):
        return [t.copy() for t in BUILTIN] + self.user_themes()

    def find(self, theme_id):
        """Look up a theme, pulling in any wallpaper saved for it."""
        overlays = self.store.settings.get("wallpapers") or {}
        for theme in self.all():
            if theme.id == theme_id:
                if theme.built_in and theme_id in overlays:
                    theme.wallpaper.update(overlays[theme_id])
                return theme
        return None

    def current(self):
        theme_id = self.store.settings.get("theme_id", MOCHA.id)
        theme = self.find(theme_id)
        if theme is not None:
            return theme
        return MOCHA.copy()

    def select(self, theme_id):
        theme = self.find(theme_id)
        if theme is None:
            return False
        if theme.built_in:
            self.store.settings["theme_id"] = theme.id
            self.store.settings["user_themes"] = [
                t.to_dict() for t in self.user_themes()
                if t.id != theme_id]
        else:
            # remember this user's own font and wallpaper choices
            for index, item in enumerate(self.store.settings
                                         .get("user_themes") or []):
                if item.get("id") == theme_id:
                    merged = item
                    merged["font_family"] = self.store.settings.get(
                        "font_family", merged.get("font_family", "Segoe UI"))
                    merged["font_size"] = self.store.settings.get(
                        "font_size", merged.get("font_size", 10))
                    items = self.store.settings["user_themes"]
                    items[index] = merged
                    self.store.settings["user_themes"] = items
                    break
            self.store.settings["theme_id"] = theme_id
        self.store.save()
        return True

    def save_theme(self, theme):
        """Add or overwrite a user theme."""
        theme.built_in = False
        items = [t.to_dict() for t in self.user_themes()
                 if t.id != theme.id]
        if theme.id.startswith("user_"):
            items.append(theme.to_dict())
        else:
            theme.id = new_user_id(theme.name)
            items.append(theme.to_dict())
        self.store.settings["user_themes"] = items
        self.store.settings["theme_id"] = theme.id
        self.store.save()
        return theme

    def delete_theme(self, theme_id):
        theme = self.find(theme_id)
        if theme is None or theme.built_in:
            return False
        self.store.settings["user_themes"] = [
            t.to_dict() for t in self.user_themes() if t.id != theme_id]
        if self.store.settings.get("theme_id") == theme_id:
            self.store.settings["theme_id"] = MOCHA.id
        self.store.save()
        return True

    # ---------- font ----------
    def font_family(self, theme=None):
        theme = theme or self.current()
        return (self.store.settings.get("font_family")
                or theme.font_family or "Segoe UI")

    def font_size(self, theme=None):
        theme = theme or self.current()
        try:
            return int(self.store.settings.get("font_size")
                       or theme.font_size or 10)
        except (TypeError, ValueError):
            return 10

    def set_font(self, family=None, size=None):
        if family:
            self.store.settings["font_family"] = family
        if size:
            self.store.settings["font_size"] = int(size)
        self.store.save()

    @staticmethod
    def reset():
        return copy.deepcopy(MOCHA)


def new_user_id(name):
    import re
    slug = re.sub(r"[^a-z0-9]+", "_", (name or "theme").lower()).strip("_")
    return "user_{0}".format(slug or "theme")