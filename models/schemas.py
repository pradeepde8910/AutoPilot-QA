"""
Data models for the AI Test Engineering Platform.
Using Pydantic for validation and structured typing.
"""
import uuid
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

class Evidence(BaseModel):
    """Represents a piece of evidence collected during testing."""
    id: str
    timestamp: datetime = Field(default_factory=datetime.now)
    evidence_type: Literal["screenshot", "dom_snapshot", "network_log", "console_log"]
    file_path: str
    description: str

class BrowserState(BaseModel):
    """Represents the current state of the browser."""
    current_url: str
    page_title: str
    dom_snapshot: Optional[str] = None
    accessibility_tree: Optional[dict] = None
    viewport_size: dict = Field(default_factory=lambda: {"width": 1280, "height": 720})
    latest_screenshot_path: Optional[str] = None

class Requirement(BaseModel):
    """Represents a single parsed requirement or user story."""
    id: str = Field(default_factory=lambda: f"REQ-{uuid.uuid4().hex[:6].upper()}")
    module: str = Field(default="General")
    feature: str = Field(default="Unknown")
    description: str
    preconditions: List[str] = Field(default_factory=list)
    test_data: str = Field(default="")
    expected_result: str = Field(default="")
    priority: str = Field(default="Medium")
    confidence: float = Field(default=1.0)
    business_rules: List[str] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)

class TestResult(BaseModel):
    """Represents the outcome of a test case execution."""
    test_case_id: str
    status: Literal["PENDING", "PASS", "FAIL", "PARTIAL", "NOT_EXECUTED"] = "PENDING"
    confidence_score: float = 0.0
    reasoning: str = ""
    suggested_fix: str = ""
    evidence_collected: List[Evidence] = Field(default_factory=list)
    execution_time_ms: int = 0

class TaskState(BaseModel):
    """Represents the state of an ongoing test execution task."""
    task_id: str
    target_requirement: Requirement
    expected_outcome: str
    status: Literal["IN_PROGRESS", "COMPLETED", "FAILED"] = "IN_PROGRESS"
    current_browser_state: Optional[BrowserState] = None
    step_history: List[str] = Field(default_factory=list)
    result: Optional[TestResult] = None
