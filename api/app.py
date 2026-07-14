from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import gradio as gr

# Import all routers
from api.routers import orchestrator, requirements, planner, navigation, observation, reflection, verification, evidence, reporting
from ui.gradio_app import gradio_app

app = FastAPI(
    title="AI Test Orchestration Service",
    description="A modular multi-agent orchestration framework for automated software testing.",
    version="1.0.0"
)

# Configure CORS for potential web dashboard integration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(orchestrator.router, prefix="/api/v1")
app.include_router(requirements.router, prefix="/api/v1")
app.include_router(planner.router, prefix="/api/v1")
app.include_router(navigation.router, prefix="/api/v1")
app.include_router(observation.router, prefix="/api/v1")
app.include_router(reflection.router, prefix="/api/v1")
app.include_router(verification.router, prefix="/api/v1")
app.include_router(evidence.router, prefix="/api/v1")
app.include_router(reporting.router, prefix="/api/v1")

# Mount reports directory to serve static HTML reports and artifacts
reports_dir = "reports"
os.makedirs(reports_dir, exist_ok=True)
app.mount("/reports", StaticFiles(directory=reports_dir), name="reports")

# Mount the Gradio Web UI
app = gr.mount_gradio_app(app, gradio_app, path="/")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "AI Test Orchestration Service"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.app:app", host="0.0.0.0", port=8000, reload=True)
