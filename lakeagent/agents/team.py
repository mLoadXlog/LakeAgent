"""Multi-agent engine.

Every runner is a generator that yields (event, payload) tuples, so the UI can
run them in a worker thread without knowing anything about the logic.

Events: status | delta | message | error | done
"""
import concurrent.futures
import queue
import threading
import time

from ..clients.llm import LLMClient, LLMError, usage_total
from ..models import Agent

SYSTEM_GUARD = (
    "\n\nAnswer directly. Use markdown. If you need to show code, use one "
    "```python block. Keep the prose under 40 lines."
)

STRATEGY_HINT = (
    "Several specialists already answered. Merge the best parts into one "
    "clear final answer and drop the rest."
)


# ---------------------------------------------------------------- helpers
def _profile_for(store, agent, chat):
    profile = store.api_by_id(agent.api_id) if agent.api_id else None
    if profile is None or profile.kind != "chat":
        profile = store.api_by_id(chat.api_id)
    if profile is None:
        candidates = store.chat_apis()
        profile = candidates[0] if candidates else None
    return profile


def _ask(profile, system, user_text):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user_text})
    return LLMClient(profile).complete(messages)


def _ask_streaming(profile, system, user_text, pump):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": user_text})
    return LLMClient(profile).stream(messages, pump)


def _msg(agent, content, usage=None, meta=None):
    payload = {
        "role": "assistant",
        "content": content,
        "agent": agent.name,
        "color": agent.color,
        "time": time.strftime("%H:%M:%S"),
    }
    if usage:
        payload["usage"] = usage
    if meta:
        payload["meta"] = meta
    return payload


def _solo_agent(store):
    leader = store.leader()
    if leader is not None:
        return leader
    return Agent(name="Assistant", color="#cdd6f4")


def _chain(transcripts):
    return "\n\n".join("### {0}\n{1}".format(name, text)
                       for name, text in transcripts)


def _banner(agent, step, total):
    return "Step {0}/{1} - {2} is working...".format(step, total, agent.name)


# ---------------------------------------------------------------- single chat
def run_chat(store, chat, prompt, stream=True):
    """One agent, one API, full context. The simple path."""
    agent = _solo_agent(store)
    profile = _profile_for(store, agent, chat)
    if profile is None or not profile.is_ready():
        yield ("error", "No usable chat API. Add one in the APIs tab.")
        yield ("done", {"ok": False})
        return

    chat.add("user", prompt)
    yield ("message", dict(chat.messages[-1]))

    system = "You are a helpful assistant." + SYSTEM_GUARD
    started = time.time()
    use_stream = bool(stream and store.settings.get("stream", True))

    result = {}
    pipe = queue.Queue()

    def pump(text):
        pipe.put(("delta", text))

    def worker():
        try:
            if use_stream:
                result["value"] = _ask_streaming(profile, system, prompt, pump)
            else:
                result["value"] = _ask(profile, system, prompt)
        except Exception as exc:  # noqa: BLE001
            result["error"] = exc
        finally:
            pipe.put(("stop", None))

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    while True:
        kind, text = pipe.get()
        if kind == "stop":
            break
        yield ("delta", {"agent": agent.name, "text": text})

    if "error" in result:
        yield ("error", str(result["error"]))
        yield ("done", {"ok": False, "elapsed": round(time.time() - started, 2)})
        return

    text, usage = result["value"]
    yield ("message", chat.push(_msg(agent, text, usage,
                                     {"elapsed": round(time.time() - started, 2),
                                      "model": profile.model})))
    yield ("done", {"ok": True, "elapsed": round(time.time() - started, 2),
                    "tokens": usage_total(usage)})


# ---------------------------------------------------------------- team runs
def run_team(store, chat, prompt, strategy="Sequential", max_rounds=2):
    """Run several enabled agents together."""
    agents = store.enabled_agents()
    if not agents:
        yield ("error", "No enabled agents. Add one in the Agents tab.")
        yield ("done", {"ok": False})
        return

    for agent in agents:
        profile = _profile_for(store, agent, chat)
        if profile is None or not profile.is_ready():
            yield ("error", "Agent '{0}' has no working API.".format(agent.name))
            yield ("done", {"ok": False})
            return

    chat.add("user", prompt)
    yield ("message", dict(chat.messages[-1]))

    started = time.time()
    total_tokens = 0
    transcripts = []

    if strategy == "Panel":
        steps = _panel(store, chat, agents, prompt, transcripts)
    elif strategy == "Debate":
        steps = _debate(store, chat, agents, prompt, transcripts, max_rounds)
    elif strategy == "Review Loop":
        steps = _review(store, chat, agents, prompt, transcripts)
    else:
        steps = _sequential(store, chat, agents, prompt, transcripts)

    try:
        for kind, payload in steps:
            if kind == "message":
                if payload.get("usage"):
                    total_tokens += usage_total(payload["usage"])
            yield (kind, payload)
    except (LLMError, Exception) as exc:  # noqa: BLE001
        yield ("error", str(exc))
        yield ("done", {"ok": False, "elapsed": round(time.time() - started, 2)})
        return

    yield ("done", {"ok": True, "elapsed": round(time.time() - started, 2),
                    "tokens": total_tokens, "turns": len(transcripts)})


def _sequential(store, chat, agents, prompt, transcripts):
    total = len(agents)
    for index, agent in enumerate(agents, 1):
        yield ("status", _banner(agent, index, total))
        if index == 1:
            user_text = prompt
        else:
            user_text = ("Original task:\n{0}\n\nSo far:\n{1}\n\n"
                         "Take over and continue. Do not repeat yourself."
                         ).format(prompt, _chain(transcripts))
        system = (agent.system or "You are a helpful assistant.") + SYSTEM_GUARD
        text, usage = _ask(_profile_for(store, agent, chat), system, user_text)
        transcripts.append((agent.name, text))
        yield ("message", chat.push(
            _msg(agent, text, usage,
                 {"step": "{0}/{1}".format(index, total)})))


def _review(store, chat, agents, prompt, transcripts):
    total = len(agents)
    drafter = agents[0]
    yield ("status", _banner(drafter, 1, total))
    draft, usage = _ask(_profile_for(store, drafter, chat),
                        (drafter.system or "") + SYSTEM_GUARD, prompt)
    transcripts.append((drafter.name, draft))
    yield ("message", chat.push(
        _msg(drafter, draft, usage,
             {"step": "1/{0} draft".format(total)})))

    notes = []
    for index, agent in enumerate(agents[1:], 2):
        yield ("status", _banner(agent, index, total))
        user_text = ("Task:\n{0}\n\nDraft:\n{1}\n\n"
                     "Find the problems, then give the fixed version."
                     ).format(prompt, draft)
        critique, usage = _ask(_profile_for(store, agent, chat),
                               (agent.system or "") + SYSTEM_GUARD, user_text)
        notes.append("### {0}\n{1}".format(agent.name, critique))
        transcripts.append((agent.name, critique))
        yield ("message", chat.push(
            _msg(agent, critique, usage,
                 {"step": "{0}/{1} review".format(index, total)})))

    leader = store.leader() or agents[-1]
    if leader.id in [a.id for a in agents[1:]]:
        return
    yield ("status", "{0} is writing the final answer...".format(leader.name))
    final, usage = _ask(_profile_for(store, leader, chat),
                        (leader.system or "") + SYSTEM_GUARD,
                        "Task:\n{0}\n\nDraft:\n{1}\n\nReview notes:\n{2}\n\n"
                        "Final answer:".format(prompt, draft, "\n\n".join(notes)))
    transcripts.append((leader.name, final))
    yield ("message", chat.push(
        _msg(leader, final, usage, {"step": "final"})))


def _debate(store, chat, agents, prompt, transcripts, max_rounds):
    rounds = max(1, int(max_rounds))
    total = len(agents) * rounds
    step = 0
    for round_index in range(rounds):
        round_notes = []
        for agent in agents:
            step += 1
            yield ("status", _banner(agent, step, total))
            if round_notes:
                peers = "\n\n".join(round_notes)
                user_text = ("Task:\n{0}\n\nOthers in this round said:\n{1}\n\n"
                             "Say where you disagree, then answer."
                             ).format(prompt, peers)
            else:
                user_text = prompt
            system = ((agent.system or "You are a helpful assistant.")
                      + SYSTEM_GUARD + "\nOther agents disagree with you; "
                        "defend or revise your view.")
            text, usage = _ask(_profile_for(store, agent, chat), system,
                               user_text)
            round_notes.append("### {0}\n{1}".format(agent.name, text))
            transcripts.append((agent.name, text))
            yield ("message", chat.push(
                _msg(agent, text, usage,
                     {"round": round_index + 1})))

    leader = store.leader() or agents[-1]
    yield ("status", "{0} is closing the debate...".format(leader.name))
    final, usage = _ask(_profile_for(store, leader, chat),
                        (leader.system or "") + SYSTEM_GUARD + "\n"
                        + STRATEGY_HINT,
                        "Task:\n{0}\n\nFull debate:\n{1}\n\nFinal answer:"
                        .format(prompt, _chain(transcripts)))
    transcripts.append((leader.name, final))
    yield ("message", chat.push(
        _msg(leader, final, usage, {"step": "verdict"})))


def _panel(store, chat, agents, prompt, transcripts):
    """Everyone answers at the same time, leader merges."""
    order = [agent.id for agent in agents]

    def work(agent):
        system = (agent.system or "You are a helpful assistant.") + SYSTEM_GUARD
        return agent, _ask(_profile_for(store, agent, chat), system, prompt)

    yield ("status", "{0} agents working in parallel...".format(len(agents)))
    results = []
    with concurrent.futures.ThreadPoolExecutor(
            max_workers=max(1, len(agents))) as pool:
        for future in [pool.submit(work, agent) for agent in agents]:
            results.append(future.result())
    results.sort(key=lambda pair: order.index(pair[0].id))

    for agent, (text, usage) in results:
        transcripts.append((agent.name, text))
        yield ("message", chat.push(
            _msg(agent, text, usage, {"parallel": True})))

    leader = store.leader() or agents[-1]
    yield ("status", "{0} is merging the answers...".format(leader.name))
    final, usage = _ask(_profile_for(store, leader, chat),
                        (leader.system or "") + SYSTEM_GUARD + "\n"
                        + STRATEGY_HINT,
                        "Task:\n{0}\n\nSpecialist answers:\n{1}\n\n"
                        "Merged final answer:".format(prompt, _chain(transcripts)))
    transcripts.append((leader.name, final))
    yield ("message", chat.push(
        _msg(leader, final, usage, {"step": "merged"})))