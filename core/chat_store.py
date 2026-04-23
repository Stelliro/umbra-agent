"""
Chat Store v1.0 — Multi-Conversation Management
=================================================
Multiple chats, folders, pinning, keyword indexing.
AI can reference past chats via keyword search.
"""
import json, os, re, time, hashlib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

def _id():
    return hashlib.md5(f"{time.time()}{os.urandom(4).hex()}".encode()).hexdigest()[:12]

def _now():
    return datetime.now().isoformat()

def _keywords(text, min_len=3):
    """Extract keywords from text for indexing."""
    words = re.findall(r'[a-zA-Z0-9_]+', text.lower())
    # Filter stopwords and short words
    stop = {'the','and','for','are','but','not','you','all','can','had','her','was','one',
            'our','out','has','its','let','say','she','too','use','how','did','get','may',
            'him','his','old','see','way','who','boy','day','new','now','any','few','got',
            'own','why','dont','will','just','that','this','with','have','from','they',
            'been','some','what','when','more','make','like','than','them','each','also',
            'into','over','such','very','after','about','would','could','should','their',
            'there','which','these','other','being','doing','going','where','still','umbra',
            'handler','stelliro'}
    return list(set(w for w in words if len(w) >= min_len and w not in stop))


class ChatStore:
    def __init__(self, data_dir="data"):
        self.base = Path(data_dir)
        self.chats_dir = self.base / "chats"
        self.index_file = self.base / "chat_index.json"
        self.folders_file = self.base / "chat_folders.json"
        self.chats_dir.mkdir(parents=True, exist_ok=True)
        self._index = self._load_index()
        self._folders = self._load_folders()

    # === Index ===

    def _load_index(self):
        if self.index_file.exists():
            try: return json.loads(self.index_file.read_text())
            except: pass
        return {"keywords": {}, "chats": {}}

    def _save_index(self):
        self.index_file.write_text(json.dumps(self._index, indent=1))

    def _load_folders(self):
        if self.folders_file.exists():
            try: return json.loads(self.folders_file.read_text())
            except: pass
        return {"folders": []}

    def _save_folders(self):
        self.folders_file.write_text(json.dumps(self._folders, indent=1))

    def _index_chat(self, chat_id, chat_data):
        """Rebuild keyword index for a single chat."""
        # Remove old entries for this chat
        for kw in list(self._index["keywords"]):
            if chat_id in self._index["keywords"][kw]:
                self._index["keywords"][kw].remove(chat_id)
                if not self._index["keywords"][kw]:
                    del self._index["keywords"][kw]

        # Build new keywords from all messages + title
        all_text = chat_data.get("title", "")
        for m in chat_data.get("messages", []):
            all_text += " " + m.get("content", "")

        kws = _keywords(all_text)
        for kw in kws:
            if kw not in self._index["keywords"]:
                self._index["keywords"][kw] = []
            if chat_id not in self._index["keywords"][kw]:
                self._index["keywords"][kw].append(chat_id)

        # Store chat metadata in index
        self._index["chats"][chat_id] = {
            "title": chat_data.get("title", "Untitled"),
            "folder": chat_data.get("folder"),
            "pinned": chat_data.get("pinned", False),
            "updated": chat_data.get("updated", _now()),
            "msg_count": len(chat_data.get("messages", [])),
        }
        self._save_index()

    # === Chat CRUD ===

    def _chat_path(self, chat_id):
        return self.chats_dir / f"{chat_id}.json"

    def create_chat(self, title="New Chat", folder=None) -> str:
        cid = _id()
        chat = {
            "id": cid,
            "title": title,
            "folder": folder,
            "pinned": False,
            "created": _now(),
            "updated": _now(),
            "messages": [],
        }
        self._chat_path(cid).write_text(json.dumps(chat, indent=1))
        self._index_chat(cid, chat)
        return cid

    def get_chat(self, chat_id) -> Optional[Dict]:
        p = self._chat_path(chat_id)
        if not p.exists():
            return None
        try: return json.loads(p.read_text())
        except: return None

    def delete_chat(self, chat_id):
        p = self._chat_path(chat_id)
        if p.exists():
            p.unlink()
        # Clean index
        for kw in list(self._index["keywords"]):
            if chat_id in self._index["keywords"][kw]:
                self._index["keywords"][kw].remove(chat_id)
                if not self._index["keywords"][kw]:
                    del self._index["keywords"][kw]
        self._index["chats"].pop(chat_id, None)
        self._save_index()

    def update_chat(self, chat_id, **fields):
        """Update chat metadata (title, folder, pinned)."""
        chat = self.get_chat(chat_id)
        if not chat:
            return False
        for k in ("title", "folder", "pinned"):
            if k in fields:
                chat[k] = fields[k]
        chat["updated"] = _now()
        self._chat_path(chat_id).write_text(json.dumps(chat, indent=1))
        self._index_chat(chat_id, chat)
        return True

    def add_message(self, chat_id, role, content) -> bool:
        chat = self.get_chat(chat_id)
        if not chat:
            return False
        msg = {"role": role, "content": content, "timestamp": _now()}
        chat["messages"].append(msg)
        chat["updated"] = _now()
        # Auto-title from first user message
        if chat["title"] == "New Chat" and role == "handler" and len(chat["messages"]) == 1:
            chat["title"] = content[:60].strip()
        self._chat_path(chat_id).write_text(json.dumps(chat, indent=1))
        self._index_chat(chat_id, chat)
        return True

    def get_messages(self, chat_id, limit=50) -> List[Dict]:
        chat = self.get_chat(chat_id)
        if not chat:
            return []
        return chat.get("messages", [])[-limit:]

    def list_chats(self) -> List[Dict]:
        """List all chats with metadata (no messages). Pinned first, then by updated desc."""
        chats = []
        for cid, meta in self._index.get("chats", {}).items():
            chats.append({"id": cid, **meta})
        chats.sort(key=lambda c: (not c.get("pinned", False), c.get("updated", "")),
                   reverse=False)
        # Reverse so: pinned=True (not=False=0) comes before pinned=False (not=True=1)
        # But updated needs newest first... use a tuple that sorts correctly
        chats.sort(key=lambda c: (0 if c.get("pinned") else 1, ""), reverse=False)
        # Simpler: just sort properly
        chats = sorted(chats, key=lambda c: (
            0 if c.get("pinned") else 1,  # pinned first
            c.get("updated", ""),  # newest first within group
        ))
        # Within each group, newest first
        pinned = [c for c in chats if c.get("pinned")]
        unpinned = [c for c in chats if not c.get("pinned")]
        pinned.sort(key=lambda c: c.get("updated", ""), reverse=True)
        unpinned.sort(key=lambda c: c.get("updated", ""), reverse=True)
        return pinned + unpinned

    # === Folders ===

    def create_folder(self, name, pinned=False) -> str:
        fid = _id()
        folder = {"id": fid, "name": name, "pinned": pinned, "created": _now()}
        self._folders["folders"].append(folder)
        self._save_folders()
        return fid

    def delete_folder(self, folder_id):
        self._folders["folders"] = [f for f in self._folders["folders"] if f["id"] != folder_id]
        self._save_folders()
        # Unassign chats from this folder
        for cid, meta in self._index.get("chats", {}).items():
            if meta.get("folder") == folder_id:
                self.update_chat(cid, folder=None)

    def rename_folder(self, folder_id, new_name):
        for f in self._folders["folders"]:
            if f["id"] == folder_id:
                f["name"] = new_name
        self._save_folders()

    def pin_folder(self, folder_id, pinned=True):
        for f in self._folders["folders"]:
            if f["id"] == folder_id:
                f["pinned"] = pinned
        self._save_folders()

    def list_folders(self) -> List[Dict]:
        folders = list(self._folders.get("folders", []))
        folders.sort(key=lambda f: (not f.get("pinned", False), f.get("name", "")))
        return folders

    # === Search & Context Retrieval ===

    def search(self, query, limit=10) -> List[Dict]:
        """Search chats by keyword. Returns chat metadata + snippet."""
        terms = _keywords(query)
        if not terms:
            return []

        scores = defaultdict(int)
        for term in terms:
            for cid in self._index.get("keywords", {}).get(term, []):
                scores[cid] += 1

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
        results = []
        for cid, score in ranked:
            meta = self._index.get("chats", {}).get(cid, {})
            # Get snippet from matching chat
            chat = self.get_chat(cid)
            snippet = ""
            if chat:
                for m in reversed(chat.get("messages", [])):
                    text_lower = m["content"].lower()
                    if any(t in text_lower for t in terms):
                        snippet = m["content"][:150]
                        break
            results.append({"id": cid, "score": score, "snippet": snippet, **meta})
        return results

    def get_context_for_query(self, query, max_chats=3, max_msgs=5) -> str:
        """Build context string from relevant past chats for LLM injection."""
        hits = self.search(query, limit=max_chats)
        if not hits:
            return ""

        parts = ["RELEVANT PAST CONVERSATIONS:"]
        for hit in hits:
            chat = self.get_chat(hit["id"])
            if not chat:
                continue
            parts.append(f"\n--- Chat: {chat['title']} ---")
            for m in chat["messages"][-max_msgs:]:
                role = "Handler" if m["role"] == "handler" else "UMBRA"
                parts.append(f"{role}: {m['content'][:200]}")

        return "\n".join(parts)

    def get_pinned_context(self, max_msgs=3) -> str:
        """Get context from pinned chats for persistent memory."""
        parts = []
        for cid, meta in self._index.get("chats", {}).items():
            if meta.get("pinned"):
                chat = self.get_chat(cid)
                if chat:
                    parts.append(f"[Pinned: {chat['title']}]")
                    for m in chat["messages"][-max_msgs:]:
                        role = "Handler" if m["role"] == "handler" else "UMBRA"
                        parts.append(f"  {role}: {m['content'][:150]}")
        return "\n".join(parts) if parts else ""

    # === Migration: import old handler_conversations.json ===

    def import_legacy(self, legacy_file="data/handler_conversations.json"):
        """Import old single-chat history into the new system."""
        p = Path(legacy_file)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text())
            history = data.get("history", [])
            if not history:
                return None
            cid = self.create_chat(title="Legacy Uplink", folder=None)
            chat = self.get_chat(cid)
            chat["messages"] = history
            chat["pinned"] = True
            chat["updated"] = _now()
            self._chat_path(cid).write_text(json.dumps(chat, indent=1))
            self._index_chat(cid, chat)
            return cid
        except:
            return None

    def rebuild_index(self):
        """Full rebuild of keyword index from all chat files."""
        self._index = {"keywords": {}, "chats": {}}
        for f in self.chats_dir.glob("*.json"):
            try:
                chat = json.loads(f.read_text())
                self._index_chat(chat["id"], chat)
            except:
                continue
        self._save_index()
