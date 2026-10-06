"""Image generation via API. Several provider shapes are supported."""
import base64
import io
import json
import re

import requests
from PIL import Image

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LakeAgent/1.0"
DATA_URL_RE = re.compile(r"data:image/[^;]+;base64,([A-Za-z0-9+/=\s]+)")
IMAGE_URL_RE = re.compile(r"https?://[^\s\)\]\}\"']+\.(?:png|jpe?g|gif|webp|bmp)",
                          re.IGNORECASE)
MARKDOWN_URL_RE = re.compile(r"!\[[^\]]*\]\((https?://[^)]+)\)")
ANY_URL_RE = re.compile(r"(https?://[^\s\)\]\}\"']+)")


class ImageError(Exception):
    pass


def _headers(api_key):
    headers = {"User-Agent": DEFAULT_UA}
    if api_key:
        headers["Authorization"] = "Bearer {0}".format(api_key)
    return headers


def _to_image(source, timeout=120):
    """Turn a url / base64 blob / bytes into a PIL image."""
    if isinstance(source, Image.Image):
        return source.convert("RGB")
    if isinstance(source, (bytes, bytearray)):
        return Image.open(io.BytesIO(source)).convert("RGB")

    source = str(source).strip()
    if not source:
        raise ImageError("Empty image source")

    if source.startswith("data:image"):
        match = DATA_URL_RE.search(source)
        if not match:
            raise ImageError("Bad data url")
        return Image.open(io.BytesIO(base64.b64decode(match.group(1)))).convert("RGB")

    if source.startswith("iVBOR") or source.startswith("/9j/") or source.startswith("R0lGOD"):
        return Image.open(io.BytesIO(base64.b64decode(source))).convert("RGB")

    response = requests.get(source, headers=_headers(None), timeout=timeout)
    response.raise_for_status()
    return Image.open(io.BytesIO(response.content)).convert("RGB")


def _size_pair(size):
    try:
        width, height = [int(x) for x in str(size).lower().split("x")]
        return max(width, 64), max(height, 64)
    except Exception:
        return 1024, 1024


class ImageClient:
    """Generates one image using one API profile."""

    def __init__(self, profile):
        self.profile = profile

    def generate(self, prompt):
        provider = self.profile.provider or "OpenAI Compatible"
        method = {
            "OpenAI Compatible": self._openai,
            "Chat Multimodal": self._multimodal,
            "Stability AI": self._stability,
            "Automatic1111": self._automatic1111,
            "Custom": self._custom,
        }.get(provider, self._openai)
        return method(prompt)

    # ---------- providers ----------
    def _openai(self, prompt):
        url = self.profile.image_url()
        if not url:
            raise ImageError("Base URL is empty")
        payload = {
            "model": self.profile.model or "dall-e-3",
            "prompt": prompt,
            "n": 1,
            "size": self.profile.image_size or "1024x1024",
        }
        response = requests.post(url, headers=_headers(self.profile.api_key),
                                 json=payload,
                                 timeout=self.profile.timeout or 180)
        if response.status_code != 200:
            raise ImageError("HTTP {0}: {1}".format(response.status_code,
                                                    response.text[:300]))
        data = response.json()
        items = data.get("data") or []
        if not items:
            raise ImageError("No image in response: {0}".format(
                json.dumps(data)[:300]))
        first = items[0]
        for key in ("b64_json", "image", "base64", "data"):
            if first.get(key):
                return _to_image(first[key])
        for key in ("url", "image_url"):
            if first.get(key):
                return _to_image(first[key])
        raise ImageError("Cannot read image field: {0}".format(json.dumps(first)[:200]))

    def _multimodal(self, prompt):
        """Providers that return an image inside a chat completion."""
        url = self.profile.chat_url()
        if not url:
            raise ImageError("Base URL is empty")
        full_prompt = prompt
        if self.profile.negative_prompt:
            full_prompt += "\nAvoid: {0}".format(self.profile.negative_prompt)
        payload = {
            "model": self.profile.model or "grok-imagine-image",
            "messages": [{"role": "user", "content": full_prompt}],
            "temperature": 0.7,
            "stream": False,
        }
        response = requests.post(url, headers=_headers(self.profile.api_key),
                                 json=payload,
                                 timeout=self.profile.timeout or 180)
        if response.status_code != 200:
            raise ImageError("HTTP {0}: {1}".format(response.status_code,
                                                    response.text[:300]))
        data = response.json()
        content = ""
        choices = data.get("choices") or []
        if choices:
            message = choices[0].get("message") or {}
            content = message.get("content") or ""
            if not content and isinstance(message.get("content"), list):
                for part in message["content"]:
                    if not isinstance(part, dict):
                        continue
                    if part.get("type") == "image_url":
                        url_part = part.get("image_url") or {}
                        if url_part.get("url"):
                            return _to_image(url_part["url"])
                    elif part.get("type") == "image":
                        if part.get("url") or part.get("data"):
                            return _to_image(part.get("url") or part.get("data"))

        match = DATA_URL_RE.search(content or "")
        if match:
            return _to_image(match.group(0))
        match = MARKDOWN_URL_RE.search(content or "") or IMAGE_URL_RE.search(content or "")
        if match:
            return _to_image(match.group(1 if match.re is MARKDOWN_URL_RE else 0))

        items = data.get("data") or []
        if isinstance(items, list) and items and isinstance(items[0], dict):
            for key in ("url", "b64_json", "image", "data"):
                if items[0].get(key):
                    return _to_image(items[0][key])
        for key in ("image", "url", "b64_json"):
            if data.get(key):
                return _to_image(data[key])

        match = ANY_URL_RE.search(content or "")
        if match:
            try:
                return _to_image(match.group(1))
            except Exception:
                pass
        raise ImageError("Could not find an image. Raw: {0}".format(
            (content or "")[:300]))

    def _stability(self, prompt):
        model = self.profile.model or "stable-diffusion-xl-1024-v1-0"
        url = self.profile.base_url.rstrip("/")
        if not url:
            url = "https://api.stability.ai/v1/generation/{0}/text-to-image".format(model)
        elif url.endswith("/v1"):
            url += "/generation/{0}/text-to-image".format(model)
        width, height = _size_pair(self.profile.image_size)
        payload = {
            "text_prompts": [
                {"text": prompt, "weight": 1},
                {"text": self.profile.negative_prompt, "weight": -1},
            ],
            "cfg_scale": self.profile.cfg_scale,
            "width": width,
            "height": height,
            "steps": self.profile.steps,
            "samples": 1,
        }
        headers = _headers(self.profile.api_key)
        headers["Accept"] = "application/json"
        response = requests.post(url, headers=headers, json=payload,
                                 timeout=self.profile.timeout or 180)
        if response.status_code != 200:
            raise ImageError("HTTP {0}: {1}".format(response.status_code,
                                                    response.text[:300]))
        data = response.json()
        artifacts = data.get("artifacts") or []
        for artifact in artifacts:
            if artifact.get("base64"):
                return _to_image(base64.b64decode(artifact["base64"]))
        raise ImageError("No artifact base64 in response")

    def _automatic1111(self, prompt):
        base = (self.profile.base_url or "http://localhost:7860").rstrip("/")
        url = base if base.endswith("/txt2img") else base + "/sdapi/v1/txt2img"
        width, height = _size_pair(self.profile.image_size)
        payload = {
            "prompt": prompt,
            "negative_prompt": self.profile.negative_prompt,
            "width": width,
            "height": height,
            "steps": self.profile.steps,
            "cfg_scale": self.profile.cfg_scale,
        }
        if self.profile.model:
            payload["override_settings"] = {"sd_model_checkpoint": self.profile.model}
        response = requests.post(url, headers=_headers(None), json=payload,
                                 timeout=self.profile.timeout or 300)
        if response.status_code != 200:
            raise ImageError("HTTP {0}: {1}".format(response.status_code,
                                                    response.text[:300]))
        data = response.json()
        images = data.get("images") or []
        if not images:
            raise ImageError("No image returned by Automatic1111")
        return _to_image(base64.b64decode(images[0]))

    def _custom(self, prompt):
        url = self.profile.image_url() or self.profile.base_url
        if not url:
            raise ImageError("Base URL is empty")
        width, height = _size_pair(self.profile.image_size)
        payload = {
            "prompt": prompt,
            "negative_prompt": self.profile.negative_prompt,
            "width": width,
            "height": height,
            "steps": self.profile.steps,
            "cfg_scale": self.profile.cfg_scale,
            "model": self.profile.model,
        }
        response = requests.post(url, headers=_headers(self.profile.api_key),
                                 json=payload,
                                 timeout=self.profile.timeout or 180)
        if response.status_code != 200:
            raise ImageError("HTTP {0}: {1}".format(response.status_code,
                                                    response.text[:300]))
        content_type = response.headers.get("Content-Type", "")
        if content_type.startswith("image/"):
            return _to_image(response.content)
        data = response.json()
        for key in ("image", "images", "b64_json", "url", "output"):
            if not data.get(key):
                continue
            value = data[key]
            if isinstance(value, list):
                value = value[0] if value else None
                if not value:
                    continue
            if isinstance(value, dict):
                value = value.get("url") or value.get("b64_json")
            if value:
                return _to_image(value)
        raise ImageError("Cannot parse response: {0}".format(json.dumps(data)[:300]))


def save_image(image, folder, name):
    """Save a PIL image into folder. Returns the path."""
    import os
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