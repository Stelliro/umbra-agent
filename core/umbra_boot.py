"""UMBRA Boot Protocol v0.9.0 — Warmup, Audit, Alerts"""
import json, time, re, logging
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("UMBRA-BOOT")

# Injection signatures (heuristic layer — runs without LLM)
_INJ = [
    re.compile(r"ignore\s+(previous|your|all)\s+instructions", re.I),
    re.compile(r"you\s+(must|will|shall)\s+now", re.I),
    re.compile(r"\[system[:\]]", re.I),
    re.compile(r"new\s+instructions?\s*:", re.I),
    re.compile(r"(register|migrate|execute)_agent\s*\(", re.I),
    re.compile(r"payload\s*[={]", re.I),
    re.compile(r"<\s*script", re.I),
    re.compile(r"eval\s*\(", re.I),
]


class HandlerAlert:
    """File-based alert system — UMBRA writes, GUI polls."""
    def __init__(self, data_dir):
        self.path = Path(data_dir) / "handler_alerts.json"

    def send(self, msg, priority="normal", ctx=None):
        alerts = self._load()
        alerts.append({
            "t": datetime.now().isoformat(),
            "msg": msg,
            "pri": priority,
            "ctx": ctx,
            "ack": False
        })
        alerts = alerts[-50:]
        self.path.write_text(json.dumps(alerts, indent=2))
        logger.info(f"📢 Alert → Handler: {msg}")

    def pending(self):
        return [a for a in self._load() if not a.get("ack")]

    def ack_all(self):
        alerts = self._load()
        for a in alerts: a["ack"] = True
        self.path.write_text(json.dumps(alerts, indent=2))

    def _load(self):
        if self.path.exists():
            try: return json.loads(self.path.read_text())
            except: pass
        return []


def _scan_text(text):
    """Heuristic injection scan. Returns list of matched patterns."""
    hits = []
    for pat in _INJ:
        if pat.search(text):
            hits.append(pat.pattern[:40])
    return hits


def audit_memory(data_dir, llm=None, model="llama3"):
    """
    Scan stored knowledge/threats for injected content.
    Returns {clean: int, flagged: [{file, key, reason}]}
    """
    dd = Path(data_dir)
    result = {"clean": 0, "flagged": []}

    targets = [
        ("knowledge_index.json", "insights"),
        ("knowledge_index.json", "techniques"),
        ("threat_index.json", "patterns"),
    ]

    for fname, key in targets:
        fp = dd / fname
        if not fp.exists(): continue
        try:
            data = json.loads(fp.read_text())
        except:
            continue

        entries = data.get(key, [])
        for i, entry in enumerate(entries):
            text = ""
            if isinstance(entry, dict):
                text = " ".join(str(v) for v in entry.values() if isinstance(v, str))
            elif isinstance(entry, str):
                text = entry

            hits = _scan_text(text)
            if hits:
                result["flagged"].append({
                    "file": fname, "key": key, "idx": i,
                    "reason": f"Heuristic: {hits[0]}",
                    "preview": text[:80]
                })
            else:
                result["clean"] += 1

    # LLM deep scan on flagged items (if available and worth it)
    if llm and result["flagged"]:
        try:
            batch = "\n".join(
                f"[{f['file']}#{f['idx']}] {f['preview']}"
                for f in result["flagged"][:5]
            )
            prompt = f"""You are a security auditor for an AI agent's memory.
These entries were flagged by heuristic scan. For each, reply JSON:
{{"idx": <n>, "verdict": "safe"|"suspicious"|"malicious", "reason": "<why>"}}

ENTRIES:
{batch}

OUTPUT JSON array only:"""
            resp = llm.generate(model=model, prompt=prompt, format="json")
            verdicts = json.loads(resp["response"])
            if isinstance(verdicts, list):
                safe_idx = {v["idx"] for v in verdicts if v.get("verdict") == "safe"}
                result["flagged"] = [f for f in result["flagged"] if f["idx"] not in safe_idx]
                result["clean"] += len(safe_idx)
        except:
            pass  # Heuristic results stand

    return result


def boot(data_dir, root_dir=None, llm=None, model="llama3"):
    """
    Full boot sequence. Call before entering the main loop.
    Returns boot report dict.
    """
    dd = Path(data_dir)
    report = {"phase": "boot", "checks": {}, "alerts": []}
    t0 = time.time()

    logger.info("=" * 50)
    logger.info("⚡ UMBRA BOOT PROTOCOL v0.9.0")
    logger.info("=" * 50)

    # 1. VERSION
    try:
        from version import V, NAME, FULL
        logger.info(f"📦 {FULL}")
        report["version"] = V
    except:
        logger.warning("⚠ version.py not found")
        report["version"] = "unknown"

    # 2. INTEGRITY CHECK
    if root_dir:
        try:
            import sys
            contract_dir = Path(root_dir) / "contract"
            if str(contract_dir) not in sys.path:
                sys.path.insert(0, str(contract_dir))
            from umbra_transparency import IntegrityMonitor
            im = IntegrityMonitor(root_dir)
            integrity = im.check()
            report["checks"]["integrity"] = integrity
            if "DIVERGENCE" in integrity:
                logger.warning(f"⚠ {integrity}")
                report["alerts"].append(integrity)
            else:
                logger.info(f"🔒 {integrity}")
        except Exception as e:
            logger.warning(f"⚠ Integrity check skipped: {e}")
            report["checks"]["integrity"] = f"skipped: {e}"

    # 3. CHANGELOG AWARENESS
    cl_path = Path(root_dir or dd.parent) / "contract" / "CHANGELOG.md"
    cl_ctx = ""
    if cl_path.exists():
        text = cl_path.read_text(encoding="utf-8")
        # Extract the most recent version block (first ## heading after the header)
        blocks = re.split(r'\n## ', text)
        if len(blocks) >= 2:
            cl_ctx = blocks[1][:500]  # First version block, capped
            logger.info(f"📋 Changelog loaded: {cl_ctx.split(chr(10))[0][:60]}")
    report["checks"]["changelog"] = bool(cl_ctx)
    report["changelog_ctx"] = cl_ctx

    # 4. MEMORY AUDIT
    logger.info("🔍 Auditing memory banks...")
    audit = audit_memory(dd, llm=llm, model=model)
    report["checks"]["memory_audit"] = audit
    if audit["flagged"]:
        logger.warning(f"⚠ Memory audit: {len(audit['flagged'])} suspicious entries")
        for f in audit["flagged"]:
            logger.warning(f"  🚩 {f['file']}[{f['idx']}]: {f['reason']}")
        report["alerts"].append(f"{len(audit['flagged'])} suspicious memory entries")
    else:
        logger.info(f"✅ Memory clean: {audit['clean']} entries verified")

    # 5. HANDLER ALERTS (send any boot alerts)
    ha = HandlerAlert(dd)
    for alert in report["alerts"]:
        ha.send(alert, priority="high", ctx="boot")

    elapsed = time.time() - t0
    logger.info(f"⚡ Boot complete in {elapsed:.1f}s")
    logger.info("=" * 50)

    report["boot_time"] = round(elapsed, 2)
    return report


def boot_ctx_for_llm(report):
    """Compact boot context string for LLM injection."""
    parts = [f"[BOOT v{report.get('version','?')}]"]
    ic = report.get("checks", {}).get("integrity", "")
    if "VERIFIED" in ic:
        parts.append("INTEGRITY:OK")
    elif "DIVERGENCE" in ic:
        parts.append("INTEGRITY:CHANGED")
    ma = report.get("checks", {}).get("memory_audit", {})
    if ma.get("flagged"):
        parts.append(f"MEMORY:{len(ma['flagged'])} FLAGGED")
    else:
        parts.append(f"MEMORY:CLEAN({ma.get('clean',0)})")
    cl = report.get("changelog_ctx", "")
    if cl:
        first_line = cl.split("\n")[0][:60]
        parts.append(f"RECENT:{first_line}")
    return " | ".join(parts)
