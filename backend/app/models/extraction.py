"""
Extraction Result Models
"""
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

class ExtractionResult(BaseModel):
    """Extraction result model"""
    document_id: str
    user_id: str = Field(..., description="User identifier for tracking")
    document_type: str
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)
    confidence_scores: Dict[str, float] = Field(default_factory=dict)
    extraction_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1.0"
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_id": "doc_123456",
                "user_id": "user_789",
                "document_type": "AADHAAR",
                "extracted_fields": {
                    "name": "John Doe",
                    "aadhaar_number": "1234 5678 9012",
                    "date_of_birth": "1990-01-15",
                    "address": "123 Main St, City, State"
                },
                "confidence_scores": {
                    "name": 0.95,
                    "aadhaar_number": 0.98,
                    "date_of_birth": 0.92
                }
            }
        }

class ExtractionResponse(BaseModel):
    """Extraction response"""
    document_id: str
    user_id: str
    document_type: str
    extracted_data: Dict[str, Any]
    quality_score: float
    validation_warnings: list
    confidence_scores: Dict[str, float]


class DocumentExtractionDetail(BaseModel):
    """Individual document extraction detail - only extracted details and document type"""
    document_id: str
    document_type: str
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)


class UserDocumentAggregation(BaseModel):
    """Aggregated model storing all extracted details of a user's documents in a single JSON schema"""
    user_id: str = Field(..., description="User identifier")
    documents: Dict[str, DocumentExtractionDetail] = Field(
        default_factory=dict,
        description="Dictionary of document_id -> DocumentExtractionDetail"
    )
    documents_by_type: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Dictionary of document_type -> list of document_ids"
    )
    total_documents: int = Field(default=0, description="Total number of documents")
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = "1.0"
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "user_789",
                "total_documents": 2,
                "documents": {
                    "doc_123456": {
                        "document_id": "doc_123456",
                        "document_type": "AADHAAR",
                        "extracted_fields": {
                            "name": "John Doe",
                            "aadhaar_number": "1234 5678 9012",
                            "date_of_birth": "1990-01-15",
                            "address": "123 Main St, City, State"
                        }
                    },
                    "doc_789012": {
                        "document_id": "doc_789012",
                        "document_type": "PAN",
                        "extracted_fields": {
                            "name": "John Doe",
                            "pan_number": "ABCDE1234F"
                        }
                    }
                },
                "documents_by_type": {
                    "AADHAAR": ["doc_123456"],
                    "PAN": ["doc_789012"]
                },
                "last_updated": "2024-01-15T11:00:00Z",
                "created_at": "2024-01-15T10:30:00Z"
            }
        }





