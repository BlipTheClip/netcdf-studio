"""
NetCDF Studio — FastAPI application entry point.

Start the backend with:
    uvicorn backend.main:app --reload --port 8000

The Electron main process spawns this process and polls GET /api/health
until it receives a 200 response before opening the browser window.
"""

from __future__ import annotations

import logging
import logging.config
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.downloader import router as downloader_router
from backend.api.routes.imagery import router as imagery_router
from backend.api.routes.processor import router as processor_router

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_LOG_CONFIG: dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "default": {
            "format": "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        }
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "default"}
    },
    "root": {"level": "INFO", "handlers": ["console"]},
    "loggers": {
        # Verbose debug output from our own code
        "backend": {"level": "DEBUG", "propagate": True},
        # Suppress the per-request access log spam
        "uvicorn.access": {"level": "WARNING", "propagate": False},
    },
}

logging.config.dictConfig(_LOG_CONFIG)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("NetCDF Studio backend ready")
    yield
    logger.info("NetCDF Studio backend shutting down")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="NetCDF Studio API",
    description=(
        "REST + WebSocket backend for NetCDF Studio. "
        "Modules: A (downloader), B (processor), C (imagery), D (visualizer), E (MCP)."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow the React dev server and Electron's custom protocol in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Vite / CRA dev server
        "http://localhost:5173",  # Vite default port
        "app://*",               # Electron production (custom protocol)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers — add each module's router here as it is implemented
# ---------------------------------------------------------------------------

app.include_router(downloader_router)         # Module A — downloader
app.include_router(processor_router)          # Module B — processor
app.include_router(imagery_router)            # Module C — imagery

# Uncomment as modules are implemented:
# from backend.api.routes.visualizer import router as visualizer_router
# app.include_router(visualizer_router)        # Module D


# ---------------------------------------------------------------------------
# Core endpoints
# ---------------------------------------------------------------------------


@app.get("/api/health", tags=["core"])
async def health() -> dict:
    """
    Heartbeat endpoint polled by the Electron main process.
    Returns 200 as soon as the server is ready to accept requests.
    """
    return {"status": "ok", "version": "0.1.0"}
