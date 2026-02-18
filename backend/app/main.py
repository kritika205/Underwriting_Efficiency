"""
FastAPI Main Application
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1 import router as api_router
from app.api.health import router as health_router
from app.core.database import init_db, close_db
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown"""
    # Startup
    await init_db()
    yield
    # Shutdown
    await close_db()

app = FastAPI(
    title="Underwriting OCR Platform",
    description="Enterprise document processing with Azure OpenAI Vision",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS Middleware - Configure to allow frontend access
# settings.CORS_ORIGINS is already a list from config.py
cors_origins = list(settings.CORS_ORIGINS)  # Make a copy to avoid modifying settings

# Log the CORS configuration
logger.info(f"CORS configured with origins: {cors_origins}")
print(f"[CORS] Allowing origins: {cors_origins}")  # Also print for visibility

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Include health check routes (separated from root)
app.include_router(health_router, prefix="/api/health", tags=["Health"])

# Include API routes
app.include_router(api_router, prefix="/api/v1")

@app.get("/")
async def root():
    """
    Root endpoint - Service information
    
    This is NOT a health check endpoint.
    Use /api/health/ for health checks.
    """
    return {
        "service": "Underwriting OCR Platform",
        "version": "1.0.0",
        "description": "Enterprise document processing with Azure OpenAI Vision",
        "docs": "/docs",
        "health_check": "/api/health/"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

