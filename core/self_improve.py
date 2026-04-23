"""
Self-Improve v1.0 — Autonomous Code Improvement Pipeline
==========================================================
UMBRA inspects its own codebase, proposes improvements, writes code,
has judges review it, tests the result, and deploys if accepted.

Pipeline:
  INSPECT  → Scan all project files, identify issues/opportunities
  PROPOSE  → LLM generates improvement proposals (primary agents)
  CODE     → Sub-agents write the actual code changes
  JUDGE    → Panel of 3+ judges review (majority vote)
  SECURITY → Sentinel audit on new code
  TEST     → Launch app, run feelers, take screenshot, verify visually
  DEPLOY   → Apply accepted changes (or reject with reasons)

Triggered by: "Optimize and Improve" button in web UI

Architecture:
  SelfImproveOrchestrator
    ├── FileInspector     (scan project files)
    ├── CodeWriter        (sub-agents write changes)
    ├── JudgePanel        (3+ judges review)
    ├── AppTester         (browser feelers + screenshots)
    └── ImprovementProposal (data class for tracking)
"""
import os, json, time, logging, re, shutil, subprocess, sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("UMBRA-IMPROVE")

# === File patterns to skip ===
SKIP_DIRS = {"__pycache__", ".git", "node_modules", "venv", ".venv",
             "data", "bin", "models", ".mypy_cache", ".pytest_cache"}
SKIP_EXTENSIONS = {".pyc", ".bak", ".backup", ".orig", ".tmp", ".log",
                   ".gguf", ".bin", ".png", ".jpg", ".jpeg", ".gif", ".ico"}
CODE_EXTENSIONS = {".py", ".js", ".html", ".css", ".json", ".yaml", ".yml",
                   ".toml", ".md", ".sh", ".bat"}


# === Data Classes ===

@dataclass
class ImprovementProposal:
    """Tracks one proposed improvement through the pipeline."""
    title: str
    file: str
    description: str
    priority: str = "medium"  # low, medium, high, critical
    effort: str = "medium"    # small, medium, large
    status: str = "proposed"  # proposed → coding → reviewing → accepted/rejected
    code_changes: Optional[Dict] = None
    judge_verdict: Optional[Dict] = None
    test_result: Optional[Dict] = None
    rejection_reason: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return {
            "title": self.title,
            "file": self.file,
            "description": self.description,
            "priority": self.priority,
            "effort": self.effort,
            "status": self.status,
            "rejection_reason": self.rejection_reason,
            "created_at": self.created_at,
        }


@dataclass
class TestVerdict:
    """Result of the AppTester verification."""
    passed: bool
    screenshot: Optional[str] = None
    feeler_results: Optional[Dict] = None
    errors: List[str] = field(default_factory=list)
    details: str = ""


# === FileInspector ===

class FileInspector:
    """Scans the project directory, cataloging all source files."""

    def __init__(self, project_dir: str):
        self.project_dir = Path(project_dir)

    def scan(self) -> List[Dict]:
        """Walk the project tree, return file info for all source files."""
        files = []
        for root, dirs, filenames in os.walk(self.project_dir):
            # Skip blacklisted directories
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]

            for fname in filenames:
                fpath = Path(root) / fname
                ext = fpath.suffix.lower()

                # Skip non-code and blacklisted extensions
                if ext in SKIP_EXTENSIONS:
                    continue
                if ext not in CODE_EXTENSIONS:
                    continue

                try:
                    content = fpath.read_text(encoding='utf-8', errors='replace')
                    lines = content.count('\n') + (1 if content and not content.endswith('\n') else 0)
                    files.append({
                        "path": str(fpath),
                        "relative": str(fpath.relative_to(self.project_dir)),
                        "extension": ext,
                        "lines": lines,
                        "size": fpath.stat().st_size,
                        "functions": self._count_functions(content, ext),
                        "classes": self._count_classes(content, ext),
                    })
                except Exception as e:
                    logger.warning(f"Skipping {fpath}: {e}")

        return files

    def _count_functions(self, content: str, ext: str) -> int:
        if ext == ".py":
            return len(re.findall(r'^    def |^def ', content, re.MULTILINE))
        if ext in (".js", ".ts"):
            return len(re.findall(r'function |=>|async ', content))
        return 0

    def _count_classes(self, content: str, ext: str) -> int:
        if ext == ".py":
            return len(re.findall(r'^class ', content, re.MULTILINE))
        if ext in (".js", ".ts"):
            return len(re.findall(r'class ', content))
        return 0

    def get_file_content(self, relative_path: str) -> str:
        """Read a specific file's content."""
        fpath = self.project_dir / relative_path
        if fpath.exists():
            return fpath.read_text(encoding='utf-8', errors='replace')
        return ""

    def get_summary(self, files: List[Dict]) -> str:
        """Generate a compact summary for LLM context."""
        lines = [f"PROJECT: {self.project_dir.name} ({len(files)} source files)"]
        for f in files:
            lines.append(f"  {f['relative']} ({f['lines']}L, {f['functions']}fn, {f['classes']}cls)")
        return "\n".join(lines)


# === CodeWriter ===

class CodeWriter:
    """Sub-agent that writes actual code changes for a proposal."""

    def __init__(self, ollama, model: str = "llama3"):
        self.ollama = ollama
        self.model = model

    def write(self, proposal: ImprovementProposal, file_content: str) -> Dict:
        """Generate code changes for a proposal."""
        prompt = f"""STAGE: WRITE CODE for an improvement to UMBRA.

IMPROVEMENT: {proposal.title}
DESCRIPTION: {proposal.description}
FILE: {proposal.file}
PRIORITY: {proposal.priority}

CURRENT FILE CONTENT:
```
{file_content[:3000]}
```

Write the code changes needed. Output JSON:
{{
  "file": "{proposal.file}",
  "changes": [
    {{
      "type": "replace",
      "old": "<exact string to find and replace>",
      "new": "<replacement string>",
      "reason": "<why this change>"
    }}
  ],
  "new_imports": ["<any new imports needed>"],
  "test_hint": "<how to verify this works>"
}}

Be precise with the 'old' strings — they must match exactly.
Minimal changes only. Don't rewrite entire files."""

        try:
            resp = self.ollama.generate(model=self.model, prompt=prompt, format="json")
            result = json.loads(resp.get("response", "{}"))
            return result
        except Exception as e:
            logger.error(f"CodeWriter failed: {e}")
            return {"changes": [], "error": str(e)}


# === JudgePanel ===

class JudgePanel:
    """Multiple judge agents review code changes. Majority vote decides."""

    def __init__(self, ollama, model: str = "llama3", num_judges: int = 3):
        self.ollama = ollama
        self.model = model
        self.num_judges = num_judges

    def review(self, proposal_title: str, original_code: str, new_code: str,
               changes_description: str) -> Dict:
        """Run all judges and tally votes."""
        judges = []

        for i in range(self.num_judges):
            verdict = self._single_judge(
                judge_id=i + 1,
                proposal_title=proposal_title,
                original_code=original_code[:2000],
                new_code=new_code[:2000],
                changes_description=changes_description,
            )
            judges.append(verdict)

        # Tally
        accept_count = sum(1 for j in judges if j.get("verdict") == "accept")
        reject_count = sum(1 for j in judges if j.get("verdict") == "reject")
        avg_score = sum(j.get("score", 0.5) for j in judges) / max(len(judges), 1)

        # Majority vote
        if accept_count > self.num_judges / 2:
            final = "accept"
        elif reject_count > self.num_judges / 2:
            final = "reject"
        else:
            final = "revise"

        # Collect all concerns and suggestions
        all_concerns = []
        all_suggestions = []
        all_reasoning = []
        for j in judges:
            all_concerns.extend(j.get("concerns", []))
            all_suggestions.extend(j.get("suggestions", []))
            all_reasoning.append(j.get("reasoning", ""))

        return {
            "verdict": final,
            "score": round(avg_score, 2),
            "accept_count": accept_count,
            "reject_count": reject_count,
            "total_judges": self.num_judges,
            "judges": judges,
            "concerns": all_concerns,
            "suggestions": all_suggestions,
            "reasoning": " | ".join(all_reasoning),
        }

    def _single_judge(self, judge_id: int, proposal_title: str,
                      original_code: str, new_code: str,
                      changes_description: str) -> Dict:
        """One judge reviews the change."""
        prompt = f"""STAGE: JUDGE — You are Judge #{judge_id} reviewing a code change.

PROPOSAL: {proposal_title}
CHANGES: {changes_description}

ORIGINAL CODE (excerpt):
```
{original_code}
```

NEW CODE (excerpt):
```
{new_code}
```

REVIEW CRITERIA:
1. Does this change do what it claims?
2. Could it break existing functionality?
3. Is the code clean and maintainable?
4. Are there security concerns?
5. Is this actually an improvement?

Output JSON:
{{
  "verdict": "accept" or "reject" or "revise",
  "score": <0.0-1.0>,
  "reasoning": "<your reasoning>",
  "concerns": ["<any concerns>"],
  "suggestions": ["<improvements>"]
}}"""

        try:
            resp = self.ollama.generate(model=self.model, prompt=prompt, format="json")
            result = json.loads(resp.get("response", "{}"))
            result["judge_id"] = judge_id
            return result
        except Exception as e:
            return {"judge_id": judge_id, "verdict": "revise",
                    "score": 0.5, "reasoning": f"Judge error: {e}",
                    "concerns": [str(e)], "suggestions": []}


# === AppTester ===

class AppTester:
    """Tests the application using the browser agent — feelers + screenshots."""

    def __init__(self, browser=None, app_url: str = "http://localhost:5000"):
        self.browser = browser
        self.app_url = app_url

    def run_feelers(self, checks: List[Dict]) -> Dict:
        """Run a list of feeler checks: each has a selector and description."""
        results = {"passed": 0, "failed": 0, "total": len(checks), "details": []}

        for check in checks:
            selector = check["selector"]
            desc = check.get("description", selector)
            exists = self.browser.feel_exists(selector) if self.browser else False

            detail = {
                "selector": selector,
                "description": desc,
                "found": exists,
            }
            results["details"].append(detail)

            if exists:
                results["passed"] += 1
            else:
                results["failed"] += 1
                logger.warning(f"Feeler FAIL: {desc} ({selector})")

        return results

    def take_verification_screenshot(self, name: str) -> Dict:
        """Take a screenshot for visual verification."""
        if not self.browser:
            return {"path": None, "error": "No browser available"}

        path = self.browser.screenshot(name)
        return {"path": path, "timestamp": time.time()}

    def full_test(self, url: str = None, expected_elements: List[str] = None,
                  screenshot_name: str = "verification") -> TestVerdict:
        """
        Full test: navigate to URL, run feelers, take screenshot.
        Returns TestVerdict with pass/fail.
        """
        url = url or self.app_url
        expected_elements = expected_elements or ["button", "nav", "a"]
        errors = []

        # Navigate
        if self.browser:
            try:
                self.browser.navigate(url)
            except Exception as e:
                return TestVerdict(passed=False, errors=[f"Navigation failed: {e}"])

        # Run feelers
        checks = [{"selector": sel, "description": f"{sel} exists"} for sel in expected_elements]
        feeler_results = self.run_feelers(checks)

        if feeler_results["failed"] > 0:
            missing = [d["selector"] for d in feeler_results["details"] if not d["found"]]
            errors.append(f"Missing elements: {missing}")

        # Screenshot
        ss = self.take_verification_screenshot(screenshot_name)

        # Verdict: pass if >80% of feelers pass and no critical errors
        pass_rate = feeler_results["passed"] / max(feeler_results["total"], 1)
        passed = pass_rate >= 0.8 and len(errors) == 0

        return TestVerdict(
            passed=passed,
            screenshot=ss.get("path"),
            feeler_results=feeler_results,
            errors=errors,
            details=f"Feelers: {feeler_results['passed']}/{feeler_results['total']} passed"
        )

    def launch_and_test(self, project_dir: str, expected_elements: List[str] = None,
                        timeout: int = 10) -> TestVerdict:
        """
        Actually launch the application as a subprocess, wait for it to start,
        then test it. Returns TestVerdict.
        """
        # Start the app
        proc = None
        try:
            proc = subprocess.Popen(
                [sys.executable, "umbra_web.py"],
                cwd=project_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            time.sleep(timeout)

            if proc.poll() is not None:
                stderr = proc.stderr.read().decode()
                return TestVerdict(passed=False, errors=[f"App crashed: {stderr[:500]}"])

            # App is running — test it
            return self.full_test(expected_elements=expected_elements,
                                  screenshot_name="launch_test")

        except Exception as e:
            return TestVerdict(passed=False, errors=[f"Launch failed: {e}"])
        finally:
            if proc and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except:
                    proc.kill()


# === Orchestrator ===

class SelfImproveOrchestrator:
    """
    Master controller for the self-improvement pipeline.
    Triggered by the 'Optimize and Improve' button.
    """

    def __init__(self, project_dir: str, ollama=None, model: str = "llama3",
                 browser=None, max_proposals: int = 5):
        self.project_dir = project_dir
        self.ollama = ollama
        self.model = model
        self.browser = browser
        self.max_proposals = max_proposals

        self.inspector = FileInspector(project_dir)
        self.writer = CodeWriter(ollama, model) if ollama else None
        self.judges = JudgePanel(ollama, model) if ollama else None
        self.tester = AppTester(browser) if browser else None

        self._files: List[Dict] = []
        self._proposals: List[ImprovementProposal] = []
        self._status = "idle"  # idle, inspecting, proposing, coding, judging, testing, complete
        self._log: List[Dict] = []

    def _log_event(self, phase: str, message: str, data: Dict = None):
        self._log.append({
            "phase": phase,
            "message": message,
            "data": data or {},
            "time": time.time(),
        })
        logger.info(f"[{phase.upper()}] {message}")

    # === Phase 1: Inspect ===

    def inspect(self) -> Dict:
        """Scan all project files."""
        self._status = "inspecting"
        self._files = self.inspector.scan()
        summary = self.inspector.get_summary(self._files)
        self._log_event("inspect", f"Scanned {len(self._files)} files")

        report = {
            "files": self._files,
            "summary": summary,
            "total_lines": sum(f["lines"] for f in self._files),
            "total_functions": sum(f["functions"] for f in self._files),
            "total_classes": sum(f["classes"] for f in self._files),
        }
        return report

    # === Phase 2: Propose ===

    def propose(self) -> List[ImprovementProposal]:
        """Use LLM to analyze the codebase and propose improvements."""
        self._status = "proposing"

        if not self.ollama:
            self._log_event("propose", "No LLM available")
            return []

        summary = self.inspector.get_summary(self._files)

        # Ask LLM to analyze and propose
        prompt = f"""STAGE: INSPECT and PROPOSE improvements to the UMBRA codebase.

{summary}

Analyze this project structure. Identify:
1. Bugs or potential issues
2. Missing error handling
3. Performance improvements
4. Missing features that would improve reliability
5. Code organization issues
6. Unnecessary or dead code to remove

Propose up to {self.max_proposals} concrete improvements.

Output JSON:
{{
  "files_analyzed": <count>,
  "issues": [
    {{"file": "<filename>", "issue": "<description>", "severity": "low|medium|high|critical"}}
  ],
  "improvements": [
    {{
      "title": "<short title>",
      "priority": "low|medium|high|critical",
      "effort": "small|medium|large",
      "description": "<what to do, specifically>",
      "file": "<primary file to change>"
    }}
  ]
}}"""

        try:
            resp = self.ollama.generate(model=self.model, prompt=prompt, format="json")
            analysis = json.loads(resp.get("response", "{}"))
        except Exception as e:
            self._log_event("propose", f"Analysis failed: {e}")
            return []

        # Convert to proposals
        improvements = analysis.get("improvements", [])[:self.max_proposals]
        self._proposals = []

        for imp in improvements:
            proposal = ImprovementProposal(
                title=imp.get("title", "Untitled"),
                file=imp.get("file", "unknown"),
                description=imp.get("description", ""),
                priority=imp.get("priority", "medium"),
                effort=imp.get("effort", "medium"),
            )
            self._proposals.append(proposal)

        self._log_event("propose", f"Generated {len(self._proposals)} proposals")
        return self._proposals

    # === Phase 3-6: Process each proposal ===

    def _process_proposal(self, proposal: ImprovementProposal) -> Dict:
        """Run a single proposal through the code → judge → test pipeline."""
        result = {
            "title": proposal.title,
            "file": proposal.file,
            "priority": proposal.priority,
        }

        # Phase 3: Write code
        proposal.status = "coding"
        file_content = self.inspector.get_file_content(proposal.file)
        if not file_content:
            proposal.status = "rejected"
            proposal.rejection_reason = f"File not found: {proposal.file}"
            result["verdict"] = "rejected"
            result["reason"] = proposal.rejection_reason
            return result

        if not self.writer:
            proposal.status = "rejected"
            proposal.rejection_reason = "No LLM available for code writing"
            result["verdict"] = "rejected"
            result["reason"] = proposal.rejection_reason
            return result

        code_result = self.writer.write(proposal, file_content)
        proposal.code_changes = code_result
        changes = code_result.get("changes", [])

        if not changes:
            proposal.status = "rejected"
            proposal.rejection_reason = "CodeWriter produced no changes"
            result["verdict"] = "rejected"
            result["reason"] = proposal.rejection_reason
            return result

        # Apply changes to get new code (in memory only)
        new_code = file_content
        for change in changes:
            if change.get("type") == "replace" and change.get("old"):
                new_code = new_code.replace(change["old"], change.get("new", ""), 1)

        result["changes_count"] = len(changes)
        self._log_event("code", f"Wrote {len(changes)} changes for '{proposal.title}'")

        # Phase 4: Judge review
        proposal.status = "reviewing"
        if self.judges:
            changes_desc = "\n".join(
                f"- {c.get('reason', 'change')}" for c in changes
            )
            judge_verdict = self.judges.review(
                proposal_title=proposal.title,
                original_code=file_content[:2000],
                new_code=new_code[:2000],
                changes_description=changes_desc,
            )
            proposal.judge_verdict = judge_verdict
            result["judge_verdict"] = judge_verdict["verdict"]
            result["judge_score"] = judge_verdict["score"]
            result["judge_reasoning"] = judge_verdict["reasoning"]

            if judge_verdict["verdict"] == "reject":
                proposal.status = "rejected"
                proposal.rejection_reason = f"Judges rejected: {judge_verdict['reasoning'][:200]}"
                result["verdict"] = "rejected"
                result["reason"] = proposal.rejection_reason
                return result

            self._log_event("judge", f"Judges: {judge_verdict['verdict']} "
                            f"({judge_verdict['accept_count']}/{judge_verdict['total_judges']})")

        # Phase 5: Test (if browser available)
        if self.tester:
            test_result = self.tester.full_test(
                expected_elements=["button", "nav"],
                screenshot_name=f"test_{proposal.title.replace(' ', '_')[:20]}"
            )
            proposal.test_result = {
                "passed": test_result.passed,
                "details": test_result.details,
                "errors": test_result.errors,
            }
            result["test_passed"] = test_result.passed
            result["test_screenshot"] = test_result.screenshot

            if not test_result.passed:
                proposal.status = "rejected"
                proposal.rejection_reason = f"Test failed: {test_result.errors}"
                result["verdict"] = "rejected"
                result["reason"] = proposal.rejection_reason
                return result

        # Phase 6: Accept
        proposal.status = "accepted"
        result["verdict"] = "accepted"
        result["new_code_preview"] = new_code[:500]
        self._log_event("accept", f"Accepted: '{proposal.title}'")

        return result

    # === Master Run ===

    def run(self, auto_deploy: bool = False) -> Dict:
        """
        Full self-improvement cycle.
        Returns complete report of everything that happened.
        """
        report = {
            "started": time.time(),
            "inspection": None,
            "proposals": [],
            "results": [],
            "deployed": [],
            "status": "running",
        }

        try:
            # Phase 1: Inspect
            report["inspection"] = self.inspect()

            # Phase 2: Propose
            proposals = self.propose()
            report["proposals"] = [p.to_dict() for p in proposals]

            if not proposals:
                report["status"] = "no_proposals"
                return report

            # Phase 3-6: Process each proposal
            for proposal in proposals:
                result = self._process_proposal(proposal)
                report["results"].append(result)

                # Phase 7: Deploy if accepted and auto_deploy is on
                if auto_deploy and result.get("verdict") == "accepted":
                    self._deploy(proposal)
                    report["deployed"].append(proposal.title)

            report["status"] = "complete"
            accepted = sum(1 for r in report["results"] if r.get("verdict") == "accepted")
            rejected = sum(1 for r in report["results"] if r.get("verdict") == "rejected")
            self._log_event("complete",
                            f"Pipeline done: {accepted} accepted, {rejected} rejected")

        except Exception as e:
            report["status"] = "error"
            report["error"] = str(e)
            self._log_event("error", str(e))

        report["elapsed"] = round(time.time() - report["started"], 2)
        return report

    def _deploy(self, proposal: ImprovementProposal):
        """Apply accepted changes to the actual file."""
        if not proposal.code_changes:
            return

        filepath = Path(self.project_dir) / proposal.file
        if not filepath.exists():
            return

        # Backup first
        backup_dir = Path(self.project_dir) / "data" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(filepath, backup_dir / f"{filepath.name}.{ts}.bak")

        # Apply changes
        content = filepath.read_text(encoding='utf-8', errors='replace')
        for change in proposal.code_changes.get("changes", []):
            if change.get("type") == "replace" and change.get("old"):
                content = content.replace(change["old"], change.get("new", ""), 1)

        filepath.write_text(content, encoding='utf-8')
        self._log_event("deploy", f"Deployed: '{proposal.title}' → {proposal.file}")

    # === Status ===

    def status(self) -> Dict:
        return {
            "phase": self._status,
            "files_scanned": len(self._files),
            "proposals": len(self._proposals),
            "accepted": sum(1 for p in self._proposals if p.status == "accepted"),
            "rejected": sum(1 for p in self._proposals if p.status == "rejected"),
            "log": self._log[-10:],
        }
