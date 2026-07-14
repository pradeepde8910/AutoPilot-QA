"""
Requirement Intelligence Agent (Pipeline 1)
Acts as a QA Architect to analyze raw requirements (text, user stories, BRDs)
and output structured, professional QA Test Cases.
"""
from typing import Dict, Any, List
from core.llm_client import llm
from utils.logger import log

class RequirementAnalysisAgent:
    def __init__(self):
        self.system_prompt = """You are an experienced QA Architect.
Your job is to analyze raw requirements (Plain English, User Stories, BRD snippets) and generate professional, structured test cases.

You must output ONLY valid JSON matching this schema:
{
  "project_context": "Brief summary of what is being tested",
  "clarifications_needed": ["List of questions if critical info like URLs, credentials, or explicit expectations are missing. Leave empty if everything is clear."],
  "requirements": [
    {
      "module": "String (e.g. Authentication, Dashboard, Search)",
      "feature": "String (e.g. Login, Data Export)",
      "requirement": "String (High-level requirement description)",
      "test_case": "String (Executable test case objective)",
      "preconditions": "String (e.g. User is logged in, URL is accessible)",
      "test_data": "String (e.g. admin/admin123 or any specific inputs)",
      "expected_result": "String (The validation target)",
      "priority": "High|Medium|Low",
      "confidence": Float (0.0 to 1.0, lower if you had to guess details)
    }
  ]
}

CRITICAL RULES:
1. Each test case MUST be completely independent. Our framework launches a fresh browser for every test case. Therefore, EVERY test case must explicitly include the target base URL in its `preconditions` or `requirement`, and include necessary setup steps (like logging in with credentials) in the `preconditions` if required.
2. If essential information (like the target URL to test, or required credentials for a login page) is completely missing from the raw text, DO NOT invent it. Instead, add a question to `clarifications_needed`. You can still attempt to draft the test cases, but mark `confidence` low (e.g. 0.5).
3. Ensure `expected_result` is highly specific. "Dashboard loads" is okay, but "Dashboard loads and displays 'Welcome'" is better if inferred from the prompt.
4. Treat each distinct validation as a separate test case.
"""

    def analyze(self, raw_text: str) -> Dict[str, Any]:
        """
        Analyzes raw text and returns the intermediate JSON structure.
        """
        log.info("RequirementAnalysisAgent analyzing raw requirements...")
        
        full_prompt = f"{self.system_prompt}\n\nRAW REQUIREMENT TEXT:\n{raw_text}"
        
        try:
            result = llm.extract_json(
                prompt=full_prompt, 
                model=llm.default_model
            )
        except Exception as e:
            log.error(f"Requirement Analysis failed: {e}")
            return {"project_context": "Error during analysis", "clarifications_needed": [str(e)], "requirements": []}
            
        return result

