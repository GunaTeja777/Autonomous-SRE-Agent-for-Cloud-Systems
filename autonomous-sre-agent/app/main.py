import asyncio
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.utils.logger import setup_logging, get_logger
from app.orchestrator.incident_orchestrator import IncidentOrchestrator
from app.api import health, routes

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize logger
    setup_logging()
    logger.info("application_starting")

    # Initialize the core SRE Orchestrator
    orchestrator = IncidentOrchestrator()
    app.state.orchestrator = orchestrator

    # Background task for periodic scanning
    settings = get_settings()
    namespace = settings.k8s_namespace
    
    async def periodic_scan():
        logger.info("background_sre_scanner_started", namespace=namespace)
        while True:
            try:
                await orchestrator.run_tick(namespace)
            except Exception as e:
                logger.error("background_sre_scan_tick_failed", error=str(e))
            # Scan every 30 seconds
            await asyncio.sleep(30)

    scan_task = asyncio.create_task(periodic_scan())
    yield
    # Cleanup background task on shutdown
    logger.info("application_shutting_down")
    scan_task.cancel()
    try:
        await scan_task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Autonomous SRE Agent",
    description="Production-style SRE Agent for Cloud Systems.",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(routes.router, prefix="/api")

# Mount web dashboard static files
import os
from fastapi.staticfiles import StaticFiles

web_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
if os.path.exists(web_dir):
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.environment == "development",
    )
