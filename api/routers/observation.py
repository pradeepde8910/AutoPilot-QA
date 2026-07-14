from fastapi import APIRouter
from api.models import AgentResponse

router = APIRouter(
    prefix="/observation",
    tags=["Observation Agent"]
)

@router.post("/observe", response_model=AgentResponse)
async def execute_observation():
    """
    Standalone endpoint to invoke only the ObservationAgent.
    (Implementation stub - ready for future expansion)
    """
    return AgentResponse(status="success", message="Observation executed (stub)")
