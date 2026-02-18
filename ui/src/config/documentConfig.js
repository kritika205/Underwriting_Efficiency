export const COMMON_DOCUMENTS = {
  identity: [
    { id: "aadhaar", label: "Aadhaar Card" },
    { id: "pan", label: "PAN Card" },
    { id: "voter", label: "Voter ID" },
    { id: "dl", label: "Driving License" },
  ],
  address: [
    { id: "electricity", label: "Electricity Bill" },
    { id: "gas", label: "Water Bill" },
    { id: "rent", label: "Rent Agreement" },
  ],
  bank: [{ id: "bank", label: "Bank Statement (6 months)" }],
  credit: [{ id: "cibil", label: "CIBIL Report" }],
};

export const APPLICANT_DOCUMENTS = {
  "Salaried": [
    { id: "salary_slip", label: "Salary Slips (3 months)" },
    { id: "form16", label: "Form 16" },
    { id: "employment_id", label: "Employment ID / Letter" },
  ],
  "Self-Employed/Business Owner": [
    { id: "itr", label: "ITR (2 years)" },
    { id: "gst", label: "GST Returns" },
    { id: "pl", label: "Business Registration" },
  ],
};

export const LOAN_DOCUMENTS = {
  "Home Loan": [
    { id: "sale_deed", label: "Sale Deed" },
    { id: "valuation", label: "Property Valuation Report" },
  ],
  "Vehicle Loan": [
    { id: "invoice", label: "Vehicle Invoice" },
    { id: "insurance", label: "Vehicle Insurance" },
    { id: "quotation", label: "Vehicle Quatation/ RC" },
    { id: "bank", label: "Bank Statement (6 months)" },
  ],
  "Agriculture Loan": [
    { id: "land_record", label: "Land Ownership Record" },
    { id: "crop_details", label: "Crop Details" },
    { id: "revenue", label: "Revenue Records" },
  ],
  "Medical Loan": [
    { id: "special_doc", label: "Medical Report" },
    { id: "estimates", label: "Hospital Estimates" },
    { id: "bank", label: "Bank Statement (6 months)" },
  ],
  "Personal Loan": [
    { id: "income_proof", label: "Income Proof(Salary Slips/ ITR)" },
    { id: "verification", label: "Employer Verification" },
    { id: "bank", label: "Bank Statement (6 months)" },
  ],
  "Business Loan": [
    { id: "business_registration", label: "Business Registration" },
    { id: "returns", label: "GST Returns" },
    { id: "bank", label: "Bank Statement (6 months)" },
  ],
};

// Map frontend document IDs to backend document types
export const DOCUMENT_TYPE_MAP = {
  // Identity documents
  "aadhaar": "AADHAAR",
  "pan": "PAN",
  "passport": "PASSPORT",
  "voter": "VOTER_ID",
  "dl": "DRIVING_LICENSE",
  
  // Address documents
  "electricity": "ELECTRICITY_BILL",
  "gas": "ELECTRICITY_BILL", // Gas bill uses same type
  "rent": "RENT_AGREEMENT",
  
  // Bank & Credit
  "bank": "BANK_STATEMENT",
  "cibil": "CIBIL_SCORE_REPORT",
  
  // Salaried documents
  "salary_slip": "PAYSLIP",
  "form16": "ITR_FORM",
  "employment_id": "OFFER_LETTER",
  
  // Self-Employed documents
  "itr": "ITR_FORM",
  "gst": "GST_RETURN",
  "pl": "BALANCE_SHEET",
  
  // Business Owner documents
  "registration": "BUSINESS_REGISTRATION",
  "audited": "BALANCE_SHEET",
  
  // Loan documents
  "sale_deed": "LAND_RECORDS",
  "valuation": "LAND_RECORDS",
  "invoice": "DEALER_INVOICE",
  "insurance": "DEALER_INVOICE",
  "quotation": "DEALER_INVOICE",
  "land_record": "LAND_RECORDS",
  "crop_details": "LAND_RECORDS",
  "revenue": "LAND_RECORDS",
  "admission": "OFFER_LETTER",
  "fee": "OFFER_LETTER",
  "special_doc": "MEDICAL_BILLS",
  "estimates": "MEDICAL_BILLS",
  "income_proof": "PAYSLIP", // Can be PAYSLIP or ITR_FORM
  "verification": "OFFER_LETTER",
  "business_registration": "BUSINESS_REGISTRATION",
  "returns": "GST_RETURN",
};

// Helper function to get expected document type for a document ID
export const getExpectedDocumentType = (docId) => {
  return DOCUMENT_TYPE_MAP[docId] || null;
};

// Helper function to get all valid document types for a document ID
// Some documents can be multiple types (e.g., income_proof can be PAYSLIP or ITR_FORM)
export const getValidDocumentTypes = (docId) => {
  const primaryType = DOCUMENT_TYPE_MAP[docId];
  if (!primaryType) return [];
  
  // Handle special cases where multiple types are valid
  const multiTypeMap = {
    "income_proof": ["PAYSLIP", "ITR_FORM"], // Can be either
    "gas": ["ELECTRICITY_BILL", "WATER_BILL"], // Utility bills
  };
  
  if (multiTypeMap[docId]) {
    return multiTypeMap[docId];
  }
  
  return [primaryType];
};

// Helper function to check if actual document type matches expected
export const isDocumentTypeValid = (docId, actualType) => {
  if (!actualType) return null; // Unknown - can't validate
  
  const validTypes = getValidDocumentTypes(docId);
  if (validTypes.length === 0) return null; // No mapping - can't validate
  
  // Check if actual type matches any valid type (case-insensitive)
  const actualTypeUpper = actualType.toUpperCase();
  return validTypes.some(validType => validType.toUpperCase() === actualTypeUpper);
};