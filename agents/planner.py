"""
Planner Agent.
Converts a natural language Requirement into a structured list of testing tasks.
"""
from typing import List
from core.llm_client import llm
from models.schemas import Requirement
from utils.logger import log

class PlannerAgent:
    def __init__(self):
        self.schema = {
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "description": "A single actionable browser step"
                    }
                }
            },
            "required": ["tasks"]
        }
        
    def plan(self, requirement: Requirement) -> List[str]:
        """Takes a Requirement and returns a sequential list of steps."""
        log.info(f"PlannerAgent planning for requirement: {requirement.description}")
        
        prompt = f"""
You are the Planner Agent for an autonomous Web QA system.
Your goal is to break down a testing requirement into a chronological list of high-level browser actions.

Requirement ID: {requirement.id}
Module: {requirement.module}
Feature: {requirement.feature}
Description: {requirement.description}
Preconditions: {', '.join(requirement.preconditions)}
Test Data: {requirement.test_data}
Expected Result: {requirement.expected_result}

Rules for the task list:
1. Keep steps very concise (e.g., 'Visit Website https://example.com', 'Enter admin into username field').
2. ALWAYS explicitly include the URL in the step if it is provided in the Description or Preconditions.
3. Incorporate the exact Test Data if provided (e.g., 'Type password123 into password field').
4. Do not write code or CSS selectors; focus on logical user intentions.
5. Ensure the final step explicitly checks the Expected Result (e.g., 'Verify the dashboard loaded successfully').

Generate the sequence of tasks required to execute this test.
"""
        try:
            response = llm.extract_json(prompt=prompt, schema=self.schema)
            tasks = response.get("tasks", [])
            log.info(f"PlannerAgent generated {len(tasks)} tasks.")
            return tasks
        except Exception as e:
            log.error(f"Planner failed to generate tasks: {e}")
            return []
