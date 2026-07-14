from fastapi import APIRouter, HTTPException
from api.models import RunPipelineRequest, AgentResponse
from agents.orchestrator import OrchestratorAgent
from utils.logger import log

router = APIRouter(
    prefix="/pipeline",
    tags=["Orchestration"]
)

@router.post("/run", response_model=AgentResponse)
async def run_pipeline(request: RunPipelineRequest):
    """
    Runs the complete end-to-end test pipeline using the OrchestratorAgent.
    """
    try:
        log.info(f"API Request: /pipeline/run with {len(request.requirements)} requirements")
        orchestrator = OrchestratorAgent()
        
        # Execute the pipeline synchronously
        orchestrator.run(request.requirements)
        
        return AgentResponse(
            status="completed",
            message=f"Pipeline executed successfully for {len(request.requirements)} requirements.",
            data={"report_dir": str(orchestrator.run_dir)}
        )
    except Exception as e:
        log.error(f"Pipeline execution failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
