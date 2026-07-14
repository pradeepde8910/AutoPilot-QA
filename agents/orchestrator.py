import os
from typing import List
from models.schemas import Requirement, TestResult
from core.browser import BrowserManager
from core.state import AgentState
from agents.planner import PlannerAgent
from agents.navigation import NavigationAgent
from agents.observation import ObservationAgent
from agents.verification import VerificationAgent
from agents.evidence import EvidenceAgent
from agents.reporter import ReportingAgent
from agents.reflection import ReflectionAgent
from config.settings import settings
from utils.logger import log

class OrchestratorAgent:
    """
    Coordinates the entire testing lifecycle.
    Each agent is independent and stateless, while the Orchestrator 
    manages execution flow, retries, shared state, and browser lifecycle.
    """
    def __init__(self):
        log.info("Initializing Orchestrator Agent and stateless workers...")
        self.planner = PlannerAgent()
        self.verification = VerificationAgent()
        self.evidence = EvidenceAgent()
        self.reflection = ReflectionAgent()
        
        # Ensure evidence agent writes to a run folder that the reporter can use
        self.run_dir = self.evidence.run_dir
        self.reporter = ReportingAgent(str(self.run_dir))

    def run(self, requirements: List[Requirement]) -> None:
        """
        Executes the autonomous test generation and reporting pipeline for the given requirements.
        """
        # Reset LLM fallback status at the start of a pipeline run
        from core.llm_client import llm
        llm.reset_fallback()
        
        # Clear the navigation action memory cache for a fresh, clean execution run
        from agents.navigation import memory_store
        memory_store.clear()
        
        final_results = []
        
        for req in requirements:
            log.info(f"========== Processing Requirement: {req.id} ==========")
            
            # 1. State Initialization
            state = AgentState()
            state.current_requirement = req
            browser = BrowserManager(headless=settings.BROWSER_HEADLESS)
            
            try:
                # 2. Planner
                tasks = self.planner.plan(req)
                if not tasks:
                    log.error("Planner failed to generate tasks. Skipping.")
                    final_results.append(TestResult(test_case_id=req.id, status="FAIL", reasoning="Planner failed to generate tasks."))
                    continue
                    
                # 3. Browser
                browser.launch_browser()
                
                # 4. Navigation (Adaptive Queue)
                nav_agent = NavigationAgent(browser)
                
                task_queue = tasks.copy()
                retries = 0
                MAX_RETRIES = 3
                
                while task_queue:
                    task = task_queue.pop(0)
                    success, msg = nav_agent.execute_task(task, state)
                    
                    if not success:
                        if retries >= MAX_RETRIES:
                            log.error(f"Max retries ({MAX_RETRIES}) reached. Halting navigation.")
                            break
                        
                        # Skip reflection on API rate limit errors — it would just waste more tokens
                        if "rate_limit_exceeded" in msg or "429" in msg:
                            log.error("Rate limit hit. Stopping navigation to conserve API quota.")
                            break
                            
                        log.warning(f"Task failed: {msg}. Triggering Reflection Agent for Self-Healing.")
                        corrected_tasks = self.reflection.reflect(state, task, msg)
                        
                        if corrected_tasks:
                            log.info(f"Adaptive Navigation: Injecting {len(corrected_tasks)} corrective tasks.")
                            # Prepend the new corrected tasks to the queue
                            task_queue = corrected_tasks + task_queue
                            retries += 1
                        else:
                            log.error("Reflection Agent could not find a way to recover. Halting navigation.")
                            break
                        
                # 5. Observation (Observe regardless of nav failure to capture the error state)
                obs_agent = ObservationAgent(browser)
                obs_agent.observe(state, description=f"Final state for {req.id}")
                
                # 6. Verification
                result = self.verification.verify(state)
                
                # 7. Evidence
                self.evidence.package_evidence(state)
                
                final_results.append(result)
                
            except Exception as e:
                error_msg = f"Error processing {req.id}: {e}"
                log.error(error_msg)
                final_results.append(TestResult(test_case_id=req.id, status="FAIL", reasoning=error_msg))
            finally:
                browser.close_browser()
                
        # 8. Reporter
        log.info("========== Generating Final Reports ==========")
        self.reporter.generate_all(final_results)
        log.info(f"Master Orchestrator Pipeline Complete! Check {self.run_dir} for reports.")
