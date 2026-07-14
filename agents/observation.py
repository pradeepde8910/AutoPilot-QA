"""
Observation Agent.
Collects DOM, Accessibility, Screenshot, HTML, Console, Network, Performance.
Everything goes into Observation inside AgentState.
"""
import uuid
from datetime import datetime
from core.browser import BrowserManager
from core.state import AgentState, Observation
from models.schemas import BrowserState
from config.constants import SCREENSHOTS_DIR
from utils.logger import log

class ObservationAgent:
    def __init__(self, browser: BrowserManager):
        self.browser = browser

    def observe(self, state: AgentState, description: str = "Automated Observation") -> bool:
        """
        Gathers all browser telemetry and appends it as an Observation to the state.
        """
        log.info("ObservationAgent starting data collection.")
        try:
            # Update current page in state first
            if self.browser.page:
                state.current_page = self.browser.page.url

            # 1. Capture Screenshot
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            unique_id = str(uuid.uuid4())[:8]
            screenshot_name = f"obs_{timestamp}_{unique_id}.png"
            screenshot_path = str(SCREENSHOTS_DIR / screenshot_name)
            
            self.browser.take_screenshot(screenshot_path)
            state.add_screenshot(screenshot_path)
            
            # 2. Extract DOM & Accessibility
            dom = self.browser.get_dom()
            a11y = self.browser.get_accessibility_tree()
            
            # 3. Extract Telemetry
            console = self.browser.get_console_logs()
            network = self.browser.get_network_requests()
            perf = self.browser.get_performance_metrics()
            
            # 4. Pack into Observation
            raw_data = {
                "url": state.current_page,
                "screenshot_path": screenshot_path,
                "accessibility_issues": len(a11y.get("violations", [])),
                "console_errors": len([log for log in console if log['type'] == 'error']),
                "network_requests_count": len(network),
                "performance_metrics": perf,
                "dom_length": len(dom),
                # Full logs for EvidenceAgent to persist to disk
                "full_console_logs": console,
                "full_network_requests": network
            }
            
            observation = Observation(
                description=description,
                raw_data=raw_data
            )
            
            state.add_observation(observation)
            
            # 5. Ensure BrowserState is updated
            if state.browser_state is None:
                state.browser_state = BrowserState(
                    current_url=state.current_page,
                    page_title=self.browser.page.title() if self.browser.page else "",
                    dom_snapshot=dom[:50000],  # truncated to save memory
                    accessibility_tree=a11y,
                    latest_screenshot_path=screenshot_path
                )
            else:
                state.browser_state.current_url = state.current_page
                state.browser_state.page_title = self.browser.page.title() if self.browser.page else ""
                state.browser_state.latest_screenshot_path = screenshot_path
                state.browser_state.accessibility_tree = a11y
                
            log.info("ObservationAgent successfully packed telemetry into state.")
            state.log_history(f"Observation completed: {description}")
            return True
            
        except Exception as e:
            error_msg = f"ObservationAgent failed: {e}"
            log.error(error_msg)
            state.add_failure(error_msg)
            return False
