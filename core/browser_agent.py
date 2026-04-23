"""
Browser Agent v1.0 — UMBRA's Private Browser
==============================================
Headless browser (Playwright) that UMBRA controls directly.
The handler can't see this browser unless UMBRA shows them.

Capabilities:
  NAVIGATE  → Go to any URL
  SCREENSHOT → Capture visible page as PNG (for LLM visual inspection)
  FEELERS   → DOM inspection: find elements, check existence, get text
  INTERACT  → Click, type, fill forms
  CAPTCHA   → Detect CAPTCHAs, request manual handler intervention

Install: pip install playwright && python -m playwright install chromium

Architecture:
  BrowserAgent
    ├── Feeler    (DOM inspection layer)
    ├── Screenshot (capture + history)
    └── CaptchaDetector (detect + manual handoff)
"""
import os, time, json, logging, base64
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("UMBRA-BROWSER")


class CaptchaDetected(Exception):
    """Raised when a CAPTCHA is detected and needs manual solving."""
    def __init__(self, screenshot_path=None, url=None):
        self.screenshot_path = screenshot_path
        self.url = url
        super().__init__(f"CAPTCHA detected at {url}. Manual intervention required.")


# === Feeler: DOM Inspection Layer ===

class Feeler:
    """
    DOM element detection and inspection.
    'Feelers' probe the page structure without visual rendering.
    """

    def __init__(self, page):
        self.page = page

    def find(self, selector: str) -> List[Dict]:
        """Find elements matching a CSS selector. Returns element info dicts."""
        try:
            results = self.page.evaluate(f"""
                () => {{
                    const els = document.querySelectorAll('{selector}');
                    return Array.from(els).slice(0, 50).map(el => {{
                        const rect = el.getBoundingClientRect();
                        return {{
                            tag: el.tagName.toLowerCase(),
                            id: el.id || null,
                            text: (el.textContent || '').trim().substring(0, 200),
                            visible: rect.width > 0 && rect.height > 0,
                            rect: {{x: rect.x, y: rect.y, width: rect.width, height: rect.height}},
                            classes: el.className || '',
                            href: el.href || null,
                            type: el.type || null,
                            value: el.value || null,
                        }};
                    }});
                }}
            """)
            return results or []
        except Exception:
            # Fallback for mock pages
            try:
                els = self.page.query_selector_all(selector)
                if isinstance(els, list) and els and isinstance(els[0], dict):
                    return els
                return [{"tag": "unknown"}] * len(els) if els else []
            except:
                return []

    def exists(self, selector: str) -> bool:
        """Check if any element matches the selector."""
        return len(self.find(selector)) > 0

    def get_text(self, selector: str) -> Optional[str]:
        """Get text content of the first matching element."""
        els = self.find(selector)
        if els and els[0].get("text"):
            return els[0]["text"]
        return None

    def inspect(self) -> Dict:
        """Full page DOM inspection — returns summary of key elements."""
        try:
            elements = self.page.evaluate("""
                () => {
                    const tags = ['button', 'a', 'input', 'select', 'textarea',
                                  'form', 'nav', 'h1', 'h2', 'h3', 'img', 'iframe'];
                    const results = [];
                    tags.forEach(tag => {
                        const els = document.querySelectorAll(tag);
                        els.forEach(el => {
                            const rect = el.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                results.push({
                                    tag: tag,
                                    id: el.id || null,
                                    text: (el.textContent || '').trim().substring(0, 100),
                                    visible: true,
                                    rect: {x: rect.x, y: rect.y, width: rect.width, height: rect.height},
                                });
                            }
                        });
                    });
                    return results;
                }
            """)
            return {"elements": elements or []}
        except Exception:
            # Fallback: use basic query
            try:
                els = self.page.evaluate("() => []")
                return {"elements": els if isinstance(els, list) else []}
            except:
                return {"elements": []}


# === Screenshot: Capture + History ===

class Screenshot:
    """Captures and stores page screenshots for LLM visual inspection."""

    def __init__(self, page, output_dir: str = None):
        self.page = page
        self.output_dir = Path(output_dir or os.path.join(os.getcwd(), "data", "screenshots"))
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.history: List[Dict] = []

    def capture(self, name: str = None, full_page: bool = False) -> str:
        """Take a screenshot. Returns file path."""
        name = name or f"shot_{int(time.time())}"
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{name}_{ts}.png"
        path = str(self.output_dir / filename)

        try:
            self.page.screenshot(path=path, full_page=full_page)
        except TypeError:
            # Mock page may not accept full_page kwarg
            self.page.screenshot(path=path)

        self.history.append({
            "name": name,
            "path": path,
            "timestamp": ts,
        })

        logger.debug(f"📸 Screenshot: {filename}")
        return path

    def capture_base64(self, full_page: bool = False) -> str:
        """Capture screenshot as base64 string (for LLM vision input)."""
        try:
            data = self.page.screenshot(full_page=full_page)
            return base64.b64encode(data).decode('utf-8')
        except:
            return ""

    def get_latest(self) -> Optional[str]:
        """Get path to most recent screenshot."""
        return self.history[-1]["path"] if self.history else None


# === BrowserAgent: Main Interface ===

class BrowserAgent:
    """
    UMBRA's private browser. Headless Chromium controlled via Playwright.
    The handler doesn't see this browser — UMBRA shares screenshots when it wants to.
    """

    def __init__(self, headless: bool = True, screenshot_dir: str = None,
                 _mock_browser=None):
        self.headless = headless
        self.action_log: List[Dict] = []
        self._browser = None
        self.page = None
        self._pw = None
        self._feeler = None
        self._screenshot = None

        if _mock_browser:
            # Testing mode
            self._browser = _mock_browser
            self.page = _mock_browser.page
        else:
            self._init_browser()

        self._feeler = Feeler(self.page)
        self._screenshot = Screenshot(self.page, output_dir=screenshot_dir)

    def _init_browser(self):
        """Initialize Playwright + Chromium."""
        try:
            from playwright.sync_api import sync_playwright
            self._pw = sync_playwright().start()
            self._browser = self._pw.chromium.launch(headless=self.headless)
            self.page = self._browser.new_page()
            logger.info("🌐 Browser initialized (Chromium)")
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && python -m playwright install chromium")
            raise
        except Exception as e:
            logger.error(f"Browser init failed: {e}")
            raise

    def _log(self, action: str, details: str = ""):
        self.action_log.append({
            "action": action,
            "details": details,
            "time": time.time(),
            "url": getattr(self.page, 'url', 'unknown'),
        })

    # === Navigation ===

    def navigate(self, url: str, wait_ms: int = 1000):
        """Navigate to a URL."""
        self.page.goto(url)
        if wait_ms:
            try:
                self.page.wait_for_timeout(wait_ms)
            except:
                time.sleep(wait_ms / 1000)
        self._log("navigate", url)
        logger.info(f"🔗 Navigate: {url}")

    # === Screenshot ===

    def screenshot(self, name: str = None, full_page: bool = False) -> str:
        """Take a screenshot. Returns file path."""
        path = self._screenshot.capture(name, full_page)
        self._log("screenshot", path)
        return path

    def screenshot_base64(self, full_page: bool = False) -> str:
        """Get screenshot as base64 for LLM vision."""
        return self._screenshot.capture_base64(full_page)

    # === Feelers (DOM Inspection) ===

    def feel(self, selector: str) -> List[Dict]:
        """Find elements by CSS selector."""
        results = self._feeler.find(selector)
        self._log("feel", f"{selector} → {len(results)} elements")
        return results

    def feel_exists(self, selector: str) -> bool:
        """Check if an element exists."""
        return self._feeler.exists(selector)

    def inspect_page(self) -> Dict:
        """Full page inspection: URL, title, all interactive elements."""
        inspection = self._feeler.inspect()
        result = {
            "url": getattr(self.page, 'url', 'unknown'),
            "title": self.page.title() if hasattr(self.page, 'title') and callable(self.page.title) else "unknown",
            "elements": inspection.get("elements", []),
            "timestamp": time.time(),
        }
        self._log("inspect", f"{len(result['elements'])} elements")
        return result

    # === Interaction ===

    def click(self, selector: str):
        """Click an element."""
        self.page.click(selector)
        self._log("click", selector)

    def type_text(self, selector: str, text: str):
        """Type text into an input field."""
        self.page.fill(selector, text)
        self._log("type", f"{selector}: {text[:30]}...")

    def get_page_content(self) -> str:
        """Get raw HTML content."""
        return self.page.content()

    # === CAPTCHA Detection ===

    def detect_captcha(self) -> bool:
        """
        Check if the current page has a CAPTCHA.
        Checks for: reCAPTCHA iframes, hCaptcha, CloudFlare challenges, generic captcha elements.
        """
        try:
            has_captcha = self.page.evaluate("""
                () => {
                    // reCAPTCHA
                    if (document.querySelector('iframe[src*="recaptcha"]')) return true;
                    if (document.querySelector('.g-recaptcha')) return true;
                    // hCaptcha
                    if (document.querySelector('iframe[src*="hcaptcha"]')) return true;
                    if (document.querySelector('.h-captcha')) return true;
                    // CloudFlare
                    if (document.querySelector('#cf-challenge-running')) return true;
                    if (document.querySelector('.cf-turnstile')) return true;
                    // Generic
                    if (document.querySelector('[id*="captcha"]')) return true;
                    if (document.querySelector('[class*="captcha"]')) return true;
                    return false;
                }
            """)
            if has_captcha:
                self._log("captcha_detected", self.page.url if hasattr(self.page, 'url') else "unknown")
                logger.warning("🔒 CAPTCHA detected — needs manual intervention")
            return bool(has_captcha)
        except Exception:
            return False

    def request_manual_captcha(self, screenshot_name: str = "captcha") -> Dict:
        """
        Take a screenshot of the CAPTCHA and flag it for handler intervention.
        Returns info dict for the handler alert system.
        """
        ss_path = self.screenshot(screenshot_name)
        return {
            "type": "captcha_manual_request",
            "url": getattr(self.page, 'url', 'unknown'),
            "screenshot": ss_path,
            "message": "CAPTCHA detected. Please solve it manually.",
            "timestamp": time.time(),
        }

    # === Status ===

    def status(self) -> Dict:
        return {
            "url": getattr(self.page, 'url', 'unknown'),
            "actions": len(self.action_log),
            "screenshots": len(self._screenshot.history),
            "last_action": self.action_log[-1] if self.action_log else None,
        }

    def close(self):
        """Shut down browser."""
        if self._browser:
            try:
                self._browser.close()
            except:
                pass
        if self._pw:
            try:
                self._pw.stop()
            except:
                pass
        logger.info("🌐 Browser closed")
