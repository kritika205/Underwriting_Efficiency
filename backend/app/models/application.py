"""
Application/Case Models
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from enum import Enum

class ApplicationStatus(str, Enum):
    """Application status"""
    SUBMITTED = "SUBMITTED"
    IN_REVIEW = "In Review"
    APPROVED = "Approved"
    REJECTED = "Rejected"
    CONDITIONAL_APPROVAL = "Conditionally Approved"

class Application(BaseModel):
    """Application/Case model"""
    application_id: str = Field(..., description="Unique application identifier")
    user_id: str = Field(..., description="User identifier")
    email: Optional[EmailStr] = Field(None, description="User email (for convenience)")
    name: Optional[str] = Field(None, description="User name (for convenience)")
    loan_type: Optional[str] = Field(None, description="Type of loan")
    applicant_type: Optional[str] = Field(None, description="Type of applicant")
    loan_amount: Optional[float] = Field(None, description="Loan amount")
    status: ApplicationStatus = Field(ApplicationStatus.IN_REVIEW, description="Application status")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    case_decision: Optional[str] = Field(None, description="Decision made on the case")
    case_notes: Optional[str] = Field(None, description="Notes about the case")
    case_conditions: Optional[Dict[str, Any]] = Field(None, description="Conditions for conditional approval")
    
    class Config:
        json_schema_extra = {
            "example": {
                "application_id": "app_123456",
                "user_id": "user_789",
                "email": "user@example.com",
                "name": "John Doe",
                "loan_type": "Personal Loan",
                "applicant_type": "Individual",
                "loan_amount": 500000.0,
                "status": "In Review",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }
        from_attributes = True

class ApplicationCreate(BaseModel):
    """Application creation request"""
    user_id: str
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    loan_type: Optional[str] = None
    applicant_type: Optional[str] = None
    loan_amount: Optional[float] = None

