"""
Document Classification API Endpoints
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.services.classification_service import classification_service
from app.services.storage_service import storage_service
from app.core.database import get_database
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class ClassifyRequest(BaseModel):
    document_id: str
    ocr_text: Optional[str] = None

class ClassifyResponse(BaseModel):
    document_id: str
    document_type: str
    confidence: float
    message: str

@router.post("/", response_model=ClassifyResponse)
async def classify_document(request: ClassifyRequest):
    """
    Classify document type
    
    - **document_id**: Document identifier
    - **ocr_text**: Optional pre-extracted OCR text
    """
    try:
        # Get document from database
        db = await get_database()
        doc = await db.documents.find_one({"document_id": request.document_id})
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Classify document
        classification_result = await classification_service.classify_document(
            doc["file_path"],
            ocr_text=request.ocr_text or doc.get("ocr_text")
        )
        
        # Update document in database
        update_data = {
            "document_type": classification_result["document_type"].value,
            "status": "CLASSIFIED"
        }
        
        if classification_result.get("ocr_text"):
            update_data["ocr_text"] = classification_result["ocr_text"]
        
        await db.documents.update_one(
            {"document_id": request.document_id},
            {"$set": update_data}
        )
        
        logger.info(f"Document classified: {request.document_id} as {classification_result['document_type']}")
        
        return ClassifyResponse(
            document_id=request.document_id,
            document_type=classification_result["document_type"].value,
            confidence=classification_result["confidence"],
            message="Document classified successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Classification failed: {e}")
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")






