from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from models.schemas import Requirement

class RunPipelineRequest(BaseModel):
    requirements: List[Requirement]

class AgentResponse(BaseModel):
    status: str
    message: str
    data: Optional[Dict[str, Any]] = None
