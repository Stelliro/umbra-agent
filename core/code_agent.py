"""
Code Agent v2.0 — Project Explorer Edition
===========================================
Back-end logic for file browsing, reading, and project root switching.
"""
import json, os, re, shutil, time, logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger("UMBRA-AGENT")

FORBIDDEN_DIRS = {"contract", ".git", "__pycache__", "node_modules", ".svn", ".hg"}
PROTECTED_FILES = {"umbra_autonomous.py", "umbra_web.py", "umbra_engine.py", "phoenix_council.py"}
MAX_FILE_SIZE = 500_000

class CodeAgent:
    def __init__(self, project_dir=".", ollama=None, model="qwen2.5-coder", backup_dir=None):
        self.project = Path(project_dir).resolve()
        self.ollama = ollama
        self.model = model
        self.backup_dir = Path(backup_dir or self.project / "data" / "backups")
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.edit_log_file = self.backup_dir / "edit_log.json"
        self._edit_log = self._load_log()
        self.pending_edits = []

    def set_root(self, new_path):
        """Switch the active project root."""
        p = Path(new_path).resolve()
        if not p.exists():
            return {"error": f"Path does not exist: {new_path}"}
        if not p.is_dir():
            return {"error": "Path is not a directory"}
        self.project = p
        return {"success": True, "root": str(self.project)}

    def browse(self, rel_path="."):
        """List files and folders."""
        try:
            target = (self.project / rel_path).resolve()
            if not target.exists():
                return {"error": "Path not found"}
            
            items = []
            for item in target.iterdir():
                try:
                    if item.name.startswith('.') or item.name in FORBIDDEN_DIRS:
                        continue
                    stats = item.stat()
                    items.append({
                        "name": item.name,
                        "type": "dir" if item.is_dir() else "file",
                        "size": stats.st_size if item.is_file() else 0,
                        "mtime": datetime.fromtimestamp(stats.st_mtime).strftime("%Y-%m-%d %H:%M")
                    })
                except PermissionError:
                    continue
            
            # Sort: Directories first, then files
            items.sort(key=lambda x: (x["type"] != "dir", x["name"].lower()))
            
            return {
                "current": str(rel_path),
                "abs_path": str(target),
                "items": items
            }
        except Exception as e:
            return {"error": str(e)}

    def read_file(self, rel_path):
        try:
            p = (self.project / rel_path).resolve()
            if not p.exists(): return None
            if p.stat().st_size > MAX_FILE_SIZE: return "<< FILE TOO LARGE >>"
            return p.read_text(encoding='utf-8', errors='replace')
        except Exception: return None

    def _load_log(self):
        if self.edit_log_file.exists():
            try: return json.loads(self.edit_log_file.read_text())
            except: pass
        return {"edits": []}
    
    def get_edit_history(self):
        return self._edit_log.get("edits", [])

    def analyze(self, rel_path):
        # Placeholder for actual analysis logic
        return {"status": "Analysis simulation", "file": rel_path}

    def list_files(self): return [] # Legacy support
