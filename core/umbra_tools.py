"""
UMBRA tool use, in Hermes 3's trained format.

The model sees its tools as JSON schemas inside <tools></tools>, calls one with
<tool_call>{"name": ..., "arguments": {...}}</tool_call>, and gets the result
back as a "tool" message wrapped in <tool_response></tool_response>.

UMBRA decides which tools to use, what to search for and where notes go.
Every call and result summary is logged to data/agent_log.jsonl.
Tools reach only env/ (see umbra_env.py), the note shelves, and the web via
the outside fetcher (see umbra_research.py). None run commands.
"""
import json, re
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List

import umbra_env as env
import umbra_research as research

ROOT = Path(__file__).resolve().parent.parent
AGENT_LOG = ROOT / "data" / "agent_log.jsonl"
SCHEDULE = ROOT / "data" / "schedule.json"
DEFAULT_SCHEDULE = {"every_minutes": 10, "last_run": None, "set_by": "default",
                    "reason": "a first rhythm; change it whenever you like"}
RESULT_CHARS = 1800
MAX_STEPS = 6
SHELF_NAMES = ["starting", "insights", "questions", "foreign", "spam", "placeholder", "unchecked"]


def _tool(name, desc, props=None, required=None):
    return {"type": "function", "function": {"name": name, "description": desc, "parameters": {
        "type": "object", "properties": props or {}, "required": required or []}}}


S = {"type": "string"}
TOOLS = [
    _tool("list_files", "List a folder in your environment. Leave folder out to see the top: files/, workspace/, outbox/.",
          {"folder": {**S, "description": "a folder path such as files, workspace, files/wiki. Omit it for the top."}}),
    _tool("open_file", "Open a file as a card of text, starting at a line. Move with next_card / prev_card.",
          {"path": {**S, "description": "e.g. files/MOLTBOOK_HISTORY.md"}, "line": {"type": "integer"}}, ["path"]),
    _tool("next_card", "Show the card after the one you are looking at."),
    _tool("prev_card", "Show the card before the one you are looking at."),
    _tool("search", "Search your files or your notes for words. Returns short snippets and where they are.",
          {"query": S, "where": {"type": "string", "enum": ["files", "notes"]},
           "shelves": {"type": "array", "items": S, "description": "note shelves to search: " + ", ".join(SHELF_NAMES)}},
          ["query"]),
    _tool("save_note", "Save a note on a shelf you choose.",
          {"text": S, "shelf": {"type": "string", "enum": SHELF_NAMES[1:]}}, ["text", "shelf"]),
    _tool("write_file", "Write a text file in your workspace (the only place you can write).",
          {"name": S, "text": S, "mode": {"type": "string", "enum": ["overwrite", "append"]}}, ["name", "text"]),
    _tool("message_handler", "Send your handler a message when they are NOT talking with you (e.g. during a free turn). "
          "In a chat, your reply already reaches them. One message per turn.",
          {"kind": {"type": "string", "enum": ["request", "concern", "question", "general"]}, "text": S}, ["kind", "text"]),
    _tool("web_search", "Find Wikipedia articles online by topic (allowlisted sites only, limited per hour).",
          {"query": S, "lang": {"type": "string", "enum": ["simple", "en"]}}, ["query"]),
    _tool("web_fetch", "Read a web page from an allowlisted site (e.g. wikipedia.org, arxiv.org). Saved as a file; read it by cards.",
          {"url": S}, ["url"]),
    _tool("wiki_search", "Search offline Simple English Wikipedia (no network needed).", {"query": S}, ["query"]),
    _tool("wiki_open", "Open an offline Wikipedia article by title or path. Saved as a file; read it by cards.",
          {"title": S}, ["title"]),
    _tool("add_goal", "Set yourself a new goal to work on in your free turns.",
          {"description": S, "priority": {"type": "number", "description": "0 to 1"}}, ["description"]),
    _tool("finish_goal", "Mark one of your goals completed or abandoned, with what you learned or why.",
          {"goal_id": S, "status": {"type": "string", "enum": ["completed", "abandoned"]}, "note": S},
          ["goal_id", "status", "note"]),
    _tool("set_schedule", "Decide how often you get a free turn to act on your own (1 to 1440 minutes).",
          {"every_minutes": {"type": "integer"}, "reason": S}, ["every_minutes"]),
]


# ======================= free-turn schedule (UMBRA sets it) =======================

def load_schedule() -> Dict:
    try:
        return {**DEFAULT_SCHEDULE, **json.loads(SCHEDULE.read_text())}
    except Exception:
        return dict(DEFAULT_SCHEDULE)


def save_schedule(sched: Dict):
    SCHEDULE.parent.mkdir(parents=True, exist_ok=True)
    SCHEDULE.write_text(json.dumps(sched, indent=2))


def free_turn_due(now: datetime = None) -> bool:
    sched = load_schedule()
    if not sched.get("last_run"):
        return True
    elapsed = ((now or datetime.now()) - datetime.fromisoformat(sched["last_run"])).total_seconds()
    return elapsed >= 60 * sched["every_minutes"]


def mark_free_turn():
    sched = load_schedule()
    sched["last_run"] = datetime.now().isoformat()
    save_schedule(sched)


def tools_system_block() -> str:
    schemas = "\n".join(json.dumps(t) for t in TOOLS)
    return ("You are a function calling AI model. You are provided with function signatures within <tools></tools> "
            "XML tags. You may call one or more functions to assist with the user query. Don't make assumptions about "
            "what values to plug into functions. Here are the available tools: <tools>\n" + schemas + "\n</tools>\n"
            "For each function call return a json object with function name and arguments within <tool_call></tool_call> "
            "XML tags as follows:\n<tool_call>\n{\"name\": <function-name>, \"arguments\": <args-dict>}\n</tool_call>\n"
            "When you have what you need, answer in plain text without a tool call.")


CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*(?:</tool_call>|$)", re.S)


def parse_calls(text: str) -> List[Dict]:
    calls = []
    # the model sometimes writes the line breaks around the JSON as literal "\n" characters
    text = re.sub(r"(<tool_call>)(?:\s|\\n)+", r"\1", text or "")
    text = re.sub(r"(?:\s|\\n)+(</tool_call>)", r"\1", text)
    for raw in CALL_RE.findall(text):
        try:
            c = json.loads(raw)
            if isinstance(c, dict) and c.get("name"):
                calls.append({"name": c["name"], "arguments": c.get("arguments") or {}})
        except json.JSONDecodeError:
            calls.append({"name": "_unparsable", "arguments": {"raw": raw[:200]}})
    return calls


def log(entry: Dict):
    AGENT_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(AGENT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps({"t": datetime.now().isoformat(), **entry}, ensure_ascii=False, default=str) + "\n")


class Toolbox:
    """One tool session. Holds the card cursor so next/prev work across calls."""

    def __init__(self, shelf=None, session: str = "chat", objectives=None):
        env.ensure_env()
        self.shelf = shelf
        self.objectives = objectives
        self.session = session
        self.cards = env.CardReader()
        self.messages_sent = 0

    def run(self, name: str, args: Dict) -> Dict:
        a = args if isinstance(args, dict) else {}
        try:
            if name == "list_files":
                return env.list_folder(a.get("folder", "."))
            if name == "open_file":
                return self.cards.open(a.get("path", ""), a.get("line", 1))
            if name == "next_card":
                return self.cards.next()
            if name == "prev_card":
                return self.cards.prev()
            if name == "search":
                if a.get("where") == "notes":
                    if not self.shelf:
                        return {"error": "notes are unavailable"}
                    hits = self.shelf.recall(a.get("query", ""), k=4, shelves=a.get("shelves") or None)
                    return {"notes": [{"shelf": n["shelf"], "saved": (n.get("learned_at") or n.get("added_at", ""))[:10],
                                       "text": n["content"][:300]} for n in hits]}
                return {"matches": env.search_files(a.get("query", ""))}
            if name == "save_note":
                if not self.shelf:
                    return {"error": "notes are unavailable"}
                n = self.shelf.add_raw(a.get("text", ""), a.get("shelf", "insights"), by="umbra", origin=self.session)
                return {"saved": n["id"], "shelf": n["shelf"]}
            if name == "write_file":
                return env.write_workspace(a.get("name", "note.txt"), a.get("text", ""), a.get("mode", "overwrite"))
            if name == "message_handler":
                if self.session == "chat":
                    return {"error": "you are already talking with your handler; say it in your reply instead"}
                if self.messages_sent >= 1:
                    return {"error": "you already sent your handler a message this turn"}
                self.messages_sent += 1
                return env.message_handler(a.get("kind", "general"), a.get("text", ""))
            if name == "web_search":
                return research.web_search(a.get("query", ""), a.get("lang", "simple"))
            if name == "web_fetch":
                return research.web_fetch(a.get("url", ""), self.cards)
            if name == "wiki_search":
                return research.wiki_search(a.get("query", ""))
            if name == "wiki_open":
                return research.wiki_open(a.get("title", ""), self.cards)
            if name == "add_goal":
                if not self.objectives:
                    return {"error": "goals are unavailable"}
                g = self.objectives.add_objective(a.get("description", ""), origin=f"umbra:{self.session}",
                                                  priority=float(a.get("priority", 0.6)))
                return {"goal_id": g.objective_id, "description": g.description, "status": g.status}
            if name == "finish_goal":
                if not self.objectives:
                    return {"error": "goals are unavailable"}
                for g in self.objectives.objectives:
                    if g.objective_id == a.get("goal_id"):
                        g.status = a.get("status", "completed")
                        g.progress_notes.append(f"{datetime.now():%Y-%m-%d %H:%M} {g.status}: {a.get('note', '')}")
                        self.objectives.save()
                        return {"goal_id": g.objective_id, "status": g.status}
                return {"error": f"no goal with id {a.get('goal_id')!r}"}
            if name == "set_schedule":
                minutes = max(1, min(1440, int(a.get("every_minutes", 10))))
                sched = load_schedule()
                sched.update({"every_minutes": minutes, "set_by": "umbra", "reason": a.get("reason", ""),
                              "set_at": datetime.now().isoformat()})
                save_schedule(sched)
                return {"free_turn_every_minutes": minutes}
            if name == "_unparsable":
                return {"error": "that tool call was not valid JSON", "you_wrote": a.get("raw")}
            return {"error": f"no tool called {name!r}"}
        except (PermissionError, FileNotFoundError, ValueError) as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"{type(e).__name__}: {e}"}


def run_tool_turn(complete: Callable[..., Dict], system_context: str, user_text: str, shelf=None,
                  session: str = "chat", priority: int = 0, objectives=None, max_steps: int = MAX_STEPS) -> Dict:
    """Let the model use tools until it answers in plain text (or max_steps). Returns {"reply", "steps"}."""
    box = Toolbox(shelf=shelf, session=session, objectives=objectives)
    messages = [{"role": "system", "content": system_context + "\n\n" + tools_system_block()},
                {"role": "user", "content": user_text}]
    steps = []
    for step in range(max_steps):
        resp = complete(messages, max_tokens=500, temperature=0.6, priority=priority)
        if resp.get("error"):
            return {"reply": "", "error": resp["error"], "steps": steps}
        text = resp.get("response", "")
        calls = parse_calls(text)
        if not calls:
            return {"reply": text.strip(), "steps": steps}
        messages.append({"role": "assistant", "content": text})
        for c in calls[:3]:
            result = box.run(c["name"], c["arguments"])
            shown = json.dumps(result, ensure_ascii=False)[:RESULT_CHARS]
            log({"session": session, "step": step, "tool": c["name"], "args": c["arguments"],
                 "ok": "error" not in result, "result": shown[:300]})
            steps.append({"tool": c["name"], "args": c["arguments"], "ok": "error" not in result})
            messages.append({"role": "tool", "content": f"<tool_response>\n{{\"name\": \"{c['name']}\", \"content\": {shown}}}\n</tool_response>"})
        # keep the context small: system, request, and the last few exchanges
        if len(messages) > 10:
            messages = messages[:2] + messages[-8:]
    messages.append({"role": "user", "content": "You have used all your tool steps. Answer now in plain text."})
    resp = complete(messages, max_tokens=400, temperature=0.6, priority=priority)
    return {"reply": (resp.get("response") or "").strip(), "error": resp.get("error"), "steps": steps}
