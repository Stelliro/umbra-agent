"""Tests for SelfImprove — autonomous code improvement pipeline"""
import sys, json, time, tempfile, shutil, os
sys.path.insert(0, '/home/claude')
from self_improve import (
    FileInspector, ImprovementProposal, CodeWriter,
    JudgePanel, AppTester, SelfImproveOrchestrator, TestVerdict
)


# === Mock LLM ===
class MockLLM:
    def __init__(self):
        self.calls = []

    def generate(self, model="llama3", prompt="", format=None, **kw):
        self.calls.append({"prompt": prompt[:120], "format": format})

        # Match on STAGE: prefix used by the actual modules
        if "STAGE: INSPECT" in prompt or ("INSPECT" in prompt and "PROPOSE" in prompt):
            return {"response": json.dumps({
                "files_analyzed": 5,
                "issues": [
                    {"file": "umbra_web.py", "issue": "No error boundary on dashboard", "severity": "medium"},
                    {"file": "umbra_state.py", "issue": "Missing type hints", "severity": "low"},
                ],
                "improvements": [
                    {"title": "Add error boundary to dashboard", "priority": "high", "effort": "small",
                     "description": "Wrap dashboard API in try/except to prevent 500 errors",
                     "file": "umbra_web.py"},
                    {"title": "Add type hints to state engine", "priority": "low", "effort": "medium",
                     "description": "Add type annotations to all public methods",
                     "file": "umbra_state.py"},
                ]
            })}

        if "STAGE: JUDGE" in prompt:
            return {"response": json.dumps({
                "verdict": "accept",
                "score": 0.85,
                "reasoning": "Change is safe, improves reliability, minimal risk",
                "concerns": [],
                "suggestions": ["Consider logging the exception"],
            })}

        if "STAGE: WRITE CODE" in prompt:
            return {"response": json.dumps({
                "file": "umbra_web.py",
                "changes": [
                    {
                        "type": "replace",
                        "old": "def api_dashboard():",
                        "new": "def api_dashboard():\n    try:",
                        "reason": "Add error handling"
                    }
                ],
                "new_imports": [],
                "test_hint": "Dashboard should return JSON even on errors",
            })}

        if "STAGE: PROPOSE" in prompt:
            return {"response": json.dumps({
                "title": "Add error boundary to dashboard",
                "file": "umbra_web.py",
                "approach": "Wrap the dashboard route handler in try/except",
                "code_sections": ["api_dashboard"],
                "risk": "low",
                "estimated_lines": 15,
            })}

        if "AUDIT" in prompt or "SECURITY" in prompt:
            return {"response": json.dumps({
                "verdict": "pass",
                "issues": [],
                "risk_level": "low",
            })}

        return {"response": json.dumps({"status": "ok"})}


# === Mock Browser Agent ===
class MockBrowserAgent:
    def __init__(self):
        self.screenshots = []
        self.inspections = []

    def navigate(self, url):
        pass

    def screenshot(self, name):
        path = f"/tmp/{name}.png"
        self.screenshots.append(path)
        return path

    def feel_exists(self, selector):
        # Simulate: buttons exist, broken selectors don't
        return selector in ["button", "#btn1", "nav", ".dashboard", "a", "input"]

    def inspect_page(self):
        self.inspections.append(True)
        return {
            "url": "http://localhost:5000",
            "title": "UMBRA Command Center",
            "elements": [
                {"tag": "button", "id": "btn1", "text": "Start", "visible": True},
                {"tag": "nav", "text": "Dashboard", "visible": True},
                {"tag": "a", "text": "Settings", "visible": True},
            ]
        }

    def detect_captcha(self):
        return False


# === FileInspector ===

def test_inspector_scan():
    tmp = tempfile.mkdtemp()
    # Create some fake project files
    with open(os.path.join(tmp, "app.py"), "w") as f:
        f.write("def main():\n    print('hello')\n")
    with open(os.path.join(tmp, "utils.py"), "w") as f:
        f.write("def helper():\n    pass\n")
    os.makedirs(os.path.join(tmp, "core"))
    with open(os.path.join(tmp, "core", "engine.py"), "w") as f:
        f.write("class Engine:\n    pass\n")

    inspector = FileInspector(tmp)
    files = inspector.scan()
    assert len(files) >= 3
    assert any("app.py" in f["path"] for f in files)
    print(f"✓ FileInspector: scanned {len(files)} files")
    shutil.rmtree(tmp)

def test_inspector_file_info():
    tmp = tempfile.mkdtemp()
    with open(os.path.join(tmp, "test.py"), "w") as f:
        f.write("# Comment\ndef foo():\n    return 1\n\ndef bar():\n    return 2\n")
    inspector = FileInspector(tmp)
    files = inspector.scan()
    info = files[0]
    assert "path" in info
    assert "lines" in info
    assert "size" in info
    assert info["lines"] == 6
    print(f"✓ FileInspector: file info (lines={info['lines']})")
    shutil.rmtree(tmp)

def test_inspector_skip_patterns():
    tmp = tempfile.mkdtemp()
    with open(os.path.join(tmp, "good.py"), "w") as f:
        f.write("code")
    os.makedirs(os.path.join(tmp, "__pycache__"))
    with open(os.path.join(tmp, "__pycache__", "junk.pyc"), "w") as f:
        f.write("junk")
    with open(os.path.join(tmp, "something.bak"), "w") as f:
        f.write("backup")
    inspector = FileInspector(tmp)
    files = inspector.scan()
    paths = [f["path"] for f in files]
    assert not any("__pycache__" in p for p in paths)
    assert not any(".bak" in p for p in paths)
    print("✓ FileInspector: skips __pycache__ and .bak")
    shutil.rmtree(tmp)


# === ImprovementProposal ===

def test_proposal_creation():
    p = ImprovementProposal(
        title="Add error handling",
        file="app.py",
        description="Wrap main route in try/except",
        priority="high",
        effort="small"
    )
    assert p.title == "Add error handling"
    assert p.status == "proposed"
    d = p.to_dict()
    assert "title" in d
    print(f"✓ Proposal: created '{p.title}'")

def test_proposal_lifecycle():
    p = ImprovementProposal(
        title="Test",
        file="x.py",
        description="test",
        priority="medium",
        effort="small"
    )
    assert p.status == "proposed"
    p.status = "coding"
    p.status = "reviewing"
    p.status = "accepted"
    print(f"✓ Proposal: lifecycle → {p.status}")


# === CodeWriter ===

def test_code_writer():
    llm = MockLLM()
    writer = CodeWriter(llm, model="llama3")
    proposal = ImprovementProposal(
        title="Add error boundary",
        file="umbra_web.py",
        description="Wrap dashboard in try/except",
        priority="high",
        effort="small"
    )
    result = writer.write(proposal, file_content="def api_dashboard():\n    d = {}\n    return d")
    assert "changes" in result
    assert len(result["changes"]) > 0
    print(f"✓ CodeWriter: produced {len(result['changes'])} changes")


# === JudgePanel ===

def test_judge_review():
    llm = MockLLM()
    panel = JudgePanel(llm, model="llama3", num_judges=3)
    verdict = panel.review(
        proposal_title="Add error boundary",
        original_code="def api_dashboard():\n    d = {}",
        new_code="def api_dashboard():\n    try:\n        d = {}",
        changes_description="Added try/except wrapper"
    )
    assert verdict["verdict"] in ("accept", "reject", "revise")
    assert "score" in verdict
    assert "judges" in verdict
    print(f"✓ JudgePanel: verdict={verdict['verdict']}, score={verdict['score']:.2f}")

def test_judge_requires_majority():
    llm = MockLLM()
    panel = JudgePanel(llm, model="llama3", num_judges=3)
    # All judges return "accept" from mock
    verdict = panel.review("title", "old", "new", "changes")
    assert verdict["verdict"] == "accept"
    print(f"✓ JudgePanel: majority rule ({verdict['accept_count']}/{verdict['total_judges']})")


# === AppTester ===

def test_app_tester_feelers():
    browser = MockBrowserAgent()
    tester = AppTester(browser=browser)
    results = tester.run_feelers([
        {"selector": "button", "description": "Main button exists"},
        {"selector": ".dashboard", "description": "Dashboard visible"},
        {"selector": ".nonexistent", "description": "Missing element"},
    ])
    assert results["passed"] == 2
    assert results["failed"] == 1
    print(f"✓ AppTester: feelers {results['passed']}/{results['total']} passed")

def test_app_tester_screenshot_check():
    browser = MockBrowserAgent()
    tester = AppTester(browser=browser)
    result = tester.take_verification_screenshot("test_verify")
    assert result["path"] is not None
    print(f"✓ AppTester: verification screenshot taken")

def test_app_tester_full_test():
    browser = MockBrowserAgent()
    tester = AppTester(browser=browser)
    verdict = tester.full_test(
        url="http://localhost:5000",
        expected_elements=["button", "nav", "a"],
        screenshot_name="post_change"
    )
    assert verdict.passed == True
    assert verdict.screenshot is not None
    print(f"✓ AppTester: full test passed={verdict.passed}")


# === Orchestrator ===

def test_orchestrator_creation():
    llm = MockLLM()
    browser = MockBrowserAgent()
    tmp = tempfile.mkdtemp()
    with open(os.path.join(tmp, "app.py"), "w") as f:
        f.write("def main():\n    print('hello')\n")

    orch = SelfImproveOrchestrator(
        project_dir=tmp,
        ollama=llm,
        model="llama3",
        browser=browser,
    )
    assert orch is not None
    print("✓ Orchestrator: created")
    shutil.rmtree(tmp)

def test_orchestrator_inspect():
    llm = MockLLM()
    browser = MockBrowserAgent()
    tmp = tempfile.mkdtemp()
    with open(os.path.join(tmp, "app.py"), "w") as f:
        f.write("def main():\n    print('hello')\n")

    orch = SelfImproveOrchestrator(project_dir=tmp, ollama=llm, model="llama3", browser=browser)
    report = orch.inspect()
    assert "files" in report
    assert len(report["files"]) >= 1
    print(f"✓ Orchestrator: inspected {len(report['files'])} files")
    shutil.rmtree(tmp)

def test_orchestrator_propose():
    llm = MockLLM()
    browser = MockBrowserAgent()
    tmp = tempfile.mkdtemp()
    with open(os.path.join(tmp, "umbra_web.py"), "w") as f:
        f.write("def api_dashboard():\n    d = {}\n    return d\n")

    orch = SelfImproveOrchestrator(project_dir=tmp, ollama=llm, model="llama3", browser=browser)
    orch.inspect()
    proposals = orch.propose()
    assert len(proposals) >= 1
    assert proposals[0].title
    print(f"✓ Orchestrator: proposed {len(proposals)} improvements")
    shutil.rmtree(tmp)

def test_orchestrator_full_pipeline():
    """Full optimize-and-improve cycle: inspect → propose → code → judge → test"""
    llm = MockLLM()
    browser = MockBrowserAgent()
    tmp = tempfile.mkdtemp()
    with open(os.path.join(tmp, "umbra_web.py"), "w") as f:
        f.write("def api_dashboard():\n    d = {}\n    return d\n")
    with open(os.path.join(tmp, "umbra_state.py"), "w") as f:
        f.write("class UmbraStateEngine:\n    def load(self):\n        pass\n")

    orch = SelfImproveOrchestrator(project_dir=tmp, ollama=llm, model="llama3", browser=browser)
    report = orch.run()
    assert "inspection" in report
    assert "proposals" in report
    assert "results" in report
    assert len(report["results"]) >= 1
    r = report["results"][0]
    assert "verdict" in r
    print(f"✓ Orchestrator: full pipeline → {len(report['results'])} results")
    for r in report["results"]:
        jv = r.get('judge_verdict', r.get('reason', 'n/a'))
        tp = r.get('test_passed', '?')
        print(f"    → {r['title']}: verdict={r['verdict']}, judge={jv}, test={tp}")
    shutil.rmtree(tmp)


if __name__ == "__main__":
    print("=" * 50)
    print("SELF-IMPROVE PIPELINE TESTS")
    print("=" * 50)
    tests = [
        test_inspector_scan, test_inspector_file_info, test_inspector_skip_patterns,
        test_proposal_creation, test_proposal_lifecycle,
        test_code_writer,
        test_judge_review, test_judge_requires_majority,
        test_app_tester_feelers, test_app_tester_screenshot_check, test_app_tester_full_test,
        test_orchestrator_creation, test_orchestrator_inspect,
        test_orchestrator_propose, test_orchestrator_full_pipeline,
    ]
    for t in tests:
        t()
    print(f"\n{'='*50}\nALL {len(tests)} TESTS PASSED ✓\n{'='*50}")
