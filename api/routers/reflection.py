from fastapi import APIRouter
from api.models import AgentResponse

router = APIRouter(
    prefix="/reflection",
    tags=["Reflection Agent"]
)

@router.post("/reflect", response_model=AgentResponse)
async def execute_reflection():
    """
    Standalone endpoint to invoke only the ReflectionAgent.
    (Implementation stub - ready for future expansion)
    """
    return AgentResponse(status="success", message="Reflection executed (stub)")
