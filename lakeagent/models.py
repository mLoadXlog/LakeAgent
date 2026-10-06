"""LakeAgent data models: API profiles, chats, agents."""
import time
import uuid

CHAT_KIND = "chat"
IMAGE_KIND = "image"

IMAGE_PROVIDERS = [
    "OpenAI Compatible",
    "Chat Multimodal",
    "Stability AI",
    "Automatic1111",
    "Custom",
]

TEAM_STRATEGIES = ["Sequential", "Review Loop", "Debate", "Panel"]


def new_id(prefix):
    return "{0}_{1}".format(prefix, uuid.uuid4().hex[:8])


def stamp():
    return time.strftime("%H:%M:%S")


class ApiProfile:
    """One saved API connection. Users can create as many as they want."""

    def __init__(self, id=None, name="New API", kind=CHAT_KIND,
                 base_url="", api_key="", model="", provider="OpenAI Compatible",
                 temperature=0.7, max_tokens=2048, timeout=60,
                 image_size="1024x1024", steps=30, cfg_scale=7,
                 negative_prompt=""):
        self.id = id or new_id("api")
        self.name = name
        self.kind = kind
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.provider = provider
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.image_size = image_size
        self.steps = steps
        self.cfg_scale = cfg_scale
        self.negative_prompt = negative_prompt

    def to_dict(self):
        return dict(
            id=self.id, name=self.name, kind=self.kind, base_url=self.base_url,
            api_key=self.api_key, model=self.model, provider=self.provider,
            temperature=self.temperature, max_tokens=self.max_tokens,
            timeout=self.timeout, image_size=self.image_size, steps=self.steps,
            cfg_scale=self.cfg_scale, negative_prompt=self.negative_prompt,
        )

    @classmethod
    def from_dict(cls, raw):
        if not isinstance(raw, dict):
            return cls()
        profile = cls(
            id=raw.get("id"), name=raw.get("name", "New API"),
            kind=raw.get("kind", CHAT_KIND), base_url=raw.get("base_url", ""),
            api_key=raw.get("api_key", ""), model=raw.get("model", ""),
            provider=raw.get("provider", "OpenAI Compatible"),
            temperature=raw.get("temperature", 0.7),
            max_tokens=raw.get("max_tokens", 2048),
            timeout=raw.get("timeout", 60),
            image_size=raw.get("image_size", "1024x1024"),
            steps=raw.get("steps", 30), cfg_scale=raw.get("cfg_scale", 7),
            negative_prompt=raw.get("negative_prompt", ""),
        )
        return profile

    def label(self):
        return "{0} [{1}/{2}]".format(self.name, self.kind, self.model or "no model")

    def is_ready(self):
        if not self.base_url:
            return False
        if self.kind == IMAGE_KIND and self.provider == "Automatic1111":
            return True
        return bool(self.api_key)

    def chat_url(self):
        """Auto-complete a chat completions endpoint from whatever the user typed."""
        base = (self.base_url or "").strip().rstrip("/")
        if not base:
            return ""
        if base.endswith("/chat/completions"):
            return base
        if base.endswith("/v1"):
            return base + "/chat/completions"
        return base + "/v1/chat/completions"

    def models_url(self):
        """Auto-complete a models list endpoint."""
        base = (self.base_url or "").strip().rstrip("/")
        if not base:
            return ""
        if base.endswith("/models"):
            return base
        if base.endswith("/chat/completions"):
            return base[: -len("/chat/completions")] + "/models"
        if base.endswith("/v1"):
            return base + "/models"
        return base + "/v1/models"

    def image_url(self):
        """Auto-complete an image generations endpoint."""
        base = (self.base_url or "").strip().rstrip("/")
        if not base:
            return ""
        if base.endswith("/images/generations"):
            return base
        if base.endswith("/v1"):
            return base + "/images/generations"
        return base + "/v1/images/generations"


class Chat:
    """One conversation. Many chats can live side by side."""

    def __init__(self, id=None, title="New Chat", api_id="", mode="chat",
                 messages=None, created=None, image_mode="api",
                 image_api_id="", image_prompt=""):
        self.id = id or new_id("chat")
        self.title = title
        self.api_id = api_id
        self.mode = mode                # chat | team | image
        self.messages = messages or []
        self.created = created or time.strftime("%Y-%m-%d %H:%M")
        self.image_mode = image_mode    # api | painter
        self.image_api_id = image_api_id
        self.image_prompt = image_prompt

    def to_dict(self):
        return dict(
            id=self.id, title=self.title, api_id=self.api_id, mode=self.mode,
            messages=self.messages, created=self.created,
            image_mode=self.image_mode, image_api_id=self.image_api_id,
            image_prompt=self.image_prompt,
        )

    @classmethod
    def from_dict(cls, raw):
        if not isinstance(raw, dict):
            return cls()
        return cls(
            id=raw.get("id"), title=raw.get("title", "New Chat"),
            api_id=raw.get("api_id", ""), mode=raw.get("mode", "chat"),
            messages=raw.get("messages") or [],
            created=raw.get("created"), image_mode=raw.get("image_mode", "api"),
            image_api_id=raw.get("image_api_id", ""),
            image_prompt=raw.get("image_prompt", ""),
        )

    def add(self, role, content, agent="", images=None, usage=None, meta=None):
        message = {
            "role": role,
            "content": content,
            "time": stamp(),
            "agent": agent,
            "images": images or [],
        }
        if usage:
            message["usage"] = usage
        if meta:
            message["meta"] = meta
        self.messages.append(message)
        if role == "user" and self.title in ("New Chat", "Welcome", ""):
            flat = " ".join(content.split())
            self.title = flat[:28] + ("..." if len(flat) > 28 else "")
        return message

    def push(self, message):
        """Store an already-built message dict (used by the engines)."""
        self.messages.append(message)
        return message

    def last(self, role=None, skip_empty=True):
        for message in reversed(self.messages):
            if role and message.get("role") != role:
                continue
            if skip_empty and not (message.get("content") or "").strip():
                continue
            return message
        return None


class Agent:
    """A team member. Each one has its own role prompt and its own API."""

    def __init__(self, id=None, name="Agent", role="assistant", system="",
                 api_id="", enabled=True, is_leader=False, color="#89b4fa"):
        self.id = id or new_id("agent")
        self.name = name
        self.role = role
        self.system = system
        self.api_id = api_id
        self.enabled = enabled
        self.is_leader = is_leader
        self.color = color

    def to_dict(self):
        return dict(
            id=self.id, name=self.name, role=self.role, system=self.system,
            api_id=self.api_id, enabled=self.enabled, is_leader=self.is_leader,
            color=self.color,
        )

    @classmethod
    def from_dict(cls, raw):
        if not isinstance(raw, dict):
            return cls()
        return cls(
            id=raw.get("id"), name=raw.get("name", "Agent"),
            role=raw.get("role", "assistant"), system=raw.get("system", ""),
            api_id=raw.get("api_id", ""), enabled=raw.get("enabled", True),
            is_leader=raw.get("is_leader", False),
            color=raw.get("color", "#89b4fa"),
        )