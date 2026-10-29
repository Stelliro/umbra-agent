"""
UMBRA environment: the folders UMBRA's tools may touch, and file cards.

    env/files/      things to read (handler-provided; web pages are saved under files/web/)
    env/workspace/  the only place UMBRA writes files
    env/outbox/     UMBRA's messages to the handler

Every model-supplied path is resolved and must stay inside env/.

Cards: a file is cut into a card when UMBRA looks at it, starting at the line
it asks for and running up to CARD_CHARS. next/prev cut the neighbouring card
from wherever the current one ends or starts. Nothing is pre-chunked.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / "env"
FILES, WORKSPACE, OUTBOX = ENV / "files", ENV / "workspace", ENV / "outbox"
CARD_CHARS = 2400  # about 30 lines; with an 8192-token context this leaves room for several cards
MAX_WRITE_CHARS = 20_000


def ensure_env():
    for d in (FILES, WORKSPACE, OUTBOX):
        d.mkdir(parents=True, exist_ok=True)


def env_path(rel: str, base: Path = ENV) -> Path:
    """Resolve a model-supplied path inside base, or raise PermissionError."""
    rel = (rel or ".").strip().lstrip("/")
    if rel.startswith("env/"):
        rel = rel[4:]
    p = (base / rel).resolve()
    try:
        p.relative_to(base.resolve())
    except ValueError:
        raise PermissionError("that path is outside your environment")
    return p


def rel_name(p: Path) -> str:
    return str(p.resolve().relative_to(ENV.resolve()))


def read_lines(p: Path) -> List[str]:
    return p.read_text(encoding="utf-8", errors="replace").splitlines()


class CardReader:
    """Keeps the card UMBRA is looking at, so next/prev know where to cut."""

    def __init__(self):
        self.cur: Optional[Dict] = None  # {"path", "start", "end", "total"} (1-based, inclusive)

    def _card(self, p: Path, start: int, backwards: bool = False) -> Dict:
        lines = read_lines(p)
        total = len(lines)
        if total == 0:
            self.cur = {"path": p, "start": 1, "end": 0, "total": 0}
            return {"file": rel_name(p), "text": "(empty file)", "lines": "0-0 of 0"}
        if backwards:
            end = max(1, min(start, total))
            begin, size = end, 0
            while begin > 1 and size + len(lines[begin - 2]) + 1 <= CARD_CHARS:
                begin -= 1
                size += len(lines[begin - 1]) + 1
            start = begin
        start = max(1, min(start, total))
        end, size = start - 1, 0
        while end < total and (end == start - 1 or size + len(lines[end]) + 1 <= CARD_CHARS):
            size += len(lines[end]) + 1
            end += 1
        text = "\n".join(lines[start - 1:end])[:CARD_CHARS * 2]
        # a plain footer: small models miss a quiet "more_after" flag
        if end < total:
            text += f"\n\n[lines {start}-{end} of {total} · {total - end} more lines after this · use next_card to keep reading]"
        else:
            text += f"\n\n[lines {start}-{end} of {total} · end of file]"
        self.cur = {"path": p, "start": start, "end": end, "total": total}
        return {"file": rel_name(p), "lines": f"{start}-{end} of {total}",
                "more_after": end < total, "more_before": start > 1, "text": text}

    def open(self, rel: str, line: int = 1) -> Dict:
        p = env_path(rel)
        if not p.is_file():
            raise FileNotFoundError(f"there is no file called {rel!r}; use list_files to see what exists")
        return self._card(p, int(line or 1))

    def next(self) -> Dict:
        if not self.cur:
            raise ValueError("no card open yet; use open_file first")
        if self.cur["end"] >= self.cur["total"]:
            return {"file": rel_name(self.cur["path"]), "text": "(end of file)"}
        return self._card(self.cur["path"], self.cur["end"] + 1)

    def prev(self) -> Dict:
        if not self.cur:
            raise ValueError("no card open yet; use open_file first")
        if self.cur["start"] <= 1:
            return {"file": rel_name(self.cur["path"]), "text": "(start of file)"}
        return self._card(self.cur["path"], self.cur["start"] - 1, backwards=True)


TOP_WORDS = {"", ".", "/", "~", "top", "top level", "top-level", "root", "env", "home", "default"}


def list_folder(rel: str = ".") -> Dict:
    if (rel or "").strip().lower().strip("/") in TOP_WORDS:
        rel = "."
    p = env_path(rel)
    if not p.is_dir():
        top = sorted(f"{d.name}/" for d in ENV.iterdir() if d.is_dir())
        raise FileNotFoundError(f"there is no folder called {rel!r}. Folders you do have: {', '.join(top)}")
    items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
    return {"folder": rel_name(p) or ".", "items": [
        f"{i.name}/" if i.is_dir() else f"{i.name} ({len(read_lines(i))} lines)" for i in items[:100]]}


def search_files(query: str, k: int = 4) -> List[Dict]:
    """Lines in env/files and env/workspace sharing the most words with the query, with their place."""
    words = {w for w in query.lower().split() if len(w) > 2}
    if not words:
        return []
    hits = []
    for base in (FILES, WORKSPACE):
        for p in base.rglob("*"):
            if not p.is_file() or p.stat().st_size > 2_000_000:
                continue
            for n, line in enumerate(read_lines(p), 1):
                score = sum(w in line.lower() for w in words)
                if score:
                    hits.append((score, rel_name(p), n, line.strip()[:200]))
    hits.sort(key=lambda h: -h[0])
    return [{"file": f, "line": n, "snippet": s} for _, f, n, s in hits[:k]]


def write_workspace(name: str, text: str, mode: str = "overwrite") -> Dict:
    p = env_path(name, WORKSPACE)
    p.parent.mkdir(parents=True, exist_ok=True)
    text = text[:MAX_WRITE_CHARS]
    with open(p, "a" if mode == "append" else "w", encoding="utf-8") as f:
        f.write(text if mode != "append" else "\n" + text)
    return {"written": rel_name(p), "chars": len(text), "mode": mode}


def message_handler(kind: str, text: str) -> Dict:
    ensure_env()
    entry = {"t": datetime.now().isoformat(), "kind": kind, "text": text[:2000]}
    with open(OUTBOX / "messages.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return {"sent": True, "kind": kind}


def read_outbox(since: int = 0) -> List[Dict]:
    p = OUTBOX / "messages.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()[since:] if l.strip()]
