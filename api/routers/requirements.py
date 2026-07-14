from fastapi import APIRouter
from api.models import AgentResponse

router = APIRouter(
    prefix="/requirements",
    tags=["Requirement Analysis Agent"]
)

@router.post("/analyze", response_model=AgentResponse)
async def analyze_requirements():
    """
    Standalone endpoint to invoke only the RequirementAnalysisAgent.
    (Implementation stub - ready for future expansion)
    """
    return AgentResponse(status="success", message="Requirement Analysis executed (stub)")
