"""
Mapping utility from UI document IDs to backend DocumentType enum
"""
from app.models.document import DocumentType
from typing import Optional

# Mapping from UI document IDs (from documentConfig.js) to backend DocumentType
UI_TO_BACKEND_MAPPING = {
    # Identity documents
    "aadhaar": DocumentType.AADHAAR,
    "pan": DocumentType.PAN,
    "passport": DocumentType.PASSPORT,
    "voter": DocumentType.VOTER_ID,
    "dl": DocumentType.DRIVING_LICENSE,
    
    # Address documents
    "electricity": DocumentType.ELECTRICITY_BILL,
    "gas": DocumentType.WATER_BILL,  # Gas bill mapped to water bill (closest match)
    "rent": DocumentType.RENT_AGREEMENT,
    
    # Credit documents
    "cibil": DocumentType.CIBIL_SCORE_REPORT,
    "bank": DocumentType.BANK_STATEMENT,
    
    # Applicant documents - Salaried
    "salary_slip": DocumentType.PAYSLIP,
    "form16": DocumentType.ITR_FORM,
    "employment_id": DocumentType.OFFER_LETTER,  # Closest match
    
    # Applicant documents - Self-Employed
    "itr": DocumentType.ITR_FORM,
    "gst": DocumentType.GST_RETURN,
    "pl": DocumentType.BALANCE_SHEET,  # Profit & Loss
    
    # Applicant documents - Business Owner
    "registration": DocumentType.BUSINESS_REGISTRATION,
    "audited": DocumentType.BALANCE_SHEET,
    
    # Loan documents
    "sale_deed": DocumentType.LAND_RECORDS,  # Closest match
    "valuation": DocumentType.LAND_RECORDS,  # Closest match
    "invoice": DocumentType.DEALER_INVOICE,
    "insurance": DocumentType.MEDICAL_BILLS,  # Closest match
    "quotation": DocumentType.DEALER_INVOICE,  # Closest match
    "land_record": DocumentType.LAND_RECORDS,
    "crop_details": DocumentType.LAND_RECORDS,  # Closest match
    "revenue": DocumentType.LAND_RECORDS,
    "admission": DocumentType.OFFER_LETTER,  # Closest match
    "fee": DocumentType.MEDICAL_BILLS,  # Closest match
    "special_doc": DocumentType.MEDICAL_BILLS,
    "estimates": DocumentType.MEDICAL_BILLS,
    "income_proof": DocumentType.PAYSLIP,  # Could be payslip or ITR
    "verification": DocumentType.OFFER_LETTER,  # Closest match
    "business_registration": DocumentType.BUSINESS_REGISTRATION,
    "returns": DocumentType.GST_RETURN,
}

def get_expected_document_type(ui_document_id: str) -> Optional[str]:
    """
    Convert UI document ID to backend DocumentType enum value
    
    Args:
        ui_document_id: Document ID from UI (e.g., "aadhaar", "salary_slip")
    
    Returns:
        DocumentType enum value as string, or None if not found
    """
    doc_type = UI_TO_BACKEND_MAPPING.get(ui_document_id.lower())
    return doc_type.value if doc_type else None

