# LakeAgent

A small multi-agent desktop desk. Python + PyQt5, no server, no database.

- **Many chats** side by side, each with its own history, API and mode
- **Many APIs** - add as many models as you like, chat or image
- **Several agents working together** on one task, four strategies
- **Pictures two ways** - call an image API, or let a text agent write Python
  that draws the picture (works even with no image API at all)

![LakeAgent](lakeagent_data/output/_screenshot_chat.png)

## Install and run

```bash
pip install -r requirements.txt
python main.py
```

Python 3.8+ and PyQt5.

## First run

A setup wizard opens the first time you start LakeAgent:

1. **Welcome** - what you are about to do.
2. **Theme** - five themes are included (Mocha, Nord, Dracula, Tokyo Night,
   Daylight). Click one to see it live. `Make my own theme` opens the editor.
3. **Font** - pick any installed typeface and a size from 8 pt to 18 pt, with
   a preview that updates as you drag.
4. **API** - add your first one, or skip and do it later.
5. **Ready** - a summary.

Skip setup at any point and change everything later in **Settings**.

To add an API by hand:

- **Name** - anything, e.g. `DeepSeek`
- **Kind** - `chat` (text) or `image` (pictures)
- **Base URL** - `https://api.example.com` or `https://api.example.com/v1`.
  LakeAgent completes the rest of the path for you
- **API Key** - your `sk-...`
- **Model** - press **Fetch** to list them, or type the name by hand

The `Resolved URL` line at the bottom of the dialog always shows exactly which
endpoint will be called.

## Themes

Five are built in, and you can make as many of your own as you like. Open
**Settings** (or the **Theme** button at the bottom of the sidebar) -> **Look**.

- **Look tab** - pick a theme, edit it, make a new one, delete your own.
- **Font tab** - typeface and size, 8 pt to 18 pt, with a live preview.
- **Background tab** - use a picture as the wallpaper.
- **Behaviour tab** - streaming, code execution, saving images.

The editor has three tabs:

**Mix colours** - pick four colours (Background, Panel, Text, Accent) and
LakeAgent derives the other nine so the theme always looks right. It detects
light and dark backgrounds and inverts the derived shades accordingly.

**Every colour** - fine tune all thirteen on their own.

**Background picture** - choose a picture and set:

| Control | What it does |
|---|---|
| Blur | 0 to 40, softens the picture |
| Strength | 0 to 100 %, how much of the picture shows |
| Dim | 0 to 100 %, darkens it further |
| Zoom | 100 to 250 %, crops in |
| Blend | `Over`, `Overlap`, `Multiply`, `Screen`, `Darken`, `Lighten` |

The picture sits behind the chat and behind the image preview. `Overlap`
multiplies it with the theme colour, which keeps text readable - a good
starting point is Blur 6, Strength 40 %, Dim 10 %, Blend `Overlap`.

Your themes and font choices are saved with the chat, so switching themes keeps
each one's own wallpaper and typeface.

## Three modes

The **Chat / Team / Image** buttons in the toolbar switch what the Send button
does. In Image mode a **Back** button at the top left returns to the chat.

### Chat

One agent answers. Answers stream in token by token. Token count and elapsed
time are shown under each reply.

### Team

Several enabled agents work on the same task. Pick a strategy:

| Strategy | What happens |
|---|---|
| `Sequential` | Agent 1 starts, then each next one takes over and improves it |
| `Review Loop` | Agent 1 drafts, the others review, the leader writes the final |
| `Debate` | Every agent answers each round and sees the others, leader decides |
| `Panel` | Everyone answers at the same time, leader merges the best parts |

Agents live in the **Team** tab. Each one has a role prompt, a colour, and its
own API. Tick the ones that should take part, and tick **Leader** on whoever
writes the final answer (the last enabled agent is used if nobody is ticked).

### Image

Two switchable modes, chosen in the **Mode** box:

**Image API** - sends the prompt straight to the selected image model.
Supported provider shapes: OpenAI-compatible `/v1/images/generations`,
Stability AI, Automatic1111, chat endpoints that reply with an image, and a
generic custom endpoint.

**Text Agent + Python** - no image API needed. A text agent writes a Pillow
script, LakeAgent runs it and shows the result. Three levels of safety:

| Setting | Result |
|---|---|
| *Let the text agent run Python code* off | LakeAgent draws the scene itself with a built-in renderer |
| on, code runs fine | You get the agent's drawing |
| on, code fails | LakeAgent falls back to its own renderer |

The built-in renderer is deterministic: it reads the prompt, picks a palette
(`sunset`, `night`, `ocean`, `forest`, `snow`, `desert`, `city`, `space`,
`aurora`, `dawn`), then draws sky, stars, layered ridges, a sun or moon with
glow, a shimmering reflection and a vignette. So you always get a real image
out of it, no API key needed.

Code runs in a restricted namespace: only `math`, `random`, `time`, `itertools`,
`functools`, `datetime`, `json`, `re` and `PIL` can be imported, and file and
process builtins are not available.

## Layout

```
lakeagent_data/
├── config.json      your APIs, chats, agents and settings
├── output/          generated images
└── error.log        written only if something goes wrong
```

The folder is created automatically on the first run. Where it goes:

| Situation | Folder |
|---|---|
| Running `python main.py` | next to `main.py` |
| Running `LakeAgent.exe` | next to the exe, so a portable copy keeps its chats when you move it |
| The exe folder cannot be written | `%APPDATA%\LakeAgent`, then `~\.lakeagent` |
| `LAKEAGENT_HOME` is set | exactly that folder |

Nothing is ever written into the folder PyInstaller extracts to, so chats
survive closing the program. Settings -> Behaviour shows the folder in use with
an **Open folder** button.

If `config.json` ever becomes unreadable it is renamed to
`config.json.broken-<date>` instead of being deleted, and the app starts with
defaults. A UTF-8 byte order mark is tolerated, so editing the file in Notepad
is safe.

Delete `config.json` to start fresh; back it up to keep your chats.

## Build a single exe

```bash
pip install pyinstaller
python build.py
```

Drop an `icon.png` or `icon.jpg` next to `main.py` first if you want an icon.
The finished exe lands in `dist/`.

## Keyboard

| Key | Action |
|---|---|
| `Enter` | Send |
| `Shift+Enter` | New line |

## Project layout

```
main.py                     entry point
build.py                    PyInstaller helper
requirements.txt
LakeAgent.spec
lakeagent/
├── config.py               JSON store: apis / chats / agents / settings
├── models.py               ApiProfile, Chat, Agent
├── markdown.py             markdown -> Qt-safe HTML
├── clients/
│   ├── llm.py              OpenAI-compatible chat, streaming, model list
│   └── image.py            image providers + saving
├── agents/
│   ├── team.py             single chat and the four team strategies
│   ├── image_job.py        the two image modes
│   └── tools.py            sandboxed python, the procedural renderer
└── ui/
    ├── main_window.py      wiring and background jobs
    ├── sidebar.py          chats / APIs / team tabs
    ├── chat_view.py        transcript and composer
    ├── image_view.py       image studio + back button
    ├── api_dialog.py       add / edit API
    ├── agent_dialog.py     add / edit agent
    ├── settings_dialog.py  look / font / background / behaviour
    ├── setup_wizard.py     first run
    ├── theme_dialogs.py    theme editor + live preview
    ├── themes.py           palettes, colour maths, theme storage
    ├── backdrop.py         wallpaper processing
    ├── theme.py            live palette + stylesheet
    └── worker.py           runs generators on a thread
```

## Notes

- Every engine function is a plain generator that yields
  `(event, payload)`, so the logic is testable without Qt.
- The transcript is built from HTML tables because Qt's rich text engine does
  not support flexbox or `border-radius`.
- Pillow 12 removed `ImageQt.ImageQt`; the UI converts images through PNG bytes
  so it works on every Pillow version.
- PyQt5 will not mix `QRect` and `QRectF` in `drawPixmap`, and an exception
  raised inside a `paintEvent` aborts the process, so `backdrop.paint` uses
  `QRectF` throughout and both custom `paintEvent`s catch and report errors
  instead of letting them escape into Qt.
- `lakeagent/config.py` resolves the data folder at import time. Under
  PyInstaller onefile, `__file__` points at the temporary `_MEIxxxx` folder
  that is deleted on exit, so `source_dir()` returns the exe's own folder when
  `sys.frozen` is set. Every candidate folder is probed by writing a real file,
  and failures are reported to `error.log` plus a dialog at startup rather than
  being swallowed.