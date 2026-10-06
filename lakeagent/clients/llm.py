"""OpenAI-compatible chat client. Works with most providers."""
import json

import requests

DEFAULT_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LakeAgent/1.0"


class LLMError(Exception):
    pass


def _headers(api_key):
    headers = {
        "Content-Type": "application/json",
        "User-Agent": DEFAULT_UA,
    }
    if api_key:
        headers["Authorization"] = "Bearer {0}".format(api_key)
    return headers


class LLMClient:
    """Talks to one API profile."""

    def __init__(self, profile):
        self.profile = profile

    # ---------- models ----------
    def list_models(self):
        url = self.profile.models_url()
        if not url:
            raise LLMError("Base URL is empty")
        response = requests.get(url, headers=_headers(self.profile.api_key),
                                timeout=self.profile.timeout or 30)
        if response.status_code != 200:
            raise LLMError("HTTP {0} from {1}".format(response.status_code, url))
        data = response.json()
        if isinstance(data, dict) and isinstance(data.get("data"), list):
            return [m.get("id") for m in data["data"] if m.get("id")]
        if isinstance(data, dict) and isinstance(data.get("models"), list):
            out = []
            for item in data["models"]:
                if isinstance(item, dict):
                    out.append(item.get("id") or item.get("name"))
                else:
                    out.append(str(item))
            return [x for x in out if x]
        raise LLMError("Unrecognised model list format")

    # ---------- completion ----------
    def complete(self, messages, temperature=None, max_tokens=None):
        """Non-streaming call. Returns (text, usage_dict)."""
        payload = self._payload(messages, temperature, max_tokens, False)
        url = self.profile.chat_url()
        response = requests.post(url, headers=_headers(self.profile.api_key),
                                 json=payload,
                                 timeout=self.profile.timeout or 120)
        if response.status_code != 200:
            raise LLMError("HTTP {0}: {1}".format(
                response.status_code, response.text[:400]))
        try:
            data = response.json()
        except ValueError:
            raise LLMError("Response was not JSON")
        text = _first_choice_text(data)
        if text is None:
            raise LLMError("No choices in response: {0}".format(
                json.dumps(data)[:300]))
        return text, data.get("usage") or {}

    def stream(self, messages, on_delta, temperature=None, max_tokens=None):
        """Streaming call. on_delta(str) is called for every chunk.

        Returns (full_text, usage_dict). Falls back to complete() if the
        provider does not support streaming.
        """
        payload = self._payload(messages, temperature, max_tokens, True)
        url = self.profile.chat_url()
        try:
            response = requests.post(url, headers=_headers(self.profile.api_key),
                                     json=payload,
                                     timeout=self.profile.timeout or 120,
                                     stream=True)
        except requests.RequestException:
            return self.complete(messages, temperature, max_tokens)

        if response.status_code != 200:
            return self.complete(messages, temperature, max_tokens)

        pieces = []
        usage = {}
        saw_delta = False
        try:
            for raw_line in response.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                line = raw_line.strip()
                if line.startswith("data:"):
                    line = line[5:].strip()
                if not line or line == "[DONE]":
                    if line == "[DONE]":
                        break
                    continue
                if not line.startswith("{"):
                    continue
                try:
                    chunk = json.loads(line)
                except ValueError:
                    continue
                if chunk.get("usage"):
                    usage = chunk["usage"]
                delta = _first_delta(chunk)
                if delta:
                    saw_delta = True
                    pieces.append(delta)
                    on_delta(delta)
        except Exception:
            pass

        if not saw_delta:
            return self.complete(messages, temperature, max_tokens)
        return "".join(pieces), usage

    # ---------- internals ----------
    def _payload(self, messages, temperature, max_tokens, stream):
        return {
            "model": self.profile.model or "gpt-4o-mini",
            "messages": messages,
            "stream": bool(stream),
            "temperature": (self.profile.temperature if temperature is None
                            else temperature),
            "max_tokens": int(self.profile.max_tokens if max_tokens is None
                              else max_tokens),
        }


def _first_choice_text(data):
    choices = data.get("choices") if isinstance(data, dict) else None
    if not choices:
        return None
    first = choices[0]
    message = first.get("message") or {}
    content = message.get("content")
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(part.get("text", ""))
        content = "".join(parts)
    if content is None:
        content = first.get("text")
    if content:
        return content
    return None


def _first_delta(chunk):
    choices = chunk.get("choices") if isinstance(chunk, dict) else None
    if not choices:
        return ""
    delta = choices[0].get("delta") or {}
    content = delta.get("content")
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content
                       if isinstance(p, dict) and p.get("type") == "text")
    return content or ""


def usage_total(usage):
    if not isinstance(usage, dict):
        return 0
    total = usage.get("total_tokens")
    if total:
        return int(total)
    prompt = int(usage.get("prompt_tokens") or 0)
    completion = int(usage.get("completion_tokens") or 0)
    return prompt + completion