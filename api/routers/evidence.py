from fastapi import APIRouter
from api.models import AgentResponse

router = APIRouter(
    prefix="/evidence",
    tags=["Evidence Agent"]
)

@router.post("/package", response_model=AgentResponse)
async def package_evidence():
    """
    Standalone endpoint to invoke only the EvidenceAgent.
    (Implementation stub - ready for future expansion)
    """
    return AgentResponse(status="success", message="Evidence packaged (stub)")
