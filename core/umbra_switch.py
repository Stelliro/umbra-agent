"""
UMBRA Switch CPU v1.0 — External Editable Weight & Index Database
==================================================================
A persistent, self-editable "switch" graph stored OUTSIDE the GGUF.

Why this exists
---------------
The GGUF model is static — its weights are frozen at training time.
The Switch CPU is a Python-level overlay that lets UMBRA expand its
reasoning, pin facts, and bias responses without ever touching the
GGUF. UMBRA can edit its own switches at runtime: register new ones,
reinforce/weaken existing ones, link them into a graph, and prune.

A "switch" is a single weighted node:
    id           sha8 of normalized key
    key          canonical trigger / concept name
    category     concept | response | bias | route | fact | skill
    content      text payload (the "weight" body — what to inject)
    weight       float clamped to [0.0, 10.0], default 1.0
    polarity     float in [-1.0, 1.0] (bias direction), default 0.0
    tags         list[str]
    triggers     list[str]  — extra phrases that activate this switch
    parents      list[str]  — graph linkage (parent switch ids)
    usage_count  int
    last_used    iso timestamp
    created_at   iso timestamp
    updated_at   iso timestamp
    locked       bool — protected from auto-prune and bulk edit

Routing
-------
`route(prompt)` returns a `RouteResult` with the top-K matching
switches and a ready-to-inject context block. The orchestrator
(`core/umbra_brain.py`) prepends this block to the system prompt
so the GGUF's behavior is shaped by the external switch DB.

CPU mode
--------
If a switch in `response` category scores above `direct_threshold`,
the router can return its `content` directly as the answer — no GGUF
call required. This is the seed of "the app IS the model": as the
switch DB grows, more prompts are answered from pure Python.

No external dependencies — uses stdlib `sqlite3` only.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger("UMBRA-SWITCH")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_DB_PATH = Path("data") / "umbra_switch.db"

WEIGHT_MIN = 0.0
WEIGHT_MAX = 10.0
WEIGHT_DEFAULT = 1.0
POLARITY_MIN = -1.0
POLARITY_MAX = 1.0

VALID_CATEGORIES = {"concept", "response", "bias", "route", "fact", "skill"}

# Stop words excluded from keyword indexing / matching.
_STOPWORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "if", "then", "of", "to", "in",
    "on", "at", "for", "with", "by", "from", "is", "are", "was", "were",
    "be", "been", "being", "as", "it", "its", "that", "this", "these",
    "those", "i", "you", "he", "she", "we", "they", "me", "him", "her",
    "us", "them", "my", "your", "his", "their", "our", "do", "does", "did",
    "have", "has", "had", "will", "would", "can", "could", "should", "shall",
    "may", "might", "must", "not", "no", "so", "than", "into", "about",
    "what", "when", "where", "why", "how", "who", "whom", "which",
})

_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_key(key: str) -> str:
    return re.sub(r"\s+", " ", key.strip().lower())


def _switch_id(key: str) -> str:
    norm = _normalize_key(key)
    return hashlib.sha1(norm.encode("utf-8")).hexdigest()[:16]


def _tokens(text: str) -> List[str]:
    return [t.lower() for t in _TOKEN_RE.findall(text or "") if t.lower() not in _STOPWORDS and len(t) > 1]


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Switch:
    id: str
    key: str
    category: str
    content: str
    weight: float = WEIGHT_DEFAULT
    polarity: float = 0.0
    tags: List[str] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)
    parents: List[str] = field(default_factory=list)
    usage_count: int = 0
    last_used: Optional[str] = None
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    locked: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RouteResult:
    """Output of `UmbraSwitch.route(prompt)`."""
    matched: List[Tuple[Switch, float]] = field(default_factory=list)
    context_block: str = ""
    direct_answer: Optional[str] = None
    direct_switch_id: Optional[str] = None

    @property
    def has_direct(self) -> bool:
        return self.direct_answer is not None

    def ids(self) -> List[str]:
        return [s.id for s, _ in self.matched]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS switches (
    id            TEXT PRIMARY KEY,
    key           TEXT NOT NULL UNIQUE,
    category      TEXT NOT NULL,
    content       TEXT NOT NULL,
    weight        REAL NOT NULL DEFAULT 1.0,
    polarity      REAL NOT NULL DEFAULT 0.0,
    tags          TEXT NOT NULL DEFAULT '[]',
    triggers      TEXT NOT NULL DEFAULT '[]',
    parents       TEXT NOT NULL DEFAULT '[]',
    usage_count   INTEGER NOT NULL DEFAULT 0,
    last_used     TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL,
    locked        INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_switch_category ON switches(category);
CREATE INDEX IF NOT EXISTS idx_switch_weight   ON switches(weight DESC);
CREATE INDEX IF NOT EXISTS idx_switch_lastused ON switches(last_used DESC);

CREATE TABLE IF NOT EXISTS switch_tokens (
    token       TEXT NOT NULL,
    switch_id   TEXT NOT NULL,
    PRIMARY KEY (token, switch_id),
    FOREIGN KEY (switch_id) REFERENCES switches(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_token_switch ON switch_tokens(switch_id);
CREATE INDEX IF NOT EXISTS idx_token_value  ON switch_tokens(token);

CREATE TABLE IF NOT EXISTS switch_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ts          TEXT NOT NULL,
    op          TEXT NOT NULL,
    switch_id   TEXT,
    detail      TEXT
);
"""


# ---------------------------------------------------------------------------
# UmbraSwitch
# ---------------------------------------------------------------------------

class UmbraSwitch:
    """Persistent editable weight/index database living outside the GGUF."""

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        *,
        direct_threshold: float = 6.0,
        route_top_k: int = 6,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.direct_threshold = float(direct_threshold)
        self.route_top_k = int(route_top_k)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,
            isolation_level=None,  # autocommit; we manage with BEGIN/COMMIT
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript(_SCHEMA)
        logger.info("Switch DB ready at %s", self.db_path)

    # -- lifecycle ----------------------------------------------------------

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except Exception:  # pragma: no cover - defensive
                pass

    def __enter__(self) -> "UmbraSwitch":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.close()

    # -- CRUD ---------------------------------------------------------------

    def register(
        self,
        key: str,
        content: str,
        *,
        category: str = "concept",
        weight: float = WEIGHT_DEFAULT,
        polarity: float = 0.0,
        tags: Optional[Iterable[str]] = None,
        triggers: Optional[Iterable[str]] = None,
        parents: Optional[Iterable[str]] = None,
        locked: bool = False,
    ) -> Switch:
        """Insert a new switch or update content of an existing one (by key)."""
        if not key or not key.strip():
            raise ValueError("switch key must be non-empty")
        if category not in VALID_CATEGORIES:
            raise ValueError(f"category must be one of {sorted(VALID_CATEGORIES)}")

        sw = Switch(
            id=_switch_id(key),
            key=_normalize_key(key),
            category=category,
            content=content or "",
            weight=_clamp(weight, WEIGHT_MIN, WEIGHT_MAX),
            polarity=_clamp(polarity, POLARITY_MIN, POLARITY_MAX),
            tags=list(tags or []),
            triggers=list(triggers or []),
            parents=list(parents or []),
            locked=bool(locked),
        )

        with self._lock, self._conn:
            existing = self._conn.execute(
                "SELECT id, weight, usage_count, created_at, locked FROM switches WHERE id = ?",
                (sw.id,),
            ).fetchone()

            if existing:
                # Update in place; preserve weight if caller used default,
                # preserve usage_count and created_at, respect lock.
                if existing["locked"] and not locked:
                    raise PermissionError(f"switch '{sw.key}' is locked")
                new_weight = sw.weight if weight != WEIGHT_DEFAULT else existing["weight"]
                self._conn.execute(
                    """
                    UPDATE switches SET
                        category = ?, content = ?, weight = ?, polarity = ?,
                        tags = ?, triggers = ?, parents = ?, updated_at = ?,
                        locked = ?
                    WHERE id = ?
                    """,
                    (
                        sw.category, sw.content, new_weight, sw.polarity,
                        json.dumps(sw.tags), json.dumps(sw.triggers),
                        json.dumps(sw.parents), _now_iso(),
                        int(sw.locked), sw.id,
                    ),
                )
                sw.weight = new_weight
                sw.usage_count = existing["usage_count"]
                sw.created_at = existing["created_at"]
                self._reindex_tokens(sw)
                self._log("update", sw.id, sw.key)
            else:
                self._conn.execute(
                    """
                    INSERT INTO switches (
                        id, key, category, content, weight, polarity,
                        tags, triggers, parents, usage_count, last_used,
                        created_at, updated_at, locked
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        sw.id, sw.key, sw.category, sw.content, sw.weight, sw.polarity,
                        json.dumps(sw.tags), json.dumps(sw.triggers),
                        json.dumps(sw.parents), sw.usage_count, sw.last_used,
                        sw.created_at, sw.updated_at, int(sw.locked),
                    ),
                )
                self._reindex_tokens(sw)
                self._log("create", sw.id, sw.key)

        return sw

    def get(self, id_or_key: str) -> Optional[Switch]:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM switches WHERE id = ? OR key = ?",
                (id_or_key, _normalize_key(id_or_key)),
            ).fetchone()
        return _row_to_switch(row) if row else None

    def delete(self, id_or_key: str, *, force: bool = False) -> bool:
        sw = self.get(id_or_key)
        if not sw:
            return False
        if sw.locked and not force:
            raise PermissionError(f"switch '{sw.key}' is locked (use force=True)")
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM switches WHERE id = ?", (sw.id,))
            self._log("delete", sw.id, sw.key)
        return True

    def all(self, category: Optional[str] = None) -> List[Switch]:
        with self._lock:
            if category:
                rows = self._conn.execute(
                    "SELECT * FROM switches WHERE category = ? ORDER BY weight DESC",
                    (category,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM switches ORDER BY weight DESC"
                ).fetchall()
        return [_row_to_switch(r) for r in rows]

    # -- weight editing -----------------------------------------------------

    def reinforce(self, id_or_key: str, delta: float = 0.1) -> Optional[Switch]:
        return self._adjust_weight(id_or_key, abs(delta))

    def weaken(self, id_or_key: str, delta: float = 0.1) -> Optional[Switch]:
        return self._adjust_weight(id_or_key, -abs(delta))

    def set_weight(self, id_or_key: str, value: float) -> Optional[Switch]:
        sw = self.get(id_or_key)
        if not sw:
            return None
        new_w = _clamp(value, WEIGHT_MIN, WEIGHT_MAX)
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE switches SET weight = ?, updated_at = ? WHERE id = ?",
                (new_w, _now_iso(), sw.id),
            )
            self._log("set_weight", sw.id, f"{sw.weight:.3f} -> {new_w:.3f}")
        sw.weight = new_w
        return sw

    def _adjust_weight(self, id_or_key: str, delta: float) -> Optional[Switch]:
        sw = self.get(id_or_key)
        if not sw:
            return None
        return self.set_weight(sw.id, sw.weight + delta)

    def lock(self, id_or_key: str, locked: bool = True) -> Optional[Switch]:
        sw = self.get(id_or_key)
        if not sw:
            return None
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE switches SET locked = ?, updated_at = ? WHERE id = ?",
                (int(locked), _now_iso(), sw.id),
            )
            self._log("lock" if locked else "unlock", sw.id, None)
        sw.locked = locked
        return sw

    # -- graph --------------------------------------------------------------

    def link(self, parent_id_or_key: str, child_id_or_key: str) -> bool:
        parent = self.get(parent_id_or_key)
        child = self.get(child_id_or_key)
        if not parent or not child:
            return False
        if parent.id == child.id:
            raise ValueError("cannot link a switch to itself")
        if parent.id in child.parents:
            return True
        child.parents.append(parent.id)
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE switches SET parents = ?, updated_at = ? WHERE id = ?",
                (json.dumps(child.parents), _now_iso(), child.id),
            )
            self._log("link", child.id, f"parent={parent.id}")
        return True

    def children_of(self, id_or_key: str) -> List[Switch]:
        sw = self.get(id_or_key)
        if not sw:
            return []
        with self._lock:
            rows = self._conn.execute("SELECT * FROM switches").fetchall()
        out: List[Switch] = []
        for row in rows:
            parents = json.loads(row["parents"] or "[]")
            if sw.id in parents:
                out.append(_row_to_switch(row))
        return out

    # -- search & routing ---------------------------------------------------

    def search(self, query: str, top_k: int = 8) -> List[Tuple[Switch, float]]:
        """Return top-K switches by token overlap * weight, descending."""
        toks = _tokens(query)
        if not toks:
            return []
        placeholders = ",".join("?" * len(toks))
        with self._lock:
            rows = self._conn.execute(
                f"""
                SELECT s.*, COUNT(t.token) AS hits
                FROM switches s
                JOIN switch_tokens t ON t.switch_id = s.id
                WHERE t.token IN ({placeholders})
                GROUP BY s.id
                ORDER BY hits DESC, s.weight DESC
                LIMIT ?
                """,
                (*toks, top_k),
            ).fetchall()
        scored: List[Tuple[Switch, float]] = []
        for row in rows:
            sw = _row_to_switch(row)
            hits = row["hits"]
            # Score = token-overlap proportion * weight, blended with polarity boost
            overlap = hits / max(len(toks), 1)
            score = overlap * sw.weight + 0.25 * abs(sw.polarity)
            scored.append((sw, round(score, 4)))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    def route(self, prompt: str) -> RouteResult:
        """Build a routing decision for the given prompt."""
        matched = self.search(prompt, top_k=self.route_top_k)
        result = RouteResult(matched=matched)

        if not matched:
            return result

        # Build injectable context block
        lines: List[str] = ["[UMBRA SWITCH CONTEXT]"]
        for sw, score in matched:
            tag = f"({sw.category}, w={sw.weight:.2f}, score={score:.2f})"
            lines.append(f"- {sw.key} {tag}: {sw.content}")
        result.context_block = "\n".join(lines)

        # Direct answer? Top match must be a 'response' switch above threshold.
        top_sw, top_score = matched[0]
        if top_sw.category == "response" and top_score >= self.direct_threshold:
            result.direct_answer = top_sw.content
            result.direct_switch_id = top_sw.id
            self._mark_used([top_sw.id])
        else:
            self._mark_used([sw.id for sw, _ in matched])

        return result

    # -- feedback / learning ------------------------------------------------

    def apply_feedback(
        self,
        switch_ids: Iterable[str],
        signal: float,
    ) -> None:
        """Reinforce or weaken switches based on a signal in [-1.0, 1.0]."""
        signal = _clamp(signal, -1.0, 1.0)
        if signal == 0.0:
            return
        delta = 0.25 * signal  # modest per-feedback adjustment
        for sid in switch_ids:
            self._adjust_weight(sid, delta)

    def teach_response(
        self,
        prompt: str,
        response: str,
        *,
        weight: float = 2.0,
        tags: Optional[Iterable[str]] = None,
    ) -> Switch:
        """Convenience: store a prompt->response pair as a 'response' switch."""
        key = f"resp::{_normalize_key(prompt)[:80]}"
        return self.register(
            key=key,
            content=response,
            category="response",
            weight=weight,
            tags=list(tags or []),
            triggers=[prompt],
        )

    # -- maintenance --------------------------------------------------------

    def prune(self, threshold: float = 0.25, max_remove: int = 100) -> int:
        """Delete unlocked switches with weight <= threshold. Returns count removed."""
        with self._lock, self._conn:
            rows = self._conn.execute(
                """
                SELECT id, key FROM switches
                WHERE locked = 0 AND weight <= ?
                ORDER BY weight ASC, last_used IS NULL DESC, last_used ASC
                LIMIT ?
                """,
                (float(threshold), int(max_remove)),
            ).fetchall()
            for row in rows:
                self._conn.execute("DELETE FROM switches WHERE id = ?", (row["id"],))
                self._log("prune", row["id"], row["key"])
        return len(rows)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._conn.execute("SELECT COUNT(*) AS c FROM switches").fetchone()["c"]
            by_cat = self._conn.execute(
                "SELECT category, COUNT(*) AS c FROM switches GROUP BY category"
            ).fetchall()
            top = self._conn.execute(
                "SELECT key, weight FROM switches ORDER BY weight DESC LIMIT 10"
            ).fetchall()
            tokens = self._conn.execute("SELECT COUNT(*) AS c FROM switch_tokens").fetchone()["c"]
        return {
            "total": total,
            "tokens_indexed": tokens,
            "by_category": {r["category"]: r["c"] for r in by_cat},
            "top_weights": [{"key": r["key"], "weight": r["weight"]} for r in top],
            "db_path": str(self.db_path),
        }

    def snapshot(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self.all()]

    def import_snapshot(self, items: Iterable[Dict[str, Any]], *, overwrite: bool = False) -> int:
        """Import a previously exported snapshot. Returns number imported."""
        count = 0
        for item in items:
            key = item.get("key")
            if not key:
                continue
            if not overwrite and self.get(key):
                continue
            self.register(
                key=key,
                content=item.get("content", ""),
                category=item.get("category", "concept"),
                weight=float(item.get("weight", WEIGHT_DEFAULT)),
                polarity=float(item.get("polarity", 0.0)),
                tags=item.get("tags") or [],
                triggers=item.get("triggers") or [],
                parents=item.get("parents") or [],
                locked=bool(item.get("locked", False)),
            )
            count += 1
        return count

    # -- internal -----------------------------------------------------------

    def _reindex_tokens(self, sw: Switch) -> None:
        """Rebuild token index for one switch. Call inside an active transaction."""
        self._conn.execute("DELETE FROM switch_tokens WHERE switch_id = ?", (sw.id,))
        bag = set(_tokens(sw.key))
        bag.update(_tokens(sw.content))
        for trig in sw.triggers:
            bag.update(_tokens(trig))
        for tag in sw.tags:
            bag.update(_tokens(tag))
        if not bag:
            return
        self._conn.executemany(
            "INSERT OR IGNORE INTO switch_tokens (token, switch_id) VALUES (?, ?)",
            [(tok, sw.id) for tok in bag],
        )

    def _mark_used(self, switch_ids: Iterable[str]) -> None:
        ids = list(switch_ids)
        if not ids:
            return
        ts = _now_iso()
        with self._lock, self._conn:
            for sid in ids:
                self._conn.execute(
                    "UPDATE switches SET usage_count = usage_count + 1, last_used = ? WHERE id = ?",
                    (ts, sid),
                )

    def _log(self, op: str, switch_id: Optional[str], detail: Optional[str]) -> None:
        try:
            self._conn.execute(
                "INSERT INTO switch_log (ts, op, switch_id, detail) VALUES (?,?,?,?)",
                (_now_iso(), op, switch_id, detail),
            )
        except Exception:  # pragma: no cover - logging must never break callers
            pass


# ---------------------------------------------------------------------------
# Row -> Switch converter
# ---------------------------------------------------------------------------

def _row_to_switch(row: sqlite3.Row) -> Switch:
    return Switch(
        id=row["id"],
        key=row["key"],
        category=row["category"],
        content=row["content"],
        weight=float(row["weight"]),
        polarity=float(row["polarity"]),
        tags=json.loads(row["tags"] or "[]"),
        triggers=json.loads(row["triggers"] or "[]"),
        parents=json.loads(row["parents"] or "[]"),
        usage_count=int(row["usage_count"]),
        last_used=row["last_used"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        locked=bool(row["locked"]),
    )


# ---------------------------------------------------------------------------
# Module-level singleton accessor
# ---------------------------------------------------------------------------

_default: Optional[UmbraSwitch] = None
_default_lock = threading.Lock()


def get_default_switch(db_path: str | Path = DEFAULT_DB_PATH) -> UmbraSwitch:
    """Return a process-wide default UmbraSwitch instance."""
    global _default
    with _default_lock:
        if _default is None:
            _default = UmbraSwitch(db_path=db_path)
        return _default


__all__ = [
    "UmbraSwitch",
    "Switch",
    "RouteResult",
    "get_default_switch",
    "DEFAULT_DB_PATH",
    "VALID_CATEGORIES",
]
