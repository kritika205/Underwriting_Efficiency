"""
Cross-Validation API Endpoints
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from app.services.cross_validation_service import cross_validation_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/document/{document_id}")
async def cross_validate_document(document_id: str):
    """
    Cross-validate a single document against customer datasheet
    
    - **document_id**: Document ID to validate
    """
    try:
        result = await cross_validation_service.cross_validate_document(document_id)
        return result
    except Exception as e:
        logger.error(f"Cross-validation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/{user_id}")
async def cross_validate_user(user_id: str):
    """
    Cross-validate all documents for a user against customer datasheet
    
    - **user_id**: User ID to validate
    """
    try:
        result = await cross_validation_service.cross_validate_user_documents(user_id)
        return result
    except Exception as e:
        logger.error(f"Cross-validation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/application/{application_id}")
async def cross_validate_application(application_id: str):
    """
    Cross-validate all documents for an application against customer datasheet
    
    - **application_id**: Application ID to validate
    """
    try:
        result = await cross_validation_service.cross_validate_application_documents(application_id)
        return result
    except Exception as e:
        logger.error(f"Cross-validation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all")
async def cross_validate_all(limit: Optional[int] = Query(None, description="Limit number of documents to validate")):
    """
    Cross-validate all documents in the system against customer datasheet
    
    - **limit**: Optional limit on number of documents
    """
    try:
        result = await cross_validation_service.cross_validate_all_documents(limit=limit)
        return result
    except Exception as e:
        logger.error(f"Cross-validation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


