"""
Risk Analysis Prompts for LLM Reasoning
"""
from typing import Dict, Any
from app.models.document import DocumentType
import json

def get_risk_analysis_prompt(
    extracted_data: Dict[str, Any],
    document_type: DocumentType,
    anomalies: Dict[str, Any],
    validation_result: Dict[str, Any]
) -> str:
    """
    Get risk analysis prompt for LLM reasoning
    
    Args:
        extracted_data: Extracted fields from document
        document_type: Type of document
        anomalies: Detected anomalies
        validation_result: Validation results
    
    Returns:
        Prompt for LLM risk analysis
    """
    
    # Format anomalies for prompt
    critical_anomalies = anomalies.get("critical_anomalies", [])
    high_anomalies = anomalies.get("high_anomalies", [])
    
    anomalies_text = ""
    if critical_anomalies:
        anomalies_text += "\nCRITICAL ANOMALIES:\n"
        for anomaly in critical_anomalies:
            anomalies_text += f"- {anomaly.get('type')}: {anomaly.get('reason')} (Field: {anomaly.get('field')}, Value: {anomaly.get('value')})\n"
    
    if high_anomalies:
        anomalies_text += "\nHIGH SEVERITY ANOMALIES:\n"
        for anomaly in high_anomalies[:10]:  # Limit to top 10
            anomalies_text += f"- {anomaly.get('type')}: {anomaly.get('reason')} (Field: {anomaly.get('field')})\n"
    
    validation_errors = validation_result.get("errors", [])
    validation_warnings = validation_result.get("warnings", [])
    
    prompt = f"""You are an expert risk analyst for underwriting and loan processing. Analyze the following document extraction and anomalies to provide risk assessment reasoning.

DOCUMENT TYPE: {document_type.value}

EXTRACTED DATA:
{json.dumps(extracted_data, indent=2)}

VALIDATION RESULTS:
- Quality Score: {validation_result.get('quality_score', 'N/A')}
- Errors: {len(validation_errors)}
- Warnings: {len(validation_warnings)}
- Is Valid: {validation_result.get('is_valid', False)}

DETECTED ANOMALIES:
{anomalies_text if anomalies_text else "No critical or high-severity anomalies detected."}

TASK:
1. Analyze the anomalies in context of the extracted data
2. Assess the overall risk level (LOW/MEDIUM/HIGH/CRITICAL)
3. Identify potential fraud indicators
4. Provide reasoning for each significant anomaly
5. Recommend specific actions (ACCEPT/REVIEW/REJECT)

OUTPUT FORMAT (JSON):
{{
    "risk_assessment": {{
        "overall_risk_level": "LOW|MEDIUM|HIGH|CRITICAL",
        "risk_score_explanation": "Brief explanation of risk score",
        "fraud_indicators": ["list of potential fraud indicators"],
        "data_quality_concerns": ["list of data quality issues"]
    }},
    "anomaly_analysis": [
        {{
            "anomaly_type": "type of anomaly",
            "severity": "CRITICAL|HIGH|MEDIUM|LOW",
            "reasoning": "Detailed explanation of why this is concerning",
            "potential_impact": "Impact on underwriting decision",
            "recommendation": "Specific action to take"
        }}
    ],
    "recommendations": {{
        "decision": "ACCEPT|REVIEW|REJECT",
        "reasoning": "Why this decision",
        "required_actions": ["list of specific actions needed"],
        "additional_documents_needed": ["list of documents to request"],
        "manual_review_required": true/false
    }},
    "confidence": 0.0-1.0
}}

Provide your analysis as a valid JSON object."""

    return prompt

