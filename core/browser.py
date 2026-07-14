"""
Browser orchestration layer using Playwright.
Provides capabilities to interact with the web and extract state.
"""
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext
from typing import Optional, Dict, Any
from utils.logger import log
from config.settings import settings

class BrowserManager:
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.console_logs = []
        self.network_requests = []

    def launch_browser(self):
        """Initializes Playwright and launches the browser."""
        log.info(f"Launching browser (headless={self.headless})")
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        # Use a desktop 1920x1080 viewport so CSS media query hides mobile toggles
        self.context = self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        self.page = self.context.new_page()
        
        # Add listeners for console and network
        self.page.on("console", lambda msg: self.console_logs.append({"type": msg.type, "text": msg.text}))
        self.page.on("request", lambda req: self.network_requests.append({"url": req.url, "method": req.method}))

    def get_console_logs(self):
        logs = self.console_logs.copy()
        self.console_logs.clear()
        return logs
        
    def get_network_requests(self):
        reqs = self.network_requests.copy()
        self.network_requests.clear()
        return reqs
        
    def get_performance_metrics(self) -> Dict[str, Any]:
        try:
            return self.page.evaluate("window.performance.timing.toJSON()")
        except Exception as e:
            log.error(f"Failed to get performance metrics: {e}")
            return {"error": str(e)}

    def open_url(self, url: str):
        if not self.page:
            self.launch_browser()
        log.info(f"Opening URL: {url}")
        try:
            # For modern SPAs, wait_until="networkidle" is best to ensure JS frameworks have loaded elements.
            self.page.goto(url, wait_until="networkidle", timeout=settings.BROWSER_TIMEOUT_MS)
            # A fallback wait just in case of slow animations
            self.page.wait_for_timeout(2000)
        except Exception as e:
            log.warning(f"Timeout or error while opening {url}, but continuing: {e}")

    def click(self, selector: str):
        """Clicks an element using standard click, with JS force-click fallback."""
        log.info(f"Clicking element: {selector}")
        try:
            # Standard click - waits for element to be visible and stable
            self.page.click(selector, timeout=10000)
        except Exception as e:
            log.warning(f"Standard click failed on '{selector}': {e}. Trying JS force-click...")
            try:
                # Force click via JavaScript - bypasses visibility checks
                self.page.evaluate(f"document.querySelector('{selector}').click()")
                log.info(f"JS force-click succeeded on '{selector}'")
            except Exception as e2:
                raise Exception(f"Both standard and JS click failed for '{selector}': {e2}") from e2

    def scroll_to_bottom(self):
        """Scrolls to the bottom of the page using JavaScript."""
        log.info("Scrolling to bottom of page")
        self.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        self.page.wait_for_timeout(1000)

    def type(self, selector: str, text: str):
        """Types text into an input field."""
        log.info(f"Typing into {selector}")
        self.page.fill(selector, text)

    def wait(self, timeout_ms: int):
        """Waits for a specific timeout in milliseconds."""
        log.info(f"Waiting for {timeout_ms} ms")
        self.page.wait_for_timeout(timeout_ms)

    def take_screenshot(self, path: str):
        """Takes a full page screenshot and saves it to the path."""
        log.info(f"Taking screenshot: {path}")
        try:
            self.page.screenshot(path=path, full_page=True, timeout=15000)
        except Exception as e:
            log.warning(f"Screenshot failed, trying without waiting for fonts: {e}")
            try:
                self.page.screenshot(path=path, full_page=False, timeout=5000)
            except Exception as e2:
                log.error(f"Failed to take screenshot entirely: {e2}")

    def get_dom(self) -> str:
        """Returns the full HTML DOM of the current page."""
        return self.page.content()

    def get_dom_snapshot(self) -> str:
        """Alias for get_dom() used by NavigationAgent."""
        return self.get_dom()

    def get_html(self, selector: str) -> str:
        """Returns the inner HTML of a specific element."""
        return self.page.inner_html(selector)

    def get_accessibility_tree(self) -> Dict[str, Any]:
        """Returns the accessibility snapshot of the page using Axe."""
        log.info("Fetching accessibility tree using axe-playwright-python")
        try:
            from axe_playwright_python.sync_playwright import Axe
            axe = Axe()
            results = axe.run(self.page)
            return {"violations": getattr(results, "violations", []), "passes": getattr(results, "passes", []), "raw": str(results)}
        except Exception as e:
            log.error(f"Axe accessibility failed: {e}")
            return {"error": str(e)}

    def close_browser(self):
        """Closes the browser and stops Playwright. Safe to call multiple times."""
        log.info("Closing browser")
        try:
            if self.context:
                self.context.close()
        except Exception as e:
            log.warning(f"Context close warning (safe to ignore): {e}")
        finally:
            self.context = None

        try:
            if self.browser:
                self.browser.close()
        except Exception as e:
            log.warning(f"Browser close warning (safe to ignore): {e}")
        finally:
            self.browser = None

        try:
            if self.playwright:
                self.playwright.stop()
        except Exception as e:
            log.warning(f"Playwright stop warning (safe to ignore): {e}")
        finally:
            self.playwright = None
