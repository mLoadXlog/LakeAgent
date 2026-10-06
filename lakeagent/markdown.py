"""Tiny markdown -> HTML converter, enough for chat bubbles.

Every style is inline because Qt's rich text engine ignores <style> blocks.
Colours come from the live theme, looked up on each call.
"""
import html
import re

FENCE_RE = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
BULLET_RE = re.compile(r"^\s*[-*]\s+(.*)$")
ORDER_RE = re.compile(r"^\s*(\d+)[.)]\s+(.*)$")


def _palette():
    from .ui import theme
    return {
        "accent": theme.ACCENT,
        "muted": theme.MUTED,
        "fg": theme.FG,
        "green": theme.GREEN,
        "code_bg": theme.CODE_BG,
    }


def _code_span(colors):
    return ('<span style="background-color:{0}; color:{1};">'
            '\u00a0{{0}}\u00a0</span>').format(colors["code_bg"], colors["green"])


def _inline(text, colors):
    text = html.escape(text)

    def code(match):
        return _code_span(colors).format(match.group(1))

    def link(match):
        return '<a href="{1}" style="color:{0};">{2}</a>'.format(
            colors["accent"], html.escape(match.group(2), quote=True),
            match.group(1))

    text = INLINE_CODE_RE.sub(code, text)
    text = BOLD_RE.sub(r"<b>\1</b>", text)
    text = ITALIC_RE.sub(r"<i>\1</i>", text)
    text = LINK_RE.sub(link, text)
    return text


def _block_code(code, language, colors):
    tag = ('<p style="margin:4px 0 1px 0;"><span style="font-size:8pt; '
           'color:{0};">{1}</span></p>'.format(
               colors["muted"], html.escape(language or "text")))
    body = html.escape(code.rstrip())
    return ('{tag}<pre style="background-color:{bg}; color:{fg}; '
            'margin:0; padding:6px;">{body}</pre>').format(
                tag=tag, bg=colors["code_bg"], fg=colors["fg"], body=body)


def to_html(text, colors=None):
    """Convert a markdown-ish message body into simple HTML."""
    if not text:
        return ""
    colors = colors or _palette()

    def inline(value):
        return _inline(value, colors)

    accent = colors["accent"]

    out = []
    chunks = []
    pos = 0
    for match in FENCE_RE.finditer(text):
        chunks.append(("text", text[pos:match.start()]))
        chunks.append(("code", match.group(1), match.group(2)))
        pos = match.end()
    chunks.append(("text", text[pos:]))

    in_list = False
    for chunk in chunks:
        if chunk[0] == "code":
            if in_list:
                out.append("</ul>")
                in_list = False
            out.append(_block_code(chunk[2], chunk[1], colors))
            continue

        for raw_line in chunk[1].splitlines():
            line = raw_line.rstrip()
            heading = HEADING_RE.match(line)
            bullet = BULLET_RE.match(line)
            order = ORDER_RE.match(line)
            if heading:
                if in_list:
                    out.append("</ul>")
                    in_list = False
                level = min(len(heading.group(1)) + 2, 6)
                out.append('<h{0} style="color:{1}; margin:6px 0 2px 0;">{2}'
                           '</h{0}>'.format(level, accent,
                                            inline(heading.group(2))))
            elif bullet:
                if not in_list:
                    out.append("<ul>")
                    in_list = True
                out.append("<li>{0}</li>".format(inline(bullet.group(1))))
            elif order:
                if not in_list:
                    out.append("<ul>")
                    in_list = True
                out.append("<li>{0}</li>".format(inline(order.group(2))))
            elif not line.strip():
                if in_list:
                    out.append("</ul>")
                    in_list = False
            else:
                if in_list:
                    out.append("</ul>")
                    in_list = False
                out.append('<p style="margin:2px 0;">{0}</p>'
                           .format(inline(line)))
    if in_list:
        out.append("</ul>")
    return "".join(out)


def extract_code(text, prefer_language=None):
    """Return the first fenced code block, or None."""
    blocks = re.findall(r"```(\w*)\n(.*?)```", text or "", re.DOTALL)
    if not blocks:
        return None
    if prefer_language:
        for language, code in blocks:
            if language.lower() == prefer_language.lower():
                return code
    return blocks[0][1]


def extract_all_code(text):
    """Return [(language, code), ...] for every fenced block."""
    return [(language, code) for language, code in
            re.findall(r"```(\w*)\n(.*?)```", text or "", re.DOTALL)]


def strip_code(text):
    """Remove fenced blocks, keeping the prose."""
    return FENCE_RE.sub("", text or "").strip()