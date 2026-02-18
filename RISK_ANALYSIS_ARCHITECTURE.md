# Risk Analysis Architecture

## Overview

The Risk Analysis module performs anomaly detection using rule-based processes and LLM reasoning to assess underwriting risk. It integrates seamlessly with the existing extraction and validation pipeline.

## Architecture Flow

```
Document Upload
    ↓
OCR Extraction
    ↓
Validation (Business Rules + Customer Profile)
    ↓
Risk Analysis ← NEW
    ├── Rule-Based Anomaly Detection
    ├── Cross-Document Consistency Checks
    ├── Fraud Pattern Detection
    └── LLM Reasoning (for critical/high anomalies)
    ↓
Risk Score & Recommendations
```

## Components

### 1. Risk Analysis Service (`risk_analysis_service.py`)

**Main Function**: `analyze_risk()`
- Performs comprehensive risk analysis
- Returns risk score, anomalies, LLM reasoning, and recommendations

**Key Methods**:
- `_detect_anomalies()`: Rule-based anomaly detection
- `_get_llm_reasoning()`: LLM-based reasoning for anomalies
- `_calculate_risk_score()`: Calculate overall risk score (0-100)
- `_generate_recommendations()`: Generate actionable recommendations

### 2. Anomaly Detection

#### Rule-Based Detection by Document Type

**Aadhaar**:
- Suspicious Aadhaar patterns (all same digits, sequential)
- Invalid age calculations
- Name inconsistencies
- Incomplete addresses

**PAN**:
- Suspicious PAN patterns
- Name similarity issues (name vs father's name)

**Payslip**:
- Salary calculation errors (net > gross)
- Unusually high deductions (>50%)
- Negative salaries
- Future-dated or very old payslips

**Bank Statement**:
- Uniform transaction patterns
- Unusually large transactions

**CIBIL**:
- Invalid credit scores
- Very low scores (<500)
- Overdue accounts

**ITR/GST**:
- Future-dated documents
- Suspicious ID patterns

#### Cross-Document Consistency Checks
- Name mismatches across documents
- Date of birth mismatches
- Address inconsistencies

#### Fraud Pattern Detection
- Test/placeholder values (test, sample, dummy, xxxx, 0000, 1234)
- Suspicious sequential patterns

#### Data Quality Anomalies
- Low quality scores (<50)
- Multiple validation errors
- Many validation warnings

### 3. Risk Scoring

**Risk Score Calculation** (0-100):
- Critical anomalies: +25 points each
- High anomalies: +15 points each
- Medium anomalies: +8 points each
- Low anomalies: +3 points each
- Quality penalty: (100 - quality_score) * 0.2

**Risk Levels**:
- **LOW**: 0-29 (Acceptable)
- **MEDIUM**: 30-59 (Review recommended)
- **HIGH**: 60-79 (Manual review required)
- **CRITICAL**: 80-100 (Reject/Investigate)

### 4. LLM Reasoning

**When Triggered**:
- Only for documents with critical or high-severity anomalies
- Uses Azure OpenAI GPT-4 for reasoning

**Output**:
- Risk assessment summary
- Risk factor identification
- Anomaly analysis with reasoning
- Specific recommendations (ACCEPT/REVIEW/REJECT)
- Confidence score

**Prompt Structure**:
- Document type and extracted data
- Validation results
- Detected anomalies
- Request for risk assessment and recommendations

### 5. Recommendations

**Automatic Recommendations**:
- **CRITICAL**: Reject, escalate to fraud team
- **HIGH**: Manual review, verify with original document
- **MEDIUM**: Review by underwriter, request clarification
- **LOW**: Proceed with standard processing

**LLM-Generated Recommendations**:
- Context-aware actions
- Additional documents needed
- Specific verification steps

## API Endpoints

### POST `/api/v1/risk-analysis/`
Perform risk analysis on a document

**Request**:
```json
{
  "document_id": "doc_123456",
  "include_llm_reasoning": true
}
```

**Response**:
```json
{
  "document_id": "doc_123456",
  "document_type": "AADHAAR",
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
    "summary": "High risk detected: 1 high-severity anomaly found...",
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
```

### GET `/api/v1/risk-analysis/{document_id}`
Get risk analysis result for a document

### GET `/api/v1/risk-analysis/user/{user_id}/summary`
Get risk summary for all documents of a user

## Database Schema

### Collection: `risk_analyses`

```json
{
  "document_id": "doc_123456",
  "user_id": "user_789",
  "document_type": "AADHAAR",
  "risk_score": 45.5,
  "risk_level": "MEDIUM",
  "anomalies": {
    "critical_anomalies": [],
    "high_anomalies": [...],
    "medium_anomalies": [],
    "low_anomalies": [],
    "anomaly_count": 1
  },
  "llm_reasoning": {...},
  "recommendations": [...],
  "analysis_timestamp": ISODate("2024-01-15T11:00:00Z")
}
```

### Document Collection Update

Risk analysis updates the `documents` collection with:
- `risk_score`: Overall risk score
- `risk_level`: Risk level (LOW/MEDIUM/HIGH/CRITICAL)

## Integration Options

### Option 1: Manual Risk Analysis (Current Implementation)
After extraction, call risk analysis endpoint separately:
```python
# Step 1: Extract
POST /api/v1/ocr-extract/
{
  "document_id": "doc_123"
}

# Step 2: Analyze Risk
POST /api/v1/risk-analysis/
{
  "document_id": "doc_123"
}
```

### Option 2: Automatic Risk Analysis (Optional)
Integrate into OCR extraction pipeline to run automatically after validation.

**To enable**: Modify `backend/app/api/v1/ocr_extract.py` to call risk analysis after Step 5 (validation).

## Usage Example

```python
from app.services.risk_analysis_service import risk_analysis_service
from app.models.document import DocumentType

# Perform risk analysis
risk_result = await risk_analysis_service.analyze_risk(
    extracted_data=extracted_fields,
    document_type=DocumentType.AADHAAR,
    validation_result=validation_result,
    user_id="user_123",
    all_user_documents=user_docs
)

# Access results
print(f"Risk Score: {risk_result['risk_score']}")
print(f"Risk Level: {risk_result['risk_level']}")
print(f"Anomalies: {risk_result['anomalies']['anomaly_count']}")
print(f"Recommendations: {risk_result['recommendations']}")
```

## Benefits

1. **Automated Risk Detection**: Identifies anomalies automatically
2. **Rule-Based + LLM**: Combines deterministic rules with AI reasoning
3. **Cross-Document Analysis**: Checks consistency across user's documents
4. **Actionable Recommendations**: Provides specific next steps
5. **Scalable**: Can process thousands of documents
6. **Audit Trail**: All analyses stored in database

## Future Enhancements

1. **Machine Learning Models**: Train ML models on historical fraud cases
2. **Real-time Alerts**: Notify fraud team for critical risks
3. **Risk Score Calibration**: Adjust thresholds based on business needs
4. **Advanced LLM Integration**: Use GPT-4 Vision for document image analysis
5. **Risk Dashboard**: Visual analytics for risk trends
6. **Custom Rules Engine**: Allow business users to define custom rules

## Configuration

Risk thresholds can be adjusted in `risk_analysis_service.py`:
```python
self.risk_thresholds = {
    "low": 0.0,
    "medium": 30.0,
    "high": 60.0,
    "critical": 80.0
}
```

## Testing

Test risk analysis with various document types and anomaly scenarios:
- Documents with suspicious patterns
- Cross-document inconsistencies
- Low quality extractions
- Fraud indicators

