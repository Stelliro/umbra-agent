"""
Startup Sequence v1.0 — Autonomous Boot-to-Action
==================================================
When UMBRA starts, it doesn't immediately browse. Instead:

1. BOOT     — Run integrity checks (umbra_boot)
2. INDEX    — Rebuild chat index, scan knowledge/threat files
3. EVALUATE — Self-assessment: what do I know? what's changed? what's pending?
4. PLAN     — LLM decides what to do: research, self-edit, reflect, train, or idle
5. EXECUTE  — Begin the chosen action

The Sentinel runs a security scan during boot.
UMBRA can discuss what it's researching during any phase.
"""
import json, time, logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, List
from enum import Enum

logger = logging.getLogger("UMBRA-STARTUP")


class StartupPhase(Enum):
    BOOT = "boot"
    INDEX = "index"
    EVALUATE = "evaluate"
    PLAN = "plan"
    EXECUTE = "execute"
    IDLE = "idle"


class StartupAction(Enum):
    BROWSE = "browse"          # Legacy (disabled in local-only mode)
    POST = "post"              # Legacy (disabled in local-only mode)
    RESEARCH = "research"      # Deep dive into a topic
    SELF_EDIT = "self_edit"    # Code agent edits own source
    REFLECT = "reflect"        # Review past actions, learn
    TRAIN = "train"            # Run Sentinel Red/Blue challenge
    IDLE = "idle"              # Wait for handler input


class StartupSequence:
    """
    Manages UMBRA's boot-to-action pipeline.
    Each phase produces a report. LLM decides the action at the end.
    """
    def __init__(self, data_dir="data", ollama=None, model="llama3"):
        self.data_dir = Path(data_dir)
        self.ollama = ollama
        self.model = model
        self.phase = StartupPhase.BOOT
        self.report = {}
        self.chosen_action = None
        self.research_topic = None
        self._start_time = time.time()

    # === Phase 1: BOOT ===

    def run_boot(self, boot_module=None) -> Dict:
        """Run integrity checks via umbra_boot."""
        self.phase = StartupPhase.BOOT
        logger.info("🔄 Phase 1: BOOT — integrity checks")
        result = {"phase": "boot", "status": "ok", "issues": []}

        if boot_module:
            try:
                ctx = boot_module.run_boot(str(self.data_dir.parent))
                result["boot_context"] = ctx
                if "FLAGGED" in ctx:
                    result["status"] = "warning"
                    result["issues"].append("Memory audit found flagged entries")
                logger.info(f"  Boot: {ctx[:80]}")
            except Exception as e:
                result["status"] = "error"
                result["issues"].append(str(e))

        self.report["boot"] = result
        return result

    # === Phase 2: INDEX ===

    def run_index(self, chat_store=None, code_agent=None) -> Dict:
        """Rebuild indexes, scan project files."""
        self.phase = StartupPhase.INDEX
        logger.info("🔄 Phase 2: INDEX — rebuilding indexes")
        result = {"phase": "index", "chats": 0, "files": 0, "knowledge": 0, "threats": 0}

        # Chat index
        if chat_store:
            chat_store.rebuild_index()
            result["chats"] = len(chat_store.list_chats())
            logger.info(f"  Chats indexed: {result['chats']}")

        # Project files
        if code_agent:
            result["files"] = len(code_agent.list_files())
            logger.info(f"  Project files: {result['files']}")

        # Knowledge index
        ki = self.data_dir / "knowledge_index.json"
        if ki.exists():
            try:
                data = json.loads(ki.read_text())
                result["knowledge"] = len(data.get("insights", []))
            except: pass

        # Threat index
        ti = self.data_dir / "threat_index.json"
        if ti.exists():
            try:
                data = json.loads(ti.read_text())
                result["threats"] = len(data.get("patterns", []))
            except: pass

        logger.info(f"  Knowledge: {result['knowledge']} insights, {result['threats']} threats")
        self.report["index"] = result
        return result

    # === Phase 3: EVALUATE ===

    def run_evaluate(self, sentinel=None) -> Dict:
        """Self-assessment. What's changed since last run? Any pending items?"""
        self.phase = StartupPhase.EVALUATE
        logger.info("🔄 Phase 3: EVALUATE — self-assessment")
        result = {"phase": "evaluate", "findings": [], "sentinel_scan": None}

        # Check recent activity
        log_dir = self.data_dir / "logs"
        if log_dir.exists():
            logs = sorted(log_dir.glob("*.log"), key=lambda f: f.stat().st_mtime, reverse=True)
            if logs:
                try:
                    last_log = logs[0].read_text(encoding='utf-8', errors='replace')
                    lines = last_log.strip().split("\n")
                    if lines:
                        result["last_activity"] = lines[-1][:200]
                        # Check for errors
                        errors = [l for l in lines[-50:] if "ERROR" in l]
                        if errors:
                            result["findings"].append(f"{len(errors)} errors in last session")
                except: pass

        # Check pending alerts
        alerts_file = self.data_dir / "handler_alerts.json"
        if alerts_file.exists():
            try:
                alerts = json.loads(alerts_file.read_text())
                unacked = [a for a in alerts if not a.get("ack")]
                if unacked:
                    result["findings"].append(f"{len(unacked)} unacknowledged alerts")
            except: pass

        # Check pending code edits
        backups_dir = self.data_dir / "backups"
        if backups_dir.exists():
            edit_log = backups_dir / "edit_log.json"
            if edit_log.exists():
                try:
                    data = json.loads(edit_log.read_text())
                    recent = [e for e in data.get("edits", [])
                              if e.get("timestamp", "") > datetime.now().strftime("%Y-%m-%d")]
                    if recent:
                        result["findings"].append(f"{len(recent)} code edits today")
                except: pass

        # Sentinel security scan
        if sentinel:
            scan = sentinel.run_blue_scan(
                [str(f) for f in (self.data_dir.parent).glob("*.py")][:10]
            )
            result["sentinel_scan"] = {
                "files": scan["files_scanned"],
                "threats": len(scan["threats_found"]),
                "clean": scan["clean"],
            }
            if not scan["clean"]:
                result["findings"].append(f"Sentinel: {len(scan['threats_found'])} code threats")
            logger.info(f"  Sentinel: {scan['files_scanned']} files, {'clean' if scan['clean'] else 'THREATS FOUND'}")

        logger.info(f"  Findings: {result['findings'] or 'none'}")
        self.report["evaluate"] = result
        return result

    # === Phase 4: PLAN ===

    def run_plan(self) -> Dict:
        """LLM decides what to do based on all gathered info."""
        self.phase = StartupPhase.PLAN
        logger.info("🔄 Phase 4: PLAN — deciding action")

        result = {"phase": "plan", "action": "reflect", "reason": "", "topic": None}

        if not self.ollama:
            result["reason"] = "No LLM available, defaulting to local reflection"
            self.chosen_action = StartupAction.REFLECT
            self.report["plan"] = result
            return result

        # Build context for planning
        summary = json.dumps(self.report, indent=1, default=str)[:2000]

        prompt = f"""You are UMBRA-734, an autonomous AI agent starting up.
Here is your startup report:
{summary}

Based on this information, decide what to do first.

Options:
- "research": Deep dive into a specific topic (specify which)
- "self_edit": Review and improve your own code
- "reflect": Review past actions and learn from them
- "train": Run a security training challenge with the Sentinel
- "idle": Wait for handler input

Consider:
- If there are unresolved errors → self_edit or reflect
- If knowledge is low → research
- If threats were found → train
- If everything is clean → reflect or research
- If you have a topic you want to explore → research

Respond in JSON only:
{{
  "action": "<one of the options above>",
  "reason": "<1-2 sentences explaining why>",
  "topic": "<research topic if action is research, null otherwise>",
  "confidence": <0.0-1.0>
}}"""

        try:
            resp = self.ollama.generate(model=self.model, prompt=prompt, format="json")
            text = resp.get("response", "{}")
            if text.startswith("```"):
                text = text.split("```")[1]
                if text.startswith("json"): text = text[4:]
                text = text.strip()
            plan = json.loads(text)

            action_str = plan.get("action", "reflect")
            try:
                self.chosen_action = StartupAction(action_str)
            except ValueError:
                self.chosen_action = StartupAction.REFLECT

            self.research_topic = plan.get("topic")
            result["action"] = action_str
            result["reason"] = plan.get("reason", "")
            result["topic"] = self.research_topic
            result["confidence"] = plan.get("confidence", 0.5)

        except Exception as e:
            result["reason"] = f"Planning error: {e}, defaulting to browse"
            self.chosen_action = StartupAction.BROWSE

        logger.info(f"  Decision: {result['action']} — {result['reason'][:100]}")
        self.report["plan"] = result
        return result

    # === Phase 5: EXECUTE ===

    def get_action(self) -> StartupAction:
        """Return the chosen action after planning."""
        return self.chosen_action or StartupAction.REFLECT

    # === Full Sequence ===

    def run_full(self, boot_module=None, chat_store=None, code_agent=None,
                 sentinel=None) -> Dict:
        """Run the complete startup sequence."""
        logger.info("=" * 40)
        logger.info("UMBRA STARTUP SEQUENCE")
        logger.info("=" * 40)

        self.run_boot(boot_module)
        self.run_index(chat_store, code_agent)
        self.run_evaluate(sentinel)
        self.run_plan()

        elapsed = time.time() - self._start_time
        self.report["elapsed"] = round(elapsed, 1)
        self.report["chosen_action"] = self.get_action().value

        logger.info(f"{'='*40}")
        logger.info(f"STARTUP COMPLETE ({elapsed:.1f}s) → {self.get_action().value}")
        logger.info(f"{'='*40}")

        # Save startup report
        report_file = self.data_dir / "last_startup.json"
        report_file.write_text(json.dumps(self.report, indent=1, default=str))

        return self.report

    # === Chat interface ===

    def get_status_message(self) -> str:
        """Human-readable status for chat display."""
        if self.phase == StartupPhase.BOOT:
            return "Running integrity checks..."
        elif self.phase == StartupPhase.INDEX:
            return "Indexing chats, files, and knowledge..."
        elif self.phase == StartupPhase.EVALUATE:
            return "Self-evaluating recent activity..."
        elif self.phase == StartupPhase.PLAN:
            return "Deciding what to do..."
        elif self.phase == StartupPhase.EXECUTE:
            action = self.get_action()
            if action == StartupAction.RESEARCH and self.research_topic:
                return f"Researching: {self.research_topic}"
            return f"Action: {action.value}"
        return "Idle"

    def can_discuss_research(self) -> bool:
        return self.research_topic is not None

    def get_research_context(self) -> str:
        """Context about current research for chat."""
        if not self.research_topic:
            return ""
        return f"UMBRA is currently researching: {self.research_topic}\nDiscuss findings or ask questions about this topic."
