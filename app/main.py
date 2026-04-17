from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging_config import configure_logging, get_logger
from app.core.telemetry import configure_tracing
from app.routes.analysis import router as analysis_router

settings = get_settings()
configure_logging(settings.log_level)
logger = get_logger(__name__)

app = FastAPI(title=settings.app_name, version="1.0.0")
app.include_router(analysis_router)
configure_tracing(app, settings)


@app.get("/")
async def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "health": "/health",
        "analyze_example": "/analyze/tech",
        "docs": "/docs",
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
