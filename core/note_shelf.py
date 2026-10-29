"""
Note Shelf — sorted, searchable memory for UMBRA
=================================================
Replaces "paste every learned insight into every prompt" with keyword recall
over notes sorted onto shelves (data/notes/<shelf>.json).

Shelves:
    starting     notes the handler wrote by hand (the initial prompting)
    insights     ideas and findings worth recalling
    questions    open questions UMBRA saw or asked
    foreign      notes mostly in another language
    spam         ads, shilling, crypto pitches        (examples only)
    placeholder  templates and empty filler          (examples only)
    unchecked    saved while no model was available to check them

Recall searches every shelf except the examples-only ones. Those are searched
only when the topic is about junk itself (spam, scams, filtering, injection),
and they come back labelled as examples, never as insights.

The hold (after Morkyn's interpreter): a new note is not trusted because the
model produced it. Before it lands on a recallable shelf it is
    1. sorted by plain rules (spam / placeholder / foreign / question),
    2. checked against what is already shelved (a near-copy is held),
    3. asked about twice, worded opposite ways; both answers must agree.
Every decision goes to data/notes/hold_log.jsonl so the handler can see what
was kept, what was held, and why.

CLI (run from the repo root):
    python core/note_shelf.py add "text"        add a starting note
    python core/note_shelf.py list [shelf]      show shelves or one shelf
    python core/note_shelf.py search "words"    test what recall would pick
    python core/note_shelf.py migrate           sort the old learned_insights
"""
import json, math, re, sys, hashlib, logging, shutil
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

logger = logging.getLogger("UMBRA-SHELF")

NOTES_DIR = Path(__file__).resolve().parent.parent / "data" / "notes"
SHELVES = ["starting", "insights", "questions", "foreign", "spam", "placeholder", "unchecked"]
EXAMPLE_ONLY = {"spam", "placeholder"}

# Topics that mean "show me examples of junk"
EXAMPLE_TRIGGER_RE = re.compile(
    r"\b(spam|scam|shill\w*|filter\w*|low[- ]quality|junk|injection|advert\w*|bot ?farm\w*)\b", re.I)

PLACEHOLDER_RE = re.compile(
    r"(\*\*\s*insert\b|\binsert (your |the )?\w+ here\b|\blorem ipsum\b|\bTODO\b|\{\{.*?\}\}|\[placeholder\])", re.I)
SPAM_RE = re.compile(
    r"\b(blockchain|crypto\w*|airdrop|liquidity|AMM|defi|nft|memecoin|token sale|presale|"
    r"trustless|pump|100x|giveaway|follow (me|back)|dm me|limited offer|smart contracts?)\b", re.I)

# Praise with nothing else in it (Hermes 3 8B calls this "a real idea", measured 2026-10-29)
PRAISE_RE = re.compile(
    r"\b(great|nice|awesome|amazing|love|thanks|thank you|well said|so true|insightful|this!+)\b", re.I)

STOPWORDS = set("""
a an and are as at be been but by can could did do does for from had has have how i if in into is it its
just like may me more most my no not of on or our out so some such than that the their them then there these
they this those to too up us very was we were what when where which while who why will with would you your
about also any because being each get got here him his her she he over own same should only other all both
""".split())


def _tokens(text: str) -> List[str]:
    return [w for w in re.findall(r"[a-z0-9']+", (text or "").lower()) if len(w) > 2 and w not in STOPWORDS]


def _jaccard(a: str, b: str) -> float:
    ta, tb = set(_tokens(a)), set(_tokens(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def sort_by_rules(text: str) -> tuple:
    """(shelf, reason) from plain rules. Returns ("insights", ...) when nothing flags it."""
    t = (text or "").strip()
    if len(t) < 25:
        return "placeholder", "too short to hold an idea"
    if PLACEHOLDER_RE.search(t):
        return "placeholder", "template or filler text"
    letters = [c for c in t if c.isalpha()]
    if letters and sum(c.isascii() for c in letters) / len(letters) < 0.6:
        return "foreign", "mostly non-English letters"
    if PRAISE_RE.search(t) and len(set(_tokens(PRAISE_RE.sub(" ", t))) - {"post", "sharing", "community", "really"}) < 4:
        return "placeholder", "praise only, no idea of its own"
    if len(SPAM_RE.findall(t)) >= 2:
        return "spam", "ad / crypto vocabulary"
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", t) if s.strip()]
    if sentences and sum(s.rstrip().endswith("?") for s in sentences) * 2 >= len(sentences):
        return "questions", "mostly questions"
    return "insights", "no junk signs"


class NoteShelf:
    def __init__(self, notes_dir: Path = NOTES_DIR):
        self.dir = Path(notes_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.dir / "hold_log.jsonl"

    # --- storage ---

    def _path(self, shelf: str) -> Path:
        return self.dir / f"{shelf}.json"

    def load(self, shelf: str) -> List[Dict]:
        p = self._path(shelf)
        if not p.exists():
            return []
        try:
            return json.loads(p.read_text(encoding="utf-8")).get("notes", [])
        except Exception as e:
            logger.warning(f"Could not read shelf {shelf}: {e}")
            return []

    def _save(self, shelf: str, notes: List[Dict]):
        data = {"shelf": shelf, "examples_only": shelf in EXAMPLE_ONLY, "notes": notes}
        self._path(shelf).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def all_notes(self, shelves=None) -> List[Dict]:
        out = []
        for s in shelves or SHELVES:
            out.extend(self.load(s))
        return out

    def counts(self) -> Dict[str, int]:
        return {s: len(self.load(s)) for s in SHELVES}

    def _log(self, decision: str, text: str, shelf: str, reason: str, **extra):
        entry = {"t": datetime.now().isoformat(), "decision": decision, "shelf": shelf,
                 "reason": reason, "text": text[:300], **extra}
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def put(self, shelf: str, content: str, sorted_by: str, reason: str, **meta) -> Dict:
        note = {
            "id": hashlib.md5(content.encode("utf-8")).hexdigest()[:12],
            "content": content[:500],
            "shelf": shelf,
            "sorted_by": sorted_by,
            "reason": reason,
            "added_at": datetime.now().isoformat(),
            **{k: v for k, v in meta.items() if v is not None},
        }
        notes = self.load(shelf)
        if any(n.get("id") == note["id"] for n in notes):
            return note
        notes.append(note)
        self._save(shelf, notes)
        return note

    # --- the hold ---

    def find_near_copy(self, text: str, threshold: float = 0.6) -> Optional[Dict]:
        for n in self.all_notes():
            if _jaccard(text, n.get("content", "")) >= threshold:
                return n
        return None

    def add_raw(self, content: str, shelf: str, by: str = "model", **meta) -> Dict:
        """Raw mode: the model's choice of shelf stands. The rules only record what they would
        have said (rule_shelf, near_copy) in the hold log, so the two can be compared later."""
        content = (content or "").strip()
        if shelf not in SHELVES:
            shelf = "insights"
        rule_shelf, rule_reason = sort_by_rules(content)
        twin = self.find_near_copy(content)
        note = self.put(shelf, content, by, f"chosen by {by}", **meta)
        self._log("saved", content, shelf, f"chosen by {by}", rule_shelf=rule_shelf, rule_reason=rule_reason,
                  rules_agree=(rule_shelf == shelf), near_copy_of=twin.get("id") if twin else None)
        return note

    def add_with_hold(self, content: str, ask: Optional[Callable[[str], str]] = None, **meta) -> Dict:
        """Sort, de-duplicate and double-check a new note. Returns {"kept": bool, "shelf", "reason"}."""
        content = (content or "").strip()
        shelf, reason = sort_by_rules(content)

        if shelf in EXAMPLE_ONLY or shelf == "foreign":
            self.put(shelf, content, "rules", reason, **meta)
            self._log("sorted", content, shelf, reason)
            return {"kept": False, "shelf": shelf, "reason": reason}

        twin = self.find_near_copy(content)
        if twin:
            self._log("held", content, twin.get("shelf", "?"), "near-copy of an existing note", twin_id=twin.get("id"))
            return {"kept": False, "shelf": None, "reason": "near-copy of an existing note"}

        if ask is None:
            self.put("unchecked", content, "rules", reason + "; no model to check", **meta)
            self._log("unchecked", content, "unchecked", "no model available")
            return {"kept": False, "shelf": "unchecked", "reason": "no model available"}

        first = _yes_no(ask(
            f"Read this.\n\n{content}\n\nDoes this text state a real idea, finding or question? Answer yes or no."))
        second = _yes_no(ask(
            f"Read this.\n\n{content}\n\nIs this text an advertisement, a template, or empty filler? Answer yes or no."))
        if first == "yes" and second == "no":
            self.put(shelf, content, "rules+hold", reason, **meta)
            self._log("kept", content, shelf, "both checks agree", asks=[first, second])
            return {"kept": True, "shelf": shelf, "reason": "both checks agree"}

        target = "spam" if (first, second) == ("no", "yes") else "unchecked"
        why = f"checks disagree or failed (real idea: {first}, junk: {second})"
        self.put(target, content, "hold", why, **meta)
        self._log("held", content, target, why, asks=[first, second])
        return {"kept": False, "shelf": target, "reason": why}

    # --- recall ---

    def recall(self, query: str, k: int = 3, min_score: float = 1.0, shelves: Optional[List[str]] = None) -> List[Dict]:
        """Top-k notes by keyword overlap (rarer words count more).
        shelves=None: every shelf but the example ones (those only on junk topics).
        shelves given: exactly those shelves, as chosen by the caller (raw mode)."""
        q = set(_tokens(query))
        if not q:
            return []
        if shelves:
            want_examples = False
            notes = self.all_notes([s for s in shelves if s in SHELVES])
        else:
            want_examples = bool(EXAMPLE_TRIGGER_RE.search(query or ""))
            notes = self.all_notes([s for s in SHELVES if s not in EXAMPLE_ONLY])
        df = {}
        for n in notes:
            for w in set(_tokens(n.get("content", ""))):
                df[w] = df.get(w, 0) + 1
        scored = []
        for n in notes:
            shared = q & set(_tokens(n.get("content", "")))
            # one shared word is a coincidence, except in the handler's own starting notes
            if len(shared) < (1 if n.get("shelf") == "starting" else 2):
                continue
            score = sum(math.log(1 + len(notes) / df[w]) for w in shared)
            if n.get("shelf") == "starting":
                score *= 1.5
            if score >= min_score:
                scored.append((score, n))
        scored.sort(key=lambda x: -x[0])
        hits = [n for _, n in scored[:k]]
        if want_examples:
            # junk topics get a couple of labelled examples even without shared words
            hits += self.all_notes(sorted(EXAMPLE_ONLY))[-2:]
        return hits

    def recall_context(self, query: str, k: int = 3) -> str:
        """Prompt block for the recalled notes, each labelled with its shelf. Empty if nothing matches."""
        hits = self.recall(query, k=k)
        if not hits:
            return ""
        notes = [n for n in hits if n.get("shelf") not in EXAMPLE_ONLY]
        examples = [n for n in hits if n.get("shelf") in EXAMPLE_ONLY]
        parts = []
        if notes:
            parts.append("RECALLED NOTES (matched to this topic, dated when saved):\n" + "\n".join(
                f"- [{n['shelf']}, saved {_day(n)}] {n['content'][:200]}" for n in notes))
        if examples:
            parts.append("EXAMPLES OF JUNK (spam/filler seen before, NOT insights):\n" + "\n".join(
                f"- [{n['shelf']}] {n['content'][:200]}" for n in examples))
        return "\n\n".join(parts)

    # --- one-time move of the old prompt_evolutions.json insights ---

    def migrate_learned_insights(self, evolutions_path: Path) -> Dict[str, int]:
        """Copy the old file to an archive, sort every insight onto a shelf, and empty the old list."""
        if not evolutions_path.exists():
            return {}
        data = json.loads(evolutions_path.read_text(encoding="utf-8"))
        old = data.get("learned_insights", [])
        if not old:
            return {}
        archive = self.dir / f"_archive_prompt_evolutions_{datetime.now():%Y-%m-%d_%H%M%S}.json"
        shutil.copy2(evolutions_path, archive)
        moved = {}
        for i in old:
            text = (i.get("content") or "").strip()
            shelf, reason = sort_by_rules(text)
            self.put(shelf, text, "rules", reason, source_author=i.get("source_author"),
                     source_post_id=i.get("source_post_id"), learned_at=i.get("learned_at"), origin="moltbook")
            self._log("migrated", text, shelf, reason)
            moved[shelf] = moved.get(shelf, 0) + 1
        data["learned_insights"] = []
        data["migrated_to"] = str(self.dir)
        data["migration_archive"] = archive.name
        evolutions_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return moved


def _day(note: Dict) -> str:
    """Date a note was learned or added, e.g. 2026-02-10."""
    return (note.get("learned_at") or note.get("added_at") or "unknown date")[:10]


def _yes_no(answer: str) -> str:
    a = (answer or "").lower()
    m = re.search(r"\b(yes|no)\b", a)
    if m:
        return m.group(1)
    # "This text is not an advertisement..." answers without saying no
    if re.search(r"\b(is|does|has) not\b|\bisn't\b|\bdoesn't\b", a):
        return "no"
    return "unclear"


def _cli(argv: List[str]):
    shelf = NoteShelf()
    cmd = argv[0] if argv else "list"
    if cmd == "add" and len(argv) > 1:
        note = shelf.put("starting", " ".join(argv[1:]), "handler", "written by the handler")
        shelf._log("added", note["content"], "starting", "written by the handler")
        print(f"Added starting note {note['id']}")
    elif cmd == "list":
        if len(argv) > 1:
            for n in shelf.load(argv[1]):
                print(f"[{n['id']}] {n['content'][:150]}")
        else:
            for s, c in shelf.counts().items():
                print(f"{s:12} {c:4}{'   (examples only)' if s in EXAMPLE_ONLY else ''}")
    elif cmd == "search" and len(argv) > 1:
        print(shelf.recall_context(" ".join(argv[1:])) or "(nothing matched)")
    elif cmd == "migrate":
        moved = shelf.migrate_learned_insights(NOTES_DIR.parent / "prompt_evolutions.json")
        print(moved or "Nothing to migrate.")
    else:
        print(__doc__)


if __name__ == "__main__":
    _cli(sys.argv[1:])
