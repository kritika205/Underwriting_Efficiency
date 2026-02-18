"""
User Models
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Dict, Any
from datetime import datetime, timezone

class User(BaseModel):
    """User model"""
    user_id: str = Field(..., description="Unique user identifier")
    email: EmailStr = Field(..., description="User email")
    name: str = Field(..., description="User name")
    organization: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: Optional[datetime] = None
    api_key: Optional[str] = None
    subscription_tier: str = Field(default="basic", description="Subscription tier")
    case_status: Optional[str] = Field(None, description="Current case status (e.g., Approved, Rejected, In Review)")
    case_decision: Optional[str] = Field(None, description="Decision made on the case")
    case_notes: Optional[str] = Field(None, description="Notes about the case")
    case_conditions: Optional[Dict[str, Any]] = Field(None, description="Conditions for conditional approval")
    case_updated_at: Optional[datetime] = Field(None, description="Last update timestamp for case status")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_123",
                "email": "user@example.com",
                "name": "John Doe",
                "organization": "ABC Bank",
                "subscription_tier": "enterprise"
            }
        }
        
        from_attributes = True

class UserCreate(BaseModel):
    """User creation request"""
    email: EmailStr
    name: str
    organization: Optional[str] = None





