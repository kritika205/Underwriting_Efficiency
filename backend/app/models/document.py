"""
Document Models
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone
from enum import Enum

class DocumentStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CLASSIFIED = "CLASSIFIED"

class DocumentType(str, Enum):
    AADHAAR = "AADHAAR"
    PAN = "PAN"
    PASSPORT = "PASSPORT"
    DRIVING_LICENSE = "DRIVING_LICENSE"
    VOTER_ID = "VOTER_ID"
    GST_RETURN = "GST_RETURN"
    ITR_FORM = "ITR_FORM"
    PAYSLIP = "PAYSLIP"
    BANK_STATEMENT = "BANK_STATEMENT"
    BALANCE_SHEET = "BALANCE_SHEET"
    SHOP_REGISTRATION = "SHOP_REGISTRATION"
    BUSINESS_LICENSE = "BUSINESS_LICENSE"
    CRIF = "CRIF"
    EXPERIAN = "EXPERIAN"
    EQUIFAX = "EQUIFAX"
    LOAN_SANCTION_LETTER = "LOAN_SANCTION_LETTER"
    EMI_SCHEDULE = "EMI_SCHEDULE"
    LOAN_AGREEMENT = "LOAN_AGREEMENT"
    RENT_AGREEMENT = "RENT_AGREEMENT"
    CIBIL_SCORE_REPORT = "CIBIL_SCORE_REPORT"
    DEALER_INVOICE = "DEALER_INVOICE"
    BUSINESS_REGISTRATION = "BUSINESS_REGISTRATION"
    LAND_RECORDS = "LAND_RECORDS"
    MEDICAL_BILLS = "MEDICAL_BILLS"
    ELECTRICITY_BILL = "ELECTRICITY_BILL"
    WATER_BILL = "WATER_BILL"
    OFFER_LETTER = "OFFER_LETTER"
    UNKNOWN = "UNKNOWN"

class Document(BaseModel):
    """Document model"""
    document_id: str = Field(..., description="Unique document identifier")
    user_id: str = Field(..., description="User identifier")
    application_id: Optional[str] = Field(None, description="Application/Case identifier")
    file_name: str = Field(..., description="Original file name")
    file_path: str = Field(..., description="Storage path")
    file_type: str = Field(..., description="File extension")
    file_size: int = Field(..., description="File size in bytes")
    mime_type: str = Field(..., description="MIME type")
    document_type: Optional[DocumentType] = Field(None, description="Classified document type")
    expected_document_type: Optional[str] = Field(None, description="Expected document type from UI")
    status: DocumentStatus = Field(DocumentStatus.PENDING, description="Processing status")
    uploaded_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    processed_at: Optional[datetime] = None
    ocr_text: Optional[str] = None
    extracted_data: Optional[Dict[str, Any]] = None
    quality_score: Optional[float] = Field(None, ge=0, le=100, description="Quality score 0-100")
    validation_warnings: List[str] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list, description="Validation errors including type mismatches")
    has_type_mismatch: bool = Field(False, description="Flag for document type mismatch")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "doc_123456",
                "user_id": "user_789",
                "application_id": "app_abc123",
                "file_name": "aadhaar.pdf",
                "file_path": "documents/user_789/doc_123456/original/aadhaar.pdf",
                "file_type": "pdf",
                "file_size": 245678,
                "mime_type": "application/pdf",
                "document_type": "AADHAAR",
                "status": "COMPLETED",
                "uploaded_at": "2024-01-15T10:30:00Z",
                "processed_at": "2024-01-15T10:30:45Z",
                "quality_score": 85.5
            }
        }

class DocumentCreate(BaseModel):
    """Document creation request"""
    user_id: str
    file_name: str
    file_type: str
    file_size: int
    mime_type: str

class DocumentResponse(BaseModel):
    """Document response model"""
    document_id: str
    user_id: str
    application_id: Optional[str] = None
    file_name: str
    document_type: Optional[str]
    status: str
    uploaded_at: datetime
    processed_at: Optional[datetime]
    quality_score: Optional[float]
    validation_warnings: List[str]
    validation_errors: List[str] = Field(default_factory=list)
    has_type_mismatch: bool = False

class DocumentUploadResponse(BaseModel):
    """Document upload response"""
    document_id: str
    status: str
    message: str
    uploaded_at: datetime





