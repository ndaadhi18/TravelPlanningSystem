from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router
from backend.core.settings import get_settings
from backend.utils.logger import get_logger

logger = get_logger("backend.main")
app = FastAPI(title="PlanIT Travel Planner API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)

@app.on_event("startup")
async def startup_event() -> None:
    settings = get_settings()
    logger.info("PlanIT startup complete")
    logger.info("OpenAI model: %s", settings.openai_model_name)
    logger.info("MCP server URL: %s", settings.mcp_server_url)

@app.get("/")
def read_root():
    return {"message": "PlanIT API is running"}

@app.get("/health")
def health():
    settings = get_settings()
    return {
        "status": "ok",
        "backend": "PlanIT",
        "openai_model_name": settings.openai_model_name,
        "mcp_server_url": settings.mcp_server_url,
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)