"""
Reflection Agent
Analyzes failures during Navigation and suggests corrective, adaptive tasks to retry.
"""
from typing import List
from core.llm_client import llm
from core.state import AgentState
from utils.logger import log
from utils.dom import clean_html

class ReflectionAgent:
    def reflect(self, state: AgentState, failed_task: str, error_reason: str) -> List[str]:
        log.info(f"ReflectionAgent analyzing failure for task: '{failed_task}'")
        
        # We need DOM to make a decision
        dom_snippet = "No DOM available"
        if state.browser_state and state.browser_state.dom_snapshot:
            cleaned_dom = clean_html(state.browser_state.dom_snapshot)
            # Limit cleaned DOM to 15000 chars to avoid token limits, but keep it large enough
            dom_snippet = cleaned_dom[:15000] if len(cleaned_dom) > 15000 else cleaned_dom
        
        prompt = f"""
        The following web automation task failed during execution:
        Failed Task: "{failed_task}"
        Error Reason: "{error_reason}"
        
        Current DOM Snippet:
        {dom_snippet}
        
        Based on the DOM, why did the task fail? 
        What corrective steps should we take? 
        For example, if "Click Login" failed because it's inside a hidden menu, output: ["Click hamburger menu", "Click Login"].
        If a popup is blocking, output: ["Close popup", "{failed_task}"].
        
        Provide the logical sequence of exact tasks to recover. If unrecoverable or you're unsure, return an empty array.
        """
        
        schema = {
            "type": "object",
            "properties": {
                "corrected_tasks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Chronological list of tasks to execute to recover from the failure."
                }
            },
            "required": ["corrected_tasks"]
        }
        
        try:
            result = llm.extract_json(prompt=prompt, schema=schema)
            corrected = result.get("corrected_tasks", [])
            log.info(f"ReflectionAgent suggested corrections: {corrected}")
            return corrected
        except Exception as e:
            log.error(f"ReflectionAgent failed to generate correction: {e}")
            return []
