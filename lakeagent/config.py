"""Persistent JSON store for LakeAgent (no database, one file, easy to backup)."""
import json
import os
import sys
import tempfile
import time

from .models import Agent, ApiProfile, Chat, new_id

APP_NAME = "LakeAgent"
DATA_FOLDER = "lakeagent_data"

# Problems seen while finding or writing the data folder. main.py shows these
# so a read-only install is never silent.
PROBLEMS = []


def _frozen():
    return bool(getattr(sys, "frozen", False))


def source_dir():
    """Where the .py files live (dev) or where the code was extracted (frozen).

    For a PyInstaller onefile build __file__ points inside a temporary
    _MEIxxxx folder that is deleted on exit, so data must never go there.
    """
    if _frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _writable(path):
    """True when `path` exists (or can be created) and accepts a file."""
    try:
        if not os.path.isdir(path):
            os.makedirs(path)
        probe = os.path.join(path, ".lakeagent_write_test")
        with open(probe, "w") as handle:
            handle.write("ok")
        os.remove(probe)
        return True
    except OSError as exc:
        PROBLEMS.append("{0} is not writable: {1}".format(path, exc))
        return False


def data_dir_candidates():
    """Places to try, best first."""
    candidates = []
    override = os.environ.get("LAKEAGENT_HOME", "").strip()
    if override:
        candidates.append(os.path.abspath(override))
    # beside the exe, so a portable copy keeps its chats when moved
    candidates.append(os.path.join(source_dir(), DATA_FOLDER))
    appdata = os.environ.get("APPDATA") or ""
    if appdata:
        candidates.append(os.path.join(appdata, APP_NAME))
    home = os.path.expanduser("~")
    if home:
        candidates.append(os.path.join(home, "." + APP_NAME.lower()))
    candidates.append(os.path.join(tempfile.gettempdir(), APP_NAME))
    return candidates


def resolve_data_dir():
    """First candidate we can actually write to."""
    tried = []
    for candidate in data_dir_candidates():
        tried.append(candidate)
        if _writable(candidate):
            if candidate != tried[0] and not os.environ.get("LAKEAGENT_HOME"):
                PROBLEMS.append("data folder: {0}".format(candidate))
            return candidate
    fallback = os.path.join(tempfile.gettempdir(), APP_NAME)
    PROBLEMS.append("could not create a data folder, using {0}".format(
        fallback))
    return fallback


DATA_DIR = resolve_data_dir()
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")
OUTPUT_DIR = os.path.join(DATA_DIR, "output")
LOG_FILE = os.path.join(DATA_DIR, "error.log")
IS_PORTABLE = os.path.normcase(DATA_DIR).startswith(
    os.path.normcase(source_dir()))

DEFAULT_SETTINGS = {
    "theme": "dark",
    "theme_id": "mocha",
    "font_family": "Segoe UI",
    "font_size": 10,
    "user_themes": [],
    "wallpapers": {},
    "setup_done": False,
    "stream": True,
    "allow_code_exec": False,
    "team_strategy": "Sequential",
    "max_rounds": 2,
    "save_images": True,
    "workdir": "",
}

DEFAULT_AGENTS = [
    ("Planner", "planner",
     "You are the planner. Break the task into clear, ordered steps. "
     "Be concrete and brief.", "#89b4fa"),
    ("Coder", "coder",
     "You are the coder. Write correct, runnable Python. "
     "Explain only briefly after the code.", "#a6e3a1"),
    ("Reviewer", "reviewer",
     "You are the reviewer. Find bugs, edge cases and unclear steps. "
     "Be specific and concise.", "#f9e2af"),
]


def log_problem(text):
    """Record a problem in memory and append it to error.log."""
    PROBLEMS.append(text)
    line = "{0}  {1}".format(time.strftime("%Y-%m-%d %H:%M:%S"), text)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except OSError:
        pass
    if sys.stdout is not None:
        try:
            print(line)
        except Exception:  # noqa: BLE001  (windowed build: no console)
            pass


def ensure_dirs():
    """Create the data folders, reporting anything that goes wrong."""
    for path in (DATA_DIR, OUTPUT_DIR):
        try:
            if not os.path.isdir(path):
                os.makedirs(path)
        except OSError as exc:
            log_problem("cannot create {0}: {1}".format(path, exc))


def data_dir_summary():
    return ("{0}\n{1}".format(DATA_DIR, "portable" if IS_PORTABLE
                               else "installed"))


# create the folders as soon as the app starts, so the user can see them
ensure_dirs()


class Store:
    """Loads and saves apis / chats / agents / settings."""

    def __init__(self, path=CONFIG_FILE):
        ensure_dirs()
        self.path = path
        self.settings = dict(DEFAULT_SETTINGS)
        self.apis = []
        self.chats = []
        self.agents = []
        self._active_chat_id = ""
        self.load()

    # ---------- persistence ----------
    def _park_broken(self):
        """Keep an unreadable config instead of overwriting it."""
        stamp = time.strftime("%Y%m%d-%H%M%S")
        target = "{0}.broken-{1}".format(self.path, stamp)
        counter = 2
        while os.path.exists(target):
            target = "{0}.broken-{1}-{2}".format(self.path, stamp, counter)
            counter += 1
        try:
            os.replace(self.path, target)
            return os.path.basename(target)
        except OSError:
            return None

    def load(self):
        raw = {}
        if os.path.exists(self.path):
            try:
                # utf-8-sig also accepts a plain utf-8 file, and tolerates the
                # byte order mark that Notepad / PowerShell like to add
                with open(self.path, "r", encoding="utf-8-sig") as handle:
                    raw = json.load(handle)
            except ValueError:
                broken = self._park_broken()
                log_problem("config.json was not valid json{0}".format(
                    ", moved to " + broken if broken else ""))
                raw = {}
            except OSError as exc:
                log_problem("cannot read config.json: {0}".format(exc))
                raw = {}

        settings = raw.get("settings") or {}
        for key, value in DEFAULT_SETTINGS.items():
            self.settings[key] = settings.get(key, value)

        self.apis = [ApiProfile.from_dict(x) for x in raw.get("apis", [])]
        self.chats = [Chat.from_dict(x) for x in raw.get("chats", [])]
        self.agents = [Agent.from_dict(x) for x in raw.get("agents", [])]
        self._active_chat_id = raw.get("active_chat_id", "")

        if not self.agents:
            self.reset_agents()
        if not self.chats:
            self.chats = [Chat(title="Welcome")]
            self._active_chat_id = self.chats[0].id
        if self._active_chat_id not in [c.id for c in self.chats]:
            self._active_chat_id = self.chats[0].id

    def save(self):
        """Write config.json. Returns True on success."""
        ensure_dirs()
        data = {
            "settings": self.settings,
            "active_chat_id": self._active_chat_id,
            "apis": [a.to_dict() for a in self.apis],
            "chats": [c.to_dict() for c in self.chats],
            "agents": [a.to_dict() for a in self.agents],
            "version": 1,
        }
        tmp = self.path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, ensure_ascii=False)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
            return True
        except (OSError, TypeError, ValueError) as exc:
            log_problem("cannot save {0}: {1}".format(
                os.path.basename(self.path), exc))
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            return False

    @property
    def folder(self):
        return os.path.dirname(os.path.abspath(self.path))

    # ---------- apis ----------
    def api_by_id(self, api_id):
        for profile in self.apis:
            if profile.id == api_id:
                return profile
        return None

    def chat_apis(self):
        return [a for a in self.apis if a.kind == "chat"]

    def image_apis(self):
        return [a for a in self.apis if a.kind == "image"]

    def add_api(self, profile):
        self.apis.append(profile)
        return profile

    def remove_api(self, api_id):
        self.apis = [a for a in self.apis if a.id != api_id]
        for chat in self.chats:
            if chat.api_id == api_id:
                chat.api_id = ""
            if chat.image_api_id == api_id:
                chat.image_api_id = ""
        for agent in self.agents:
            if agent.api_id == api_id:
                agent.api_id = ""

    # ---------- chats ----------
    def chat_by_id(self, chat_id):
        for chat in self.chats:
            if chat.id == chat_id:
                return chat
        return None

    def add_chat(self, title="New Chat"):
        chat = Chat(title=title)
        self.chats.insert(0, chat)
        self._active_chat_id = chat.id
        return chat

    def remove_chat(self, chat_id):
        if len(self.chats) <= 1:
            return False
        self.chats = [c for c in self.chats if c.id != chat_id]
        if self._active_chat_id == chat_id:
            self._active_chat_id = self.chats[0].id
        return True

    @property
    def active_chat(self):
        chat = self.chat_by_id(self._active_chat_id)
        if chat is None:
            chat = self.chats[0]
            self._active_chat_id = chat.id
        return chat

    def set_active_chat(self, chat_id):
        self._active_chat_id = chat_id

    # ---------- agents ----------
    def reset_agents(self):
        self.agents = []
        for name, role, system, color in DEFAULT_AGENTS:
            self.agents.append(Agent(name=name, role=role, system=system,
                                     color=color))
        if self.agents:
            self.agents[-1].is_leader = True

    def enabled_agents(self):
        return [a for a in self.agents if a.enabled]

    def agent_by_id(self, agent_id):
        for agent in self.agents:
            if agent.id == agent_id:
                return agent
        return None

    def leader(self):
        for agent in self.enabled_agents():
            if agent.is_leader:
                return agent
        enabled = self.enabled_agents()
        return enabled[-1] if enabled else None

    def new_id(self, prefix):
        return new_id(prefix)