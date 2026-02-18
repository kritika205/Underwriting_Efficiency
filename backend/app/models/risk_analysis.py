"""
Risk Analysis Models
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

class Anomaly(BaseModel):
    """Anomaly model"""
    type: str = Field(..., description="Type of anomaly")
    field: str = Field(..., description="Field where anomaly was detected")
    value: Any = Field(..., description="Value that triggered anomaly")
    reason: str = Field(..., description="Reason for anomaly")
    severity: str = Field(..., description="Severity level: critical, high, medium, low")

class Anomalies(BaseModel):
    """Collection of anomalies"""
    critical_anomalies: List[Anomaly] = Field(default_factory=list)
    high_anomalies: List[Anomaly] = Field(default_factory=list)
    medium_anomalies: List[Anomaly] = Field(default_factory=list)
    low_anomalies: List[Anomaly] = Field(default_factory=list)
    anomaly_count: int = Field(default=0)

class LLMReasoning(BaseModel):
    """LLM reasoning result"""
    summary: str = Field(..., description="Summary of risk analysis")
    risk_factors: List[str] = Field(default_factory=list, description="Key risk factors identified")
    recommendations: List[str] = Field(default_factory=list, description="LLM-generated recommendations")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in analysis")
    risk_assessment: Optional[Dict[str, Any]] = None
    anomaly_analysis: Optional[List[Dict[str, Any]]] = None

class RiskAnalysisResult(BaseModel):
    """Risk analysis result"""
    risk_score: float = Field(..., ge=0.0, le=100.0, description="Overall risk score 0-100")
    risk_level: str = Field(..., description="Risk level: LOW, MEDIUM, HIGH, CRITICAL")
    anomalies: Anomalies = Field(..., description="Detected anomalies")
    llm_reasoning: Optional[LLMReasoning] = None
    recommendations: List[str] = Field(default_factory=list, description="Actionable recommendations")
    analysis_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    class Config:
        json_schema_extra = {
            "example": {
                "risk_score": 45.5,
                "risk_level": "MEDIUM",
                "anomalies": {
                    "critical_anomalies": [],
                    "high_anomalies": [
                        {
                            "type": "name_mismatch_across_documents",
                            "field": "name",
                            "value": "Current: John Doe, Other: Jane Doe",
                            "reason": "Name mismatch with PAN document",
                            "severity": "high"
                        }
                    ],
                    "medium_anomalies": [],
                    "low_anomalies": [],
                    "anomaly_count": 1
                },
                "llm_reasoning": {
                    "summary": "High risk detected: 1 high-severity anomaly found that needs review.",
                    "risk_factors": ["HIGH: Name mismatch with PAN document"],
                    "recommendations": ["REVIEW: Document requires detailed manual verification."],
                    "confidence": 0.85
                },
                "recommendations": [
                    "MANUAL REVIEW: Document requires detailed manual verification",
                    "VERIFY: Cross-check with original physical document"
                ],
                "analysis_timestamp": "2024-01-15T11:00:00Z"
            }
        }

class RiskAnalysisRequest(BaseModel):
    """Risk analysis request"""
    document_id: str = Field(..., description="Document ID to analyze")
    include_llm_reasoning: bool = Field(default=True, description="Include LLM reasoning in analysis")

class RiskAnalysisResponse(BaseModel):
    """Risk analysis API response"""
    document_id: str
    document_type: str
    risk_score: float
    risk_level: str
    anomalies: Dict[str, Any]
    llm_reasoning: Optional[Dict[str, Any]] = None
    recommendations: List[str]
    analysis_timestamp: datetime

