"""
Navigation Agent.
Translates a logical task (e.g., 'Click Login') into a strict Playwright action.
Performs NO complex reasoning. Strictly mapping task -> action based on the DOM.
Includes a MemoryStore for lightning-fast repeated executions and self-healing.
"""
import json
from pathlib import Path
from typing import Dict, Any, Tuple
from core.llm_client import llm
from core.browser import BrowserManager
from core.state import AgentState
from utils.logger import log
from utils.dom import clean_html

class MemoryStore:
    def __init__(self):
        self._last_filepath = None
        self._memory = {}

    @property
    def filepath(self) -> Path:
        from config.constants import PROJECT_ROOT
        from config.settings import settings
        base = Path(settings.OUTPUT_DIR).resolve() if settings.OUTPUT_DIR else PROJECT_ROOT
        return base / "memory.json"

    @property
    def memory(self):
        current_path = self.filepath
        if current_path != self._last_filepath:
            self._last_filepath = current_path
            self._memory = self._load()
        return self._memory

    @memory.setter
    def memory(self, value):
        self._memory = value

    def _load(self):
        path = self.filepath
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return {}
        return {}
        
    def save(self):
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self.memory, f, indent=4)
            
    def get_action(self, task: str):
        return self.memory.get(task)
        
    def set_action(self, task: str, action: dict):
        self.memory[task] = action
        self.save()

    def clear(self):
        """Clears the memory cache and deletes the memory file if it exists."""
        self.memory = {}
        path = self.filepath
        if path.exists():
            try:
                path.unlink()
            except Exception as e:
                from utils.logger import log
                log.warning(f"Could not delete memory file: {e}")

memory_store = MemoryStore()

class NavigationAgent:
    def __init__(self, browser: BrowserManager):
        self.browser = browser
        self.schema = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["click", "type", "open_url", "scroll", "wait", "fail", "none"],
                    "description": "The Playwright action to perform. Use 'scroll' to scroll to bottom of page. 'fail' if impossible. 'none' if no action needed."
                },
                "selector": {
                    "type": ["string", "null"],
                    "description": "The CSS selector to interact with (for click/type). Null if not applicable."
                },
                "value": {
                    "type": ["string", "null"],
                    "description": "The text to type (for type), or the URL to open (for open_url). Null if not applicable."
                },
                "reason": {
                    "type": "string",
                    "description": "Brief explanation of why this action was chosen."
                }
            },
            "required": ["action", "reason"]
        }

    def execute_task(self, task: str, state: AgentState) -> Tuple[bool, str]:
        """
        Takes a task string, evaluates the current DOM (or memory), and executes the Playwright action.
        Returns a tuple of (Success: bool, Message: str).
        """
        log.info(f"NavigationAgent processing task: {task}")
        
        try:
            dom = self.browser.get_dom()
            cleaned_dom = clean_html(dom)
            # Limit DOM to 30000 chars to save tokens, but keep it large enough to include all elements
            dom_snippet = cleaned_dom[:30000] if len(cleaned_dom) > 30000 else cleaned_dom
        except Exception as e:
            dom_snippet = f"Could not retrieve DOM: {e}"

        # 1. Memory Check (Fast Path / Self Healing Validation)
        cached_action = memory_store.get_action(task)
        action_payload = None
        
        if cached_action:
            selector = cached_action.get("selector")
            # Verify if selector is still valid
            if selector:
                try:
                    element = self.browser.page.query_selector(selector)
                    if element:
                        log.info(f"Memory Hit! Re-using known selector '{selector}' for '{task}'")
                        action_payload = cached_action
                    else:
                        log.warning(f"Self-Healing triggered! Cached selector '{selector}' not found in DOM. Falling back to LLM.")
                except Exception:
                    log.warning("Self-Healing triggered! Playwright could not query the cached selector.")
            else:
                # Actions without selectors (e.g., open_url) are safe to reuse from memory
                log.info(f"Memory Hit! Re-using known action for '{task}'")
                action_payload = cached_action

        # 2. AI Navigation (if not in memory, or if self-healing kicked in)
        if not action_payload:
            prompt = f"""
            You are the Navigation Agent. You must map the given Task to a strict Browser Action.
            Do NOT reason about whether the test passes or fails. Only figure out HOW to interact with the DOM to achieve the task.
            
            Current URL: {state.current_page}
            Task: {task}
            
            Current DOM Snippet:
            ```html
            {dom_snippet}
            ```
            
            Based on the DOM, what is the exact action to perform? Output a JSON object matching the schema.
            If the task requires interacting with an element that DOES NOT exist in the DOM, return action='fail'.
            
            CRITICAL RULES:
            1. If the task is to verify, check, confirm, or assert a state or page elements (e.g., 'Verify the dashboard loaded successfully', 'Verify error message is displayed'), and does NOT require clicking, typing, scrolling, or navigating, output action='none'.
            2. Do NOT attempt to perform redundant or random interactions (like typing into inputs or clicking unrelated buttons) if the task is purely verification.
            """
            
            try:
                action_payload = llm.extract_json(prompt=prompt, schema=self.schema)
                log.info(f"LLM suggested action: {action_payload.get('action')} on selector: {action_payload.get('selector')}. Reason: {action_payload.get('reason')}")
                
                # Save to Memory for next time (if it's a successful step)
                if action_payload.get("action") != "fail":
                    memory_store.set_action(task, action_payload)
                    
            except Exception as e:
                msg = f"Failed to get AI action: {e}"
                log.error(msg)
                state.log_history(msg)
                return False, msg
                
        # 3. Execute Action
        try:
            action = action_payload.get("action", "fail")
            selector = action_payload.get("selector", "")
            value = action_payload.get("value", "")
            reason = action_payload.get("reason", "")
            
            if action == "fail":
                error_msg = f"Navigation Failed. Reason: {reason}"
                log.error(error_msg)
                state.add_failure(error_msg)
                return False, error_msg
                
            elif action == "click":
                self.browser.click(selector)
                
            elif action == "type":
                self.browser.type(selector, value)
                
            elif action == "open_url":
                self.browser.open_url(value)
                state.current_page = value
                
            elif action == "scroll":
                self.browser.scroll_to_bottom()
                
            elif action == "wait":
                wait_time = int(value) if value and str(value).isdigit() else 2000
                self.browser.wait(wait_time)
                
            elif action == "none":
                log.info("No interactive action required for this task.")
            
            success_msg = f"Successfully performed '{action}' for task '{task}'"
            state.log_history(success_msg)
            return True, success_msg

        except Exception as e:
            error_msg = f"Navigation Failed due to exception: {e}"
            log.error(error_msg)
            state.add_failure(error_msg)
            return False, error_msg
