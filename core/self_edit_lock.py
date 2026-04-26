"""
Self-edit lock helpers.

This lock prevents autonomous/self-improve code paths from editing source files
until the handler explicitly unlocks it.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict


LOCK_PATH = Path(__file__).parent.parent / "data" / "self_edit_lock.json"


def _default_state() -> Dict:
    return {
        "locked": True,
        "reason": "Self-edit is locked by default until handler approval.",
        "updated_at": datetime.now().isoformat(),
        "actor": "system"
    }


def _save(state: Dict):
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def get_self_edit_lock_status() -> Dict:
    if not LOCK_PATH.exists():
        state = _default_state()
        _save(state)
        return state

    try:
        data = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
        if "locked" not in data:
            data["locked"] = True
        if "reason" not in data:
            data["reason"] = "No reason provided."
        if "updated_at" not in data:
            data["updated_at"] = datetime.now().isoformat()
        if "actor" not in data:
            data["actor"] = "unknown"
        return data
    except Exception:
        state = _default_state()
        _save(state)
        return state


def is_self_edit_locked() -> bool:
    return bool(get_self_edit_lock_status().get("locked", True))


def set_self_edit_lock(locked: bool, reason: str, actor: str = "handler") -> Dict:
    state = {
        "locked": bool(locked),
        "reason": reason,
        "updated_at": datetime.now().isoformat(),
        "actor": actor,
    }
    _save(state)
    return state
