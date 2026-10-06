"""Palette + stylesheet.

`use(theme)` copies a Theme's colours into module level names so the rest of
the UI can just say theme.ACCENT, then `stylesheet()` builds the Qt style.
"""
from PyQt5 import QtGui

from .themes import COLOR_KEYS, MOCHA

BG = MOCHA.get("bg")
BG_DEEP = MOCHA.get("bg_deep")
CARD = MOCHA.get("card")
CARD_HI = MOCHA.get("card_hi")
FG = MOCHA.get("fg")
FG_DIM = MOCHA.get("fg_dim")
MUTED = MOCHA.get("muted")
ACCENT = MOCHA.get("accent")
GREEN = MOCHA.get("green")
YELLOW = MOCHA.get("yellow")
RED = MOCHA.get("red")
PINK = MOCHA.get("pink")
BORDER = MOCHA.get("border")

USER_BUBBLE = MOCHA.get("card_hi")
AGENT_BUBBLE = MOCHA.get("card")
BUBBLE_EDGE = MOCHA.get("border")

CODE_BG = MOCHA.get("bg_deep")
CODE_TAG = MOCHA.get("muted")

TRANSPARENT = "background:transparent; border:none;"
MONO = "Consolas"


def use(theme):
    """Make `theme` the live palette."""
    global BG, BG_DEEP, CARD, CARD_HI, FG, FG_DIM, MUTED
    global ACCENT, GREEN, YELLOW, RED, PINK, BORDER
    global USER_BUBBLE, AGENT_BUBBLE, BUBBLE_EDGE, CODE_BG, CODE_TAG

    values = {key: theme.get(key) for key in COLOR_KEYS}
    BG = values["bg"]
    BG_DEEP = values["bg_deep"]
    CARD = values["card"]
    CARD_HI = values["card_hi"]
    FG = values["fg"]
    FG_DIM = values["fg_dim"]
    MUTED = values["muted"]
    ACCENT = values["accent"]
    GREEN = values["green"]
    YELLOW = values["yellow"]
    RED = values["red"]
    PINK = values["pink"]
    BORDER = values["border"]

    USER_BUBBLE = values["card_hi"]
    AGENT_BUBBLE = values["card"]
    BUBBLE_EDGE = values["border"]
    CODE_BG = values["bg_deep"]
    CODE_TAG = values["muted"]
    return values


def qcolor(key_or_hex, alpha=255):
    value = key_or_hex
    if key_or_hex in COLOR_KEYS:
        value = locals_map()[key_or_hex]
    colour = QtGui.QColor(value)
    if alpha != 255:
        colour.setAlpha(alpha)
    return colour


def locals_map():
    return {"bg": BG, "bg_deep": BG_DEEP, "card": CARD, "card_hi": CARD_HI,
            "fg": FG, "fg_dim": FG_DIM, "muted": MUTED, "accent": ACCENT,
            "green": GREEN, "yellow": YELLOW, "red": RED, "pink": PINK,
            "border": BORDER}


def stylesheet(font_size=10, font_family="Segoe UI"):
    return """
QWidget {{
    background: {bg};
    color: {fg};
    font-family: "{font}", "Microsoft YaHei UI", sans-serif;
    font-size: {fs}pt;
}}
QToolTip {{
    background: {card_hi};
    color: {fg};
    border: 1px solid {border};
    padding: 4px;
}}

/* ---------- sidebar / bars ---------- */
QFrame#Sidebar {{ background: {card}; border-right: 1px solid {border}; }}
QFrame#Topbar {{ background: {card}; border-bottom: 1px solid {border}; }}
QFrame#StudioPanel {{
    background: {card}; border: 1px solid {border}; border-radius: 10px;
}}
QLabel#AppTitle {{ font-size: {big}pt; font-weight: 700; color: {accent}; }}
QLabel#AppSub {{ color: {muted}; font-size: {small}pt; }}

/* ---------- buttons ---------- */
QPushButton {{
    background: {card_hi};
    color: {fg};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 5px 12px;
}}
QPushButton:hover {{ background: {border}; }}
QPushButton:disabled {{ color: {muted}; background: {card}; }}
QPushButton#Primary {{
    background: {accent}; color: {bg_deep};
    border: 1px solid {accent}; font-weight: 600;
}}
QPushButton#Primary:hover {{ background: {fg_dim}; }}
QPushButton#Primary:disabled {{
    background: {card_hi}; color: {muted}; border-color: {border};
}}
QPushButton#Danger:hover {{ background: {red}; color: {bg_deep}; }}
QPushButton#Ghost {{
    background: transparent; border: 1px solid {border}; color: {fg_dim};
    padding: 4px 10px;
}}
QPushButton#Ghost:hover {{ color: {fg}; border-color: {accent}; }}
QPushButton#Ghost:checked {{
    background: {card_hi}; color: {accent}; border-color: {accent};
}}

/* ---------- inputs ---------- */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {bg_deep};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: {accent};
    selection-color: {bg_deep};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus,
QSpinBox:focus, QComboBox:focus {{ border-color: {accent}; }}
QLineEdit:disabled, QComboBox:disabled {{ color: {muted}; }}
QComboBox::drop-down {{ border: none; width: 18px; }}
QComboBox QAbstractItemView {{
    background: {card}; border: 1px solid {border};
    selection-background-color: {accent}; selection-color: {bg_deep};
}}
QComboBox::item:selected {{ background: {accent}; color: {bg_deep}; }}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: {card_hi}; border: none; width: 17px; margin: 1px;
    border-radius: 4px;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow,
QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{ width: 0; height: 0; }}
QCheckBox, QRadioButton {{ spacing: 7px; background: transparent; }}
QCheckBox::indicator, QRadioButton::indicator {{
    width: 15px; height: 15px;
    border: 1px solid {border}; border-radius: 4px; background: {bg_deep};
}}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
    background: {accent}; border-color: {accent};
}}
QRadioButton::indicator {{ border-radius: 8px; }}

/* ---------- lists ---------- */
QListWidget, QTreeWidget, QListView {{
    background: {bg_deep};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 3px;
}}
QListWidget::item {{ padding: 7px 9px; border-radius: 6px; margin: 1px 2px; }}
QListWidget::item:hover {{ background: {card}; }}
QListWidget::item:selected {{ background: {accent}; color: {bg_deep}; }}

/* ---------- tabs ---------- */
QTabWidget::pane {{
    border: 1px solid {border}; border-radius: 8px;
    top: -1px; background: {card};
}}
QTabBar::tab {{
    background: transparent; color: {muted};
    padding: 6px 14px; margin-right: 2px;
    border-top-left-radius: 7px; border-top-right-radius: 7px;
}}
QTabBar::tab:selected {{ background: {card}; color: {accent};
                         font-weight: 600; }}
QTabBar::tab:hover {{ color: {fg}; }}

/* ---------- transcript ---------- */
QTextBrowser {{ background: transparent; border: none; padding: 4px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {border}; border-radius: 5px;
                               min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {muted}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; }}
QScrollBar::handle:horizontal {{ background: {border}; border-radius: 5px;
                                 min-width: 30px; }}

/* ---------- misc ---------- */
QGroupBox {{
    border: 1px solid {border}; border-radius: 8px;
    margin-top: 14px; padding-top: 8px; font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 10px; padding: 0 5px; color: {accent};
}}
QSplitter::handle {{ background: {border}; }}
QStatusBar {{
    background: {card}; color: {muted}; border-top: 1px solid {border};
}}
QMenu {{ background: {card}; border: 1px solid {border}; padding: 4px; }}
QMenu::item {{ padding: 5px 22px; border-radius: 4px; }}
QMenu::item:selected {{ background: {accent}; color: {bg_deep}; }}
QProgressBar {{
    background: {bg_deep}; border: 1px solid {border};
    border-radius: 5px; height: 8px; text-align: center; color: transparent;
}}
QProgressBar::chunk {{ background: {accent}; border-radius: 4px; }}
QSlider::groove:horizontal {{
    background: {bg_deep}; height: 5px; border-radius: 3px;
    border: 1px solid {border};
}}
QSlider::handle:horizontal {{
    background: {accent}; width: 13px; height: 13px;
    margin: -5px 0; border-radius: 7px;
}}
QSlider::sub-page:horizontal {{ background: {accent}; border-radius: 3px; }}
""".format(bg=BG, bg_deep=BG_DEEP, card=CARD, card_hi=CARD_HI, fg=FG,
           fg_dim=FG_DIM, muted=MUTED, accent=ACCENT, green=GREEN, red=RED,
           yellow=YELLOW, border=BORDER, font=font_family, fs=font_size,
           big=font_size + 5, small=max(font_size - 1, 7))


def body_css():
    return "body {{ color:{0}; }}".format(FG)


# ---------------------------------------------------------------- transcript
# Qt's rich text engine only understands a small CSS subset (no flexbox, no
# border-radius), so bubbles are built out of tables: a table cell gives us the
# background and the 1px border.
SPACER = "&nbsp;"


def _meta_row(text):
    if not text:
        return ""
    return ('<p align="left" style="margin-top:2px; margin-bottom:0;">'
            '<span style="font-size:8pt; color:{0};">{1}</span></p>'
            .format(MUTED, text))


def bubble_html(role, agent, content_html, time_text, meta_text, color,
                images_html):
    if role == "user":
        name = "You"
        accent = ACCENT
        background = USER_BUBBLE
        spacer_left, align = SPACER, "right"
    else:
        name = agent or "Assistant"
        accent = color or ACCENT
        background = AGENT_BUBBLE
        spacer_left, align = "", "left"

    heading = ('<p style="margin:0 0 3px 0;">'
               '<span style="font-size:9pt; font-weight:700; color:{0};">{1}'
               '</span>'
               '<span style="font-size:8pt; color:{2};">  {3}</span></p>'
               ).format(accent, name, MUTED, time_text or "")

    return (
        '<table width="100%" cellspacing="0" cellpadding="8" '
        'style="margin-bottom:4px;">'
        '<tr>'
        '<td width="12%" style="border:none;">{spacer}</td>'
        '<td width="88%" align="{align}" bgcolor="{bg}" '
        'style="border:1px solid {edge};">'
        '{heading}{body}{images}{meta}'
        '</td>'
        '</tr></table>'
    ).format(spacer=spacer_left, align=align, bg=background, edge=BUBBLE_EDGE,
             heading=heading, body=content_html, images=images_html,
             meta=_meta_row(meta_text))


def notice_html(text, kind="info"):
    colors = {"info": ACCENT, "warn": YELLOW, "error": RED, "ok": GREEN}
    colour = colors.get(kind, ACCENT)
    return (
        '<table width="100%" cellspacing="0" cellpadding="6" '
        'style="margin-bottom:4px;"><tr>'
        '<td align="center" bgcolor="{card}" style="border:1px solid {edge};">'
        '<span style="font-size:9pt; color:{c};">{t}</span>'
        '</td></tr></table>'
    ).format(card=CARD, edge=BUBBLE_EDGE, c=colour, t=text)