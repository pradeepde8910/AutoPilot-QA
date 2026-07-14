"""
State Engine for the AI Test Engineering Platform.
Provides the centralized AgentState that all agents read from and write to.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
from models.schemas import Requirement, BrowserState, Evidence

class Observation(BaseModel):
    """An observation made by the Observation Agent."""
    timestamp: datetime = Field(default_factory=datetime.now)
    description: str
    raw_data: Optional[Dict[str, Any]] = None

class AgentState(BaseModel):
    """
    The global state engine. 
    Every agent reads and writes to this state. 
    Agents do not communicate directly.
    """
    # High-level context
    website: str = ""
    
    # Execution Context
    current_page: str = ""
    current_requirement: Optional[Requirement] = None
    current_task: str = ""
    
    # State data
    browser_state: Optional[BrowserState] = None
    observations: List[Observation] = Field(default_factory=list)
    history: List[str] = Field(default_factory=list)
    evidence: List[Evidence] = Field(default_factory=list)
    
    # Failures and debugging
    failures: List[str] = Field(default_factory=list)
    screenshots: List[str] = Field(default_factory=list)

    def log_history(self, event: str):
        """Helper to append to the agent history log."""
        self.history.append(event)
        
    def add_failure(self, failure: str):
        """Helper to record a failure during execution."""
        self.failures.append(failure)
        
    def add_screenshot(self, path: str):
        """Helper to record a screenshot path."""
        self.screenshots.append(path)
        
    def add_observation(self, obs: Observation):
        """Helper to record an observation from the DOM/Vision."""
        self.observations.append(obs)
