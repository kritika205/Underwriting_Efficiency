/**
 * Mapping from UI document IDs to backend DocumentType enum values
 * This matches the backend mapping in document_type_mapping.py
 */

export const UI_TO_BACKEND_MAPPING = {
  // Identity documents
  aadhaar: "AADHAAR",
  pan: "PAN",
  passport: "PASSPORT",
  voter: "VOTER_ID",
  dl: "DRIVING_LICENSE",
  
  // Address documents
  electricity: "ELECTRICITY_BILL",
  gas: "WATER_BILL",
  rent: "RENT_AGREEMENT",
  
  // Credit documents
  cibil: "CIBIL_SCORE_REPORT",
  bank: "BANK_STATEMENT",
  
  // Applicant documents - Salaried
  salary_slip: "PAYSLIP",
  form16: "ITR_FORM",
  employment_id: "OFFER_LETTER",
  
  // Applicant documents - Self-Employed
  itr: "ITR_FORM",
  gst: "GST_RETURN",
  pl: "BALANCE_SHEET",
  
  // Applicant documents - Business Owner
  registration: "BUSINESS_REGISTRATION",
  audited: "BALANCE_SHEET",
  
  // Loan documents
  sale_deed: "LAND_RECORDS",
  valuation: "LAND_RECORDS",
  invoice: "DEALER_INVOICE",
  insurance: "MEDICAL_BILLS",
  quotation: "DEALER_INVOICE",
  land_record: "LAND_RECORDS",
  crop_details: "LAND_RECORDS",
  revenue: "LAND_RECORDS",
  admission: "OFFER_LETTER",
  fee: "MEDICAL_BILLS",
  special_doc: "MEDICAL_BILLS",
  estimates: "MEDICAL_BILLS",
  income_proof: "PAYSLIP", // Could be payslip or ITR
  verification: "OFFER_LETTER",
  business_registration: "BUSINESS_REGISTRATION",
  returns: "GST_RETURN",
};

/**
 * Get expected document type for a UI document ID
 * @param {string} uiDocumentId - Document ID from UI (e.g., "aadhaar", "salary_slip")
 * @returns {string|null} - Backend DocumentType enum value or null if not found
 */
export function getExpectedDocumentType(uiDocumentId) {
  return UI_TO_BACKEND_MAPPING[uiDocumentId?.toLowerCase()] || null;
}

