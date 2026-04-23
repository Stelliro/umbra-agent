"""Tests for BrowserAgent — headless browser with visual inspection"""
import sys, json, time, os, tempfile, shutil
sys.path.insert(0, '/home/claude')
from browser_agent import BrowserAgent, Feeler, Screenshot, CaptchaDetected


# === Mock Browser (no real Playwright needed for unit tests) ===
class MockPage:
    def __init__(self):
        self.url = "about:blank"
        self._html = "<html><body><h1>Test</h1><button id='btn1'>Click</button></body></html>"
        self._elements = {
            "button": [{"tag": "button", "id": "btn1", "text": "Click", "visible": True}],
            "#btn1": [{"tag": "button", "id": "btn1", "text": "Click", "visible": True}],
            "h1": [{"tag": "h1", "text": "Test", "visible": True}],
            ".missing": [],
        }
        self.navigation_history = []

    def goto(self, url):
        self.url = url
        self.navigation_history.append(url)

    def content(self):
        return self._html

    def screenshot(self, path=None, **kw):
        # Write a fake PNG header
        data = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        if path:
            with open(path, 'wb') as f:
                f.write(data)
        return data

    def query_selector_all(self, selector):
        return self._elements.get(selector, [])

    def query_selector(self, selector):
        els = self._elements.get(selector, [])
        return els[0] if els else None

    def evaluate(self, js):
        # Mock JS evaluation — detect selector from the querySelectorAll call
        if "querySelectorAll" in js:
            # If it's an inspect call (has multiple tags), return all elements
            if "forEach" in js or "tags" in js:
                all_els = []
                for sel, els in self._elements.items():
                    if not sel.startswith(".") and not sel.startswith("#"):
                        for e in els:
                            all_els.append(dict(e, rect={"x": 10, "y": 20, "width": 100, "height": 40}))
                return all_els
            # Single selector query — find which selector is in the JS
            for sel, els in self._elements.items():
                if f"'{sel}'" in js or f'"{sel}"' in js:
                    return [dict(e, rect={"x": 10, "y": 20, "width": 100, "height": 40}) for e in els]
            return []  # No matching selector found
        if "captcha" in js.lower() or "recaptcha" in js.lower():
            return False  # No captcha by default
        return None

    def click(self, selector):
        pass

    def fill(self, selector, value):
        pass

    def title(self):
        return "Test Page"

    def wait_for_timeout(self, ms):
        time.sleep(ms / 1000)


class MockBrowser:
    def __init__(self):
        self.page = MockPage()

    def new_page(self):
        return self.page

    def close(self):
        pass


# === Feeler Tests ===

def test_feeler_find_elements():
    page = MockPage()
    f = Feeler(page)
    results = f.find("button")
    assert len(results) > 0
    assert results[0]["tag"] == "button"
    print("✓ Feeler: found button elements")

def test_feeler_exists():
    page = MockPage()
    f = Feeler(page)
    assert f.exists("button") == True
    assert f.exists(".missing") == False
    print("✓ Feeler: exists check")

def test_feeler_get_text():
    page = MockPage()
    f = Feeler(page)
    el = f.find("h1")
    assert el[0]["text"] == "Test"
    print("✓ Feeler: get text")

def test_feeler_inspect():
    page = MockPage()
    f = Feeler(page)
    report = f.inspect()
    assert "elements" in report
    assert isinstance(report["elements"], list)
    print(f"✓ Feeler: inspect found {len(report['elements'])} elements")


# === Screenshot Tests ===

def test_screenshot_capture():
    page = MockPage()
    tmp = tempfile.mkdtemp()
    ss = Screenshot(page, output_dir=tmp)
    path = ss.capture("test_shot")
    assert os.path.exists(path)
    assert path.endswith(".png")
    print(f"✓ Screenshot: captured to {os.path.basename(path)}")
    shutil.rmtree(tmp)

def test_screenshot_history():
    page = MockPage()
    tmp = tempfile.mkdtemp()
    ss = Screenshot(page, output_dir=tmp)
    ss.capture("shot1")
    ss.capture("shot2")
    assert len(ss.history) == 2
    print(f"✓ Screenshot: {len(ss.history)} in history")
    shutil.rmtree(tmp)


# === BrowserAgent Tests ===

def test_agent_creation():
    agent = BrowserAgent(headless=True, _mock_browser=MockBrowser())
    assert agent.page is not None
    print("✓ BrowserAgent: created")

def test_agent_navigate():
    agent = BrowserAgent(headless=True, _mock_browser=MockBrowser())
    agent.navigate("https://example.com")
    assert agent.page.url == "https://example.com"
    print("✓ BrowserAgent: navigated")

def test_agent_screenshot():
    tmp = tempfile.mkdtemp()
    agent = BrowserAgent(headless=True, _mock_browser=MockBrowser(), screenshot_dir=tmp)
    path = agent.screenshot("test")
    assert os.path.exists(path)
    print(f"✓ BrowserAgent: screenshot saved")
    shutil.rmtree(tmp)

def test_agent_feeler():
    agent = BrowserAgent(headless=True, _mock_browser=MockBrowser())
    found = agent.feel("button")
    assert len(found) > 0
    print("✓ BrowserAgent: feeler found elements")

def test_agent_feel_exists():
    agent = BrowserAgent(headless=True, _mock_browser=MockBrowser())
    assert agent.feel_exists("button") == True
    assert agent.feel_exists(".missing") == False
    print("✓ BrowserAgent: feel_exists")

def test_agent_inspect_page():
    agent = BrowserAgent(headless=True, _mock_browser=MockBrowser())
    report = agent.inspect_page()
    assert "url" in report
    assert "title" in report
    assert "elements" in report
    print(f"✓ BrowserAgent: inspect_page")

def test_agent_captcha_detection():
    agent = BrowserAgent(headless=True, _mock_browser=MockBrowser())
    # Default mock: no captcha
    assert agent.detect_captcha() == False
    print("✓ BrowserAgent: no captcha detected (correct)")

def test_agent_captcha_found():
    """When captcha IS detected, agent should flag it for manual handling."""
    browser = MockBrowser()
    # Inject captcha into mock
    browser.page._elements["iframe[src*='recaptcha']"] = [{"tag": "iframe", "src": "recaptcha"}]
    browser.page.evaluate = lambda js: True if "captcha" in js.lower() else None
    agent = BrowserAgent(headless=True, _mock_browser=browser)
    assert agent.detect_captcha() == True
    print("✓ BrowserAgent: captcha detected → manual flag")

def test_agent_action_log():
    agent = BrowserAgent(headless=True, _mock_browser=MockBrowser())
    agent.navigate("https://example.com")
    agent.screenshot("test")
    agent.feel("button")
    assert len(agent.action_log) == 3
    print(f"✓ BrowserAgent: {len(agent.action_log)} actions logged")

def test_agent_status():
    agent = BrowserAgent(headless=True, _mock_browser=MockBrowser())
    s = agent.status()
    assert "url" in s
    assert "actions" in s
    assert "screenshots" in s
    print("✓ BrowserAgent: status report")


if __name__ == "__main__":
    print("=" * 50)
    print("BROWSER AGENT TESTS")
    print("=" * 50)
    tests = [
        test_feeler_find_elements, test_feeler_exists, test_feeler_get_text, test_feeler_inspect,
        test_screenshot_capture, test_screenshot_history,
        test_agent_creation, test_agent_navigate, test_agent_screenshot,
        test_agent_feeler, test_agent_feel_exists, test_agent_inspect_page,
        test_agent_captcha_detection, test_agent_captcha_found,
        test_agent_action_log, test_agent_status,
    ]
    for t in tests:
        t()
    print(f"\n{'='*50}\nALL {len(tests)} TESTS PASSED ✓\n{'='*50}")
