"""UMBRA Glass Box // Integrity & Transparency Layer"""
import os, hashlib, json, time
from pathlib import Path

class IntegrityMonitor:
    def __init__(self, root_dir):
        self.root = Path(root_dir)
        self.t_dir = self.root / "transparency"
        self.log_path = self.t_dir / "integrity.json"
        self.cl_path = self.root / "contract" / "CHANGELOG.md"
        self.contract_path = self.root / "contract" / "moral_contract.txt"

    def tree(self, cap=50):
        out = []
        for p in self.root.rglob("*"):
            if p.is_file() and not p.name.startswith(".") and "__pycache__" not in str(p):
                out.append(str(p.relative_to(self.root)))
                if len(out) >= cap: break
        return "\n".join(out)

    def snap(self):
        h = {}
        for d in [self.root / "core", self.root / "contract"]:
            if not d.exists(): continue
            for p in d.rglob("*.py"):
                try:
                    h[str(p.relative_to(self.root))] = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
                except: pass
        return h

    def check(self):
        cur = self.snap()
        hist = self._load_hist()
        if not hist:
            self._log("GENESIS", "v0.8.0 Glass Box - Initial Snapshot", cur)
            return "INTEGRITY: STABLE (Genesis Snapshot Created)"
        diff = []
        prev = hist[-1].get("h", {})
        for f, h in cur.items():
            if f not in prev: diff.append(f"NEW: {f}")
            elif prev[f] != h: diff.append(f"MOD: {f}")
        for f in prev:
            if f not in cur: diff.append(f"DEL: {f}")
        if diff:
            return "⚠️ CODEBASE DIVERGENCE:\n" + "\n".join(diff)
        return "INTEGRITY: VERIFIED ✓"

    def stamp(self, author, note):
        self._log(author, note, self.snap())

    def _load_hist(self):
        if self.log_path.exists():
            try: return json.loads(self.log_path.read_text())
            except: pass
        return []

    def _log(self, author, note, hashes):
        hist = self._load_hist()
        hist.append({"t": time.ctime(), "by": author, "note": note, "h": hashes})
        self.t_dir.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text(json.dumps(hist, indent=2))

    def changelog(self):
        return self.cl_path.read_text(encoding="utf-8") if self.cl_path.exists() else "No changelog."

    def contract(self):
        return self.contract_path.read_text(encoding="utf-8") if self.contract_path.exists() else "⚠ MORAL CONTRACT MISSING."

    def ctx_for_llm(self):
        """Compact context string for injection into LLM prompts"""
        return f"[GLASS BOX] {self.check()}\n[BODY] {len(self.snap())} tracked files"
