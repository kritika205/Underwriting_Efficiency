"""
Document Classification Prompts
"""
def get_classification_prompt(ocr_text: str) -> str:
    """
    Get classification prompt for Azure OpenAI
    
    Args:
        ocr_text: Extracted OCR text
    
    Returns:
        Classification prompt
    """
    return f"""Analyze the following document text and classify it into one of these document types:

DOCUMENT TYPES:
1. AADHAAR - Indian national identity card with 12-digit number
2. PAN - Permanent Account Number card (5 letters, 4 digits, 1 letter)
3. PASSPORT - International passport document
4. DRIVING_LICENSE - Driver's license document
5. VOTER_ID - Voter identification card
6. GST_RETURN - Goods and Services Tax return document
7. ITR_FORM - Income Tax Return form
8. PAYSLIP - Salary slip/pay stub
9. BANK_STATEMENT - Bank account statement
10. BALANCE_SHEET - Financial balance sheet
11. SHOP_REGISTRATION - Shop registration certificate
12. BUSINESS_LICENSE - Business license document
13. CIBIL_SCORE_REPORT - CIBIL credit score report (credit bureau report from CIBIL)
14. CRIF - Credit bureau report from CRIF
15. EXPERIAN - Credit bureau report from Experian
16. EQUIFAX - Credit bureau report from Equifax
17. LOAN_SANCTION_LETTER - Loan approval/sanction letter
18. EMI_SCHEDULE - Equated Monthly Installment schedule
19. LOAN_AGREEMENT - Loan agreement document
20. RENT_AGREEMENT - Rental/lease agreement document (look for: 'Rental Agreement', 'Rent Agreement', 'Lease Agreement', 'Tenancy Agreement', keywords like Lessor, Lessee, rent amount, property address, stamp paper)
21. DEALER_INVOICE - Dealer or vendor invoice
22. BUSINESS_REGISTRATION - Business/company registration certificate
23. LAND_RECORDS - Land ownership or property records
24. MEDICAL_BILLS - Medical/hospital bills
25. ELECTRICITY_BILL - Electricity utility bill
26. WATER_BILL - Water utility bill
27. OFFER_LETTER - Job offer letter or employment offer letter
28. UNKNOWN - If document doesn't match any category

DOCUMENT TEXT:
{ocr_text[:2000]}

INSTRUCTIONS:
1. Analyze the document text carefully
2. Identify key indicators (document names, numbers, formats)
3. Classify into the most appropriate document type
4. Provide your answer in this exact format:
   DOCUMENT_TYPE: [type]
   CONFIDENCE: [0.0-1.0]
   REASON: [brief explanation]

Respond with only the classification result in the specified format."""


