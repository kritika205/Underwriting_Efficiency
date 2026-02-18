"""
Document Management API Endpoints
"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional
import uuid
import asyncio
from datetime import datetime
from app.models.document import (
    Document, DocumentCreate, DocumentResponse, DocumentUploadResponse,
    DocumentStatus
)
from app.services.storage_service import storage_service
from app.services.user_aggregation_service import user_aggregation_service
from app.core.database import get_database
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    user_id: str = Form(None),
    application_id: str = Form(None),
    expected_document_type: str = Form(None)
):
    """
    Upload a document for processing
    
    - **file**: Document file (PDF, JPG, PNG, TIFF)
    - **user_id**: User identifier
    - **application_id**: Application/Case identifier (optional but recommended)
    """
    try:
        # Validate file type
        file_ext = file.filename.split('.')[-1].lower() if '.' in file.filename else ''
        allowed_types = [t.strip() for t in settings.ALLOWED_FILE_TYPES.split(',')]
        
        if file_ext not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"File type not allowed. Allowed types: {', '.join(allowed_types)}"
            )
        
        # Validate file size
        file_content = await file.read()
        file_size_mb = len(file_content) / (1024 * 1024)
        
        if file_size_mb > settings.MAX_FILE_SIZE_MB:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB"
            )
        
        # Generate document ID
        document_id = f"doc_{uuid.uuid4().hex[:12]}"
        
        # Default user_id if not provided
        if not user_id:
            user_id = "default_user"
        
        # Save file
        file_path = await storage_service.save_file(
            file_content,
            user_id,
            document_id,
            file.filename
        )
        
        # Create document record
        document = Document(
            document_id=document_id,
            user_id=user_id,
            application_id=application_id,
            file_name=file.filename,
            file_path=file_path,
            file_type=file_ext,
            file_size=len(file_content),
            mime_type=file.content_type or "application/octet-stream",
            status=DocumentStatus.PENDING,
            expected_document_type=expected_document_type
        )
        
        # Save to database
        db = await get_database()
        await db.documents.insert_one(document.model_dump())
        
        logger.info(f"Document uploaded: {document_id}")
        
        return DocumentUploadResponse(
            document_id=document_id,
            status="PENDING",
            message="Document uploaded successfully",
            uploaded_at=document.uploaded_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """Get document details by ID"""
    try:
        db = await get_database()
        doc = await db.documents.find_one({"document_id": document_id})
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Remove MongoDB _id
        doc.pop("_id", None)
        
        return DocumentResponse(**doc)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[DocumentResponse])
async def list_documents(
    user_id: Optional[str] = None,
    application_id: Optional[str] = None,
    status: Optional[str] = None,
    document_type: Optional[str] = None,
    limit: int = 50,
    skip: int = 0
):
    """List documents with optional filters"""
    try:
        db = await get_database()
        query = {}
        
        if user_id:
            query["user_id"] = user_id
        if application_id:
            query["application_id"] = application_id
        if status:
            query["status"] = status
        if document_type:
            query["document_type"] = document_type
        
        cursor = db.documents.find(query).skip(skip).limit(limit).sort("uploaded_at", -1)
        documents = await cursor.to_list(length=limit)
        
        # Remove _id from each document
        for doc in documents:
            doc.pop("_id", None)
        
        return [DocumentResponse(**doc) for doc in documents]
        
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{document_id}")
async def delete_document(document_id: str):
    """Delete a document"""
    try:
        db = await get_database()
        doc = await db.documents.find_one({"document_id": document_id})
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        user_id = doc.get("user_id")
        file_path = doc.get("file_path")
        
        # Run all deletion operations in parallel for better performance
        # Prepare all deletion tasks
        tasks = [
            # Delete file and directory from storage
            storage_service.delete_file_and_directory(file_path),
            # Delete from database collections in parallel
            db.documents.delete_one({"document_id": document_id}),
            db.extraction_results.delete_many({"document_id": document_id}),
            db.risk_analyses.delete_many({"document_id": document_id}),
        ]
        
        # Execute all deletions in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Check for exceptions in results (excluding the first one which is the file deletion result)
        for i, result in enumerate(results[1:], start=1):
            if isinstance(result, Exception):
                logger.warning(f"Error during parallel deletion operation {i}: {result}")
        
        # Update user aggregation (should be done after DB deletions)
        if user_id:
            try:
                await user_aggregation_service.remove_document_from_aggregation(
                    user_id, document_id
                )
            except Exception as e:
                logger.warning(f"Failed to update user aggregation: {e}")
        
        return {"message": "Document deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{document_id}/status")
async def get_document_status(document_id: str):
    """Get processing status of a document"""
    try:
        db = await get_database()
        doc = await db.documents.find_one(
            {"document_id": document_id},
            {"status": 1, "document_type": 1, "processed_at": 1, "quality_score": 1}
        )
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {
            "document_id": document_id,
            "status": doc.get("status"),
            "document_type": doc.get("document_type"),
            "processed_at": doc.get("processed_at"),
            "quality_score": doc.get("quality_score")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/{user_id}/all")
async def get_user_all_documents(user_id: str):
    """
    Get all documents for a specific user, grouped by document type
    
    Returns all documents (Aadhar, PAN, DL, etc.) for the given user_id
    """
    try:
        db = await get_database()
        
        # Find all documents for this user
        cursor = db.documents.find({"user_id": user_id}).sort("uploaded_at", -1)
        documents = await cursor.to_list(length=None)
        
        # Remove _id from each document
        for doc in documents:
            doc.pop("_id", None)
        
        # Group documents by type
        grouped_docs = {}
        for doc in documents:
            doc_type = doc.get("document_type", "UNKNOWN")
            if doc_type not in grouped_docs:
                grouped_docs[doc_type] = []
            grouped_docs[doc_type].append(DocumentResponse(**doc))
        
        return {
            "user_id": user_id,
            "total_documents": len(documents),
            "documents_by_type": grouped_docs,
            "all_documents": [DocumentResponse(**doc) for doc in documents]
        }
        
    except Exception as e:
        logger.error(f"Failed to get user documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/{user_id}/summary")
async def get_user_documents_summary(user_id: str):
    """
    Get a summary of all document types for a specific user
    
    Returns count of each document type (Aadhar, PAN, DL, etc.) for the user
    """
    try:
        db = await get_database()
        
        # Aggregate documents by type
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$document_type",
                "count": {"$sum": 1},
                "latest_upload": {"$max": "$uploaded_at"}
            }},
            {"$sort": {"count": -1}}
        ]
        
        result = await db.documents.aggregate(pipeline).to_list(length=None)
        
        summary = {
            "user_id": user_id,
            "document_types": {}
        }
        
        for item in result:
            doc_type = item.get("_id", "UNKNOWN")
            summary["document_types"][doc_type] = {
                "count": item.get("count", 0),
                "latest_upload": item.get("latest_upload")
            }
        
        return summary
        
    except Exception as e:
        logger.error(f"Failed to get user summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/application/{application_id}/all")
async def get_application_all_documents(application_id: str):
    """
    Get all documents for a specific application, grouped by document type
    
    Returns all documents (Aadhar, PAN, DL, etc.) for the given application_id
    """
    try:
        db = await get_database()
        
        # Find all documents for this application
        cursor = db.documents.find({"application_id": application_id}).sort("uploaded_at", -1)
        documents = await cursor.to_list(length=None)
        
        # Remove _id from each document
        for doc in documents:
            doc.pop("_id", None)
        
        # Group documents by type
        grouped_docs = {}
        for doc in documents:
            doc_type = doc.get("document_type", "UNKNOWN")
            if doc_type not in grouped_docs:
                grouped_docs[doc_type] = []
            grouped_docs[doc_type].append(DocumentResponse(**doc))
        
        return {
            "application_id": application_id,
            "total_documents": len(documents),
            "documents_by_type": grouped_docs,
            "all_documents": [DocumentResponse(**doc) for doc in documents]
        }
        
    except Exception as e:
        logger.error(f"Failed to get application documents: {e}")
        raise HTTPException(status_code=500, detail=str(e))





