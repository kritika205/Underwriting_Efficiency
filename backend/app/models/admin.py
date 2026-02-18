"""
Admin Models
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime, timezone

class Admin(BaseModel):
    """Admin model"""
    admin_id: str = Field(..., description="Unique admin identifier")
    email: EmailStr = Field(..., description="Admin email")
    name: str = Field(..., description="Admin name")
    hashed_password: str = Field(..., description="Hashed password")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_login: Optional[datetime] = None
    is_active: bool = Field(default=True, description="Whether admin is active")
    
    class Config:
        json_schema_extra = {
            "example": {
                "admin_id": "admin_001",
                "email": "admin@admin.com",
                "name": "Admin User",
                "is_active": True
            }
        }
        
        from_attributes = True

class AdminCreate(BaseModel):
    """Admin creation request"""
    email: EmailStr
    name: str
    password: str

class AdminLogin(BaseModel):
    """Admin login request"""
    email: EmailStr
    password: str

class AdminResponse(BaseModel):
    """Admin response (without password)"""
    admin_id: str
    email: EmailStr
    name: str
    created_at: datetime
    last_login: Optional[datetime] = None
    is_active: bool

class TokenResponse(BaseModel):
    """Token response"""
    access_token: str
    token_type: str = "bearer"
    admin: AdminResponse
