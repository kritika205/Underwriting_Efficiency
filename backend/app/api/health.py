"""
Health Check API Endpoints
Separated from root endpoint for better organization
"""
from fastapi import APIRouter
from app.core.database import get_database
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/")
async def health_check():
    """
    Detailed health check endpoint
    
    Returns:
    - status: Service health status
    - database: Database connection status
    - azure_openai: Azure OpenAI configuration status
    """
    try:
        # Check database connection
        db = await get_database()
        # Try a simple operation to verify connection
        await db.users.find_one({}, {"_id": 1})
        database_status = "connected"
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        database_status = "disconnected"
    
    # Check Azure OpenAI configuration
    from app.core.config import settings
    azure_status = "configured" if settings.AZURE_OPENAI_API_KEY else "not_configured"
    
    return {
        "status": "healthy",
        "database": database_status,
        "azure_openai": azure_status,
        "service": "Underwriting OCR Platform",
        "version": "1.0.0"
    }

@router.get("/ping")
async def ping():
    """
    Simple ping endpoint for quick connectivity check
    """
    return {
        "status": "ok",
        "message": "pong"
    }


