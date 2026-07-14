from fastapi import APIRouter
from api.models import AgentResponse

router = APIRouter(
    prefix="/reporting",
    tags=["Reporting Agent"]
)

@router.post("/generate", response_model=AgentResponse)
async def generate_reports():
    """
    Standalone endpoint to invoke only the ReportingAgent.
    (Implementation stub - ready for future expansion)
    """
    return AgentResponse(status="success", message="Reports generated (stub)")
