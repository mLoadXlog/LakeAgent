"""Image generation with two switchable modes.

  api     -> send the prompt to an image API profile
  painter -> a text agent writes a Pillow script, we run it and render
  (if the painter fails, a local procedural scene is drawn from the prompt)
"""
import os
import time

from ..clients.image import ImageClient, ImageError, save_image
from ..clients.llm import LLMClient, LLMError, usage_total
from ..config import OUTPUT_DIR
from . import tools
from .team import SYSTEM_GUARD

MODE_API = "api"
MODE_PAINTER = "painter"

MODE_LABELS = {
    MODE_API: "Image API",
    MODE_PAINTER: "Text Agent + Python",
}

DEFAULT_SIZES = ["512x512", "768x768", "1024x1024", "1024x576", "576x1024"]


def _name(prompt):
    flat = "".join(ch if ch.isalnum() else "_" for ch in (prompt or "lake"))
    flat = "_".join(part for part in flat.split("_") if part)[:32]
    return flat or "lake"


def _writer_profile(store, chat, image_api):
    """Prefer the image profile's own chat settings, else any chat API."""
    if image_api is not None and image_api.api_key and image_api.base_url:
        return image_api
    if chat is not None:
        profile = store.api_by_id(chat.api_id)
        if profile is not None and profile.is_ready():
            return profile
    for profile in store.chat_apis():
        if profile.is_ready():
            return profile
    return None


def run_image(store, chat, profile, mode, prompt, size="768x768"):
    """Generator. Yields status | message | image | error | done."""
    started = time.time()
    if not (prompt or "").strip():
        yield ("error", "Prompt is empty.")
        yield ("done", {"ok": False})
        return

    if mode == MODE_PAINTER:
        for event in _run_painter(store, chat, profile, prompt, size, started):
            yield event
        return
    for event in _run_api(store, chat, profile, prompt, size, started):
        yield event


def _finish(store, chat, image, prompt, mode, label, started, usage=None):
    path = ""
    if store.settings.get("save_images", True):
        path = save_image(image, OUTPUT_DIR, _name(prompt))
    yield ("image", {"path": path, "mode": mode, "label": label,
                     "prompt": prompt})
    yield ("message", chat.push({
        "role": "assistant",
        "content": "{0} ready for: {1}".format(label, prompt.strip()),
        "agent": "Image Studio",
        "color": "#f5c2e7",
        "time": time.strftime("%H:%M:%S"),
        "images": [path] if path else [],
        "meta": {"elapsed": round(time.time() - started, 2)},
    }))
    done = {"ok": True, "elapsed": round(time.time() - started, 2),
            "path": path, "mode": mode}
    if usage:
        done["tokens"] = usage_total(usage)
    yield ("done", done)


def _run_api(store, chat, profile, prompt, size, started):
    if profile is None:
        yield ("error", "Pick an image API in the APIs tab (kind = image).")
        yield ("done", {"ok": False})
        return
    if profile.kind != "image":
        yield ("error", "'{0}' is a chat API. Set its kind to image or add a "
                        "new image API.".format(profile.name))
        yield ("done", {"ok": False})
        return
    if not profile.is_ready():
        yield ("error", "API '{0}' is missing key or URL.".format(profile.name))
        yield ("done", {"ok": False})
        return

    yield ("status", "Calling {0} ({1})...".format(profile.name,
                                                   profile.model or "auto"))
    previous = profile.image_size
    profile.image_size = size
    try:
        image = ImageClient(profile).generate(prompt)
    except (ImageError, Exception) as exc:  # noqa: BLE001
        profile.image_size = previous
        hint = ""
        if not profile.api_key and profile.provider == "Automatic1111":
            hint = " Automatic1111 usually needs no key."
        yield ("error", "{0}{1}".format(exc, hint))
        yield ("done", {"ok": False, "elapsed": round(time.time() - started, 2)})
        return
    profile.image_size = previous
    for event in _finish(store, chat, image, prompt, MODE_API, "Image API", started):
        yield event


def _run_painter(store, chat, image_api, prompt, size, started):
    writer = _writer_profile(store, chat, image_api)
    if writer is None:
        yield ("error", "No text API available to write the drawing code.")
        yield ("done", {"ok": False})
        return

    try:
        width, height = [int(x) for x in str(size).lower().split("x")]
    except Exception:
        width, height = 768, 768

    yield ("status", "Text agent is writing the drawing code...")

    if not store.settings.get("allow_code_exec", False):
        image = tools.procedural_art(prompt, width, height)
        for event in _finish(store, chat, image, prompt, MODE_PAINTER,
                             "Local procedural scene", started):
            yield event
        yield ("status", "Tip: turn on Settings > Allow Python drawing code to "
                         "let the agent write the scene itself.")
        return

    instruction = tools.prompt_for_painter(prompt, width, height)
    system = ("You are a Python graphics artist. You output one Pillow script "
              "and nothing else." + SYSTEM_GUARD)
    try:
        code_text, usage = LLMClient(writer).complete(
            [{"role": "system", "content": system},
             {"role": "user", "content": instruction}])
    except (LLMError, Exception) as exc:  # noqa: BLE001
        yield ("error", "Text agent failed: {0}".format(exc))
        image = tools.procedural_art(prompt, width, height)
        for event in _finish(store, chat, image, prompt, MODE_PAINTER,
                             "Local procedural scene (fallback)", started):
            yield event
        return

    code = tools.extract_code(code_text)
    if not code:
        yield ("status", "Agent sent no code block, using local scene...")
        image = tools.procedural_art(prompt, width, height)
        for event in _finish(store, chat, image, prompt, MODE_PAINTER,
                             "Local procedural scene", started):
            yield event
        return

    yield ("status", "Running the drawing code...")
    try:
        image = tools.run_painter(code, width, height)
        label = "Text agent + Python"
        usage_note = usage
    except tools.ToolError as exc:
        yield ("status", "Code failed ({0}). Using local scene instead."
                         .format(str(exc).splitlines()[0]))
        image = tools.procedural_art(prompt, width, height)
        label = "Local procedural scene (after code error)"
        usage_note = usage

    for event in _finish(store, chat, image, prompt, MODE_PAINTER, label, started,
                         usage_note):
        yield event


def clear_output():
    """Remove saved images (used by the gallery's Clear button)."""
    if not os.path.isdir(OUTPUT_DIR):
        return 0
    removed = 0
    for name in os.listdir(OUTPUT_DIR):
        if name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            try:
                os.remove(os.path.join(OUTPUT_DIR, name))
                removed += 1
            except OSError:
                pass
    return removed