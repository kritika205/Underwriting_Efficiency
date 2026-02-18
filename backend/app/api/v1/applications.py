"""
Application Management API Endpoints
"""
from fastapi import APIRouter, HTTPException, Body
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
from app.models.application import Application, ApplicationCreate, ApplicationStatus
from app.core.database import get_database
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

def _normalize_application_status(value: Any) -> str:
    """
    Normalize application status values to match ApplicationStatus enum.
    Handles legacy statuses and UI variations.
    """
    if not isinstance(value, str):
        return value
    
    s = value.strip()
    
    # Handle legacy DRAFT status
    if s.upper() == "DRAFT":
        return ApplicationStatus.SUBMITTED.value
    
    # Handle UI variation: "Conditionally Approved" -> "Conditionally Approved"
    if s == "Conditionally Approved":
        return ApplicationStatus.CONDITIONALLY_APPROVED.value
    
    # Normalize common variations
    if s.upper() in ("IN_REVIEW", "IN REVIEW"):
        return ApplicationStatus.IN_REVIEW.value
    if s.upper() == "APPROVED":
        return ApplicationStatus.APPROVED.value
    if s.upper() == "REJECTED":
        return ApplicationStatus.REJECTED.value
    if s.upper() == "SUBMITTED":
        return ApplicationStatus.SUBMITTED.value
    if s == "Conditional Approved":
        return ApplicationStatus.CONDITIONALLY_APPROVED.value
    
    # Return as-is if it's already a valid enum value
    return s

@router.post("/", response_model=Application)
async def create_application(application_data: ApplicationCreate):
    """
    Create a new application/case
    
    - **user_id**: User identifier (required)
    - **email**: User email (optional, for convenience)
    - **name**: User name (optional, for convenience)
    - **loan_type**: Type of loan (optional)
    - **applicant_type**: Type of applicant (optional)
    - **loan_amount**: Loan amount (optional)
    """
    try:
        db = await get_database()
        
        # Validate user_id
        if not application_data.user_id or not application_data.user_id.strip():
            raise HTTPException(status_code=422, detail="user_id is required and cannot be empty")
        
        # Generate application_id
        application_id = f"app_{uuid.uuid4().hex[:12]}"
        
        # Create application
        application = Application(
            application_id=application_id,
            user_id=application_data.user_id.strip(),
            email=application_data.email,
            name=application_data.name,
            loan_type=application_data.loan_type,
            applicant_type=application_data.applicant_type,
            loan_amount=application_data.loan_amount,
            status=ApplicationStatus.IN_REVIEW,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Save to database
        await db.applications.insert_one(application.model_dump())
        
        logger.info(f"Application created: {application_id} for user: {application_data.user_id}")
        
        return application
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create application: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[Application])
async def list_applications(
    user_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    skip: int = 0
):
    """Get all applications with optional filters"""
    try:
        db = await get_database()
        query = {}
        
        if user_id:
            query["user_id"] = user_id
        if status:
            query["status"] = _normalize_application_status(status)
        
        cursor = db.applications.find(query).skip(skip).limit(limit).sort("created_at", -1)
        applications = await cursor.to_list(length=limit)
        
        # Remove _id from each application and normalize statuses
        result = []
        for app in applications:
            app.pop("_id", None)
            # Normalize legacy statuses before validation
            if "status" in app:
                app["status"] = _normalize_application_status(app.get("status"))
            result.append(Application.model_validate(app))
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to list applications: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{application_id}", response_model=Application)
async def get_application(application_id: str):
    """Get application by ID"""
    try:
        db = await get_database()
        application = await db.applications.find_one({"application_id": application_id})
        
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        
        application.pop("_id", None)
        # Normalize legacy statuses before validation
        if "status" in application:
            application["status"] = _normalize_application_status(application.get("status"))
        return Application.model_validate(application)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get application: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{application_id}/status")
async def update_application_status(
    application_id: str,
    request_data: Dict[str, Any] = Body(...)
):
    """Update application status and decision"""
    try:
        db = await get_database()
        application = await db.applications.find_one({"application_id": application_id})
        
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        
        # Update application with status and decision
        update_data = {
            "updated_at": datetime.now(timezone.utc)
        }
        
        if request_data.get("status"):
            update_data["status"] = _normalize_application_status(request_data["status"])
        if request_data.get("decision"):
            update_data["case_decision"] = request_data["decision"]
        if request_data.get("notes"):
            update_data["case_notes"] = request_data["notes"]
        if request_data.get("conditions"):
            update_data["case_conditions"] = request_data["conditions"]
        
        await db.applications.update_one(
            {"application_id": application_id},
            {"$set": update_data}
        )
        
        logger.info(f"Application status updated: {application_id} -> {update_data.get('status', 'N/A')}")
        
        # Return updated application
        updated_application = await db.applications.find_one({"application_id": application_id})
        if not updated_application:
            raise HTTPException(status_code=404, detail="Application not found after update")
        
        updated_application.pop("_id", None)
        # Normalize legacy statuses before validation
        if "status" in updated_application:
            updated_application["status"] = _normalize_application_status(updated_application.get("status"))
        return Application.model_validate(updated_application)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update application status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{application_id}")
async def delete_application(application_id: str):
    """Delete an application by ID"""
    try:
        db = await get_database()
        application = await db.applications.find_one({"application_id": application_id})
        
        if not application:
            raise HTTPException(status_code=404, detail="Application not found")
        
        # Delete application
        await db.applications.delete_one({"application_id": application_id})
        
        logger.info(f"Application deleted: {application_id}")
        
        return {"message": f"Application {application_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete application: {e}")
        raise HTTPException(status_code=500, detail=str(e))

