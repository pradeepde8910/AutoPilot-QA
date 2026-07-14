from fastapi import APIRouter
from api.models import AgentResponse

router = APIRouter(
    prefix="/navigation",
    tags=["Navigation Agent"]
)

@router.post("/navigate", response_model=AgentResponse)
async def execute_navigation():
    """
    Standalone endpoint to invoke only the NavigationAgent.
    (Implementation stub - ready for future expansion)
    """
    return AgentResponse(status="success", message="Navigation executed (stub)")
