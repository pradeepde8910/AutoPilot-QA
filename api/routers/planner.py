from fastapi import APIRouter
from api.models import AgentResponse

router = APIRouter(
    prefix="/planner",
    tags=["Planner Agent"]
)

@router.post("/plan", response_model=AgentResponse)
async def generate_plan():
    """
    Standalone endpoint to invoke only the PlannerAgent.
    (Implementation stub - ready for future expansion)
    """
    return AgentResponse(status="success", message="Planner executed (stub)")
