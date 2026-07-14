from fastapi import APIRouter
from api.models import AgentResponse

router = APIRouter(
    prefix="/verification",
    tags=["Verification Agent"]
)

@router.post("/verify", response_model=AgentResponse)
async def execute_verification():
    """
    Standalone endpoint to invoke only the VerificationAgent.
    (Implementation stub - ready for future expansion)
    """
    return AgentResponse(status="success", message="Verification executed (stub)")
