"""
Verification Agent.
Acts as the intelligence of the QA platform.
Analyzes the Requirement and the Observation to determine PASS/FAIL.
"""
from core.llm_client import llm
from core.state import AgentState
from models.schemas import TestResult
from utils.logger import log
from utils.dom import clean_html

class VerificationAgent:
    def __init__(self):
        self.schema = {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["PASS", "FAIL", "PARTIAL"],
                    "description": "The outcome of the verification."
                },
                "confidence": {
                    "type": "number",
                    "description": "Confidence score from 0.0 to 1.0"
                },
                "reason": {
                    "type": "string",
                    "description": "Detailed reasoning for the status decision."
                },
                "suggested_fix": {
                    "type": "string",
                    "description": "Suggested fix if FAIL or PARTIAL. Empty string if PASS."
                }
            },
            "required": ["status", "confidence", "reason", "suggested_fix"]
        }

    def verify(self, state: AgentState) -> TestResult:
        """
        Reads the current requirement and the latest observations from state,
        and uses the LLM to output a TestResult.
        """
        log.info("VerificationAgent starting verification process.")
        
        req = state.current_requirement
        if not req:
            raise ValueError("No current requirement found in state.")
            
        if not state.observations:
            raise ValueError("No observations found in state to verify against.")
            
        # Verify against the latest observation
        latest_obs = state.observations[-1]
        
        dom_snippet = ""
        if state.browser_state and state.browser_state.dom_snapshot:
            cleaned_dom = clean_html(state.browser_state.dom_snapshot)
            # Send a reasonable snippet of the cleaned DOM
            dom_snippet = cleaned_dom[:30000] if len(cleaned_dom) > 30000 else cleaned_dom
            
        prompt = f"""
You are the Verification Agent. Your job is to determine if a web requirement has been met based on the observed data.

Requirement:
{req.description}
Rules: {req.business_rules}

Observation Context:
- Current URL: {latest_obs.raw_data.get('url', 'N/A')}
- Console Errors: {latest_obs.raw_data.get('console_errors', 0)}
- Network Requests: {latest_obs.raw_data.get('network_requests', 0)}
- DOM Length: {latest_obs.raw_data.get('dom_length', 0)}
- Accessibility Issues: {latest_obs.raw_data.get('accessibility_issues', 0)}

DOM Snapshot (Truncated):
```html
{dom_snippet}
```

Based on this observation, does the system satisfy the requirement?
Output a JSON object matching the schema.
"""
        try:
            response = llm.extract_json(prompt=prompt, schema=self.schema)
            
            result = TestResult(
                test_case_id=req.id,
                status=response.get("status", "FAIL"),
                confidence_score=float(response.get("confidence", 0.0)),
                reasoning=response.get("reason", "No reason provided."),
                suggested_fix=response.get("suggested_fix", "")
            )
            
            log.info(f"Verification complete: {result.status} (Confidence: {result.confidence_score})")
            state.log_history(f"Verification complete: {result.status}. {result.reasoning}")
            
            return result
            
        except Exception as e:
            error_msg = f"Verification failed due to exception: {e}"
            log.error(error_msg)
            state.add_failure(error_msg)
            return TestResult(
                test_case_id=req.id,
                status="FAIL",
                confidence_score=0.0,
                reasoning=error_msg
            )
