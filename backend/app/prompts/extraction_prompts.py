"""
Document Extraction Prompts
"""
from app.models.document import DocumentType

def get_extraction_prompt(document_type: DocumentType) -> str:
    """
    Get extraction prompt for specific document type
    
    Args:
        document_type: Type of document
    
    Returns:
        Extraction prompt
    """
    prompts = {
        DocumentType.AADHAAR: _get_aadhaar_prompt(),
        DocumentType.PAN: _get_pan_prompt(),
        DocumentType.PASSPORT: _get_passport_prompt(),
        DocumentType.DRIVING_LICENSE: _get_driving_license_prompt(),
        DocumentType.VOTER_ID: _get_voter_id_prompt(),
        DocumentType.GST_RETURN: _get_gst_return_prompt(),
        DocumentType.ITR_FORM: _get_itr_form_prompt(),
        DocumentType.PAYSLIP: _get_payslip_prompt(),
        DocumentType.BANK_STATEMENT: _get_bank_statement_prompt(),
        DocumentType.BALANCE_SHEET: _get_balance_sheet_prompt(),
        DocumentType.SHOP_REGISTRATION: _get_shop_registration_prompt(),
        DocumentType.BUSINESS_LICENSE: _get_business_license_prompt(),
        DocumentType.CRIF: _get_credit_report_prompt("CRIF"),
        DocumentType.EXPERIAN: _get_credit_report_prompt("Experian"),
        DocumentType.EQUIFAX: _get_credit_report_prompt("Equifax"),
        DocumentType.LOAN_SANCTION_LETTER: _get_loan_sanction_prompt(),
        DocumentType.EMI_SCHEDULE: _get_emi_schedule_prompt(),
        DocumentType.LOAN_AGREEMENT: _get_loan_agreement_prompt(),
        DocumentType.RENT_AGREEMENT: _get_rent_agreement_prompt(),
        DocumentType.CIBIL_SCORE_REPORT: _get_cibil_score_report_prompt(),
        DocumentType.DEALER_INVOICE: _get_dealer_invoice_prompt(),
        DocumentType.BUSINESS_REGISTRATION: _get_business_registration_prompt(),
        DocumentType.LAND_RECORDS: _get_land_records_prompt(),
        DocumentType.MEDICAL_BILLS: _get_medical_bills_prompt(),
        DocumentType.ELECTRICITY_BILL: _get_electricity_bill_prompt(),
        DocumentType.WATER_BILL: _get_water_bill_prompt(),
        DocumentType.OFFER_LETTER: _get_offer_letter_prompt()
    }
    
    return prompts.get(document_type, _get_generic_prompt())

def _get_aadhaar_prompt() -> str:
    return """Extract all information from this Aadhaar card document and return as JSON.

REQUIRED FIELDS:
- name: Full name of the cardholder
- aadhaar_number: 12-digit Aadhaar number (with or without spaces)
- date_of_birth: Date of birth (YYYY-MM-DD format)
- gender: Gender (MALE/FEMALE/OTHER)
- address: Complete address
- pincode: PIN code
- state: State name
- district: District name

OPTIONAL FIELDS:
- father_name: Father's name
- husband_name: Husband's name
- photo_present: Boolean indicating if photo is visible

Return the result as a valid JSON object with the extracted fields."""

def _get_pan_prompt() -> str:
    return """Extract all information from this PAN card document and return as JSON.

REQUIRED FIELDS:
- name: Full name of the cardholder
- pan_number: PAN number (format: ABCDE1234F)
- father_name: Father's name
- date_of_birth: Date of birth (YYYY-MM-DD format)

OPTIONAL FIELDS:
- signature_present: Boolean indicating if signature is visible

Return the result as a valid JSON object with the extracted fields."""

def _get_passport_prompt() -> str:
    return """Extract all information from this Passport document and return as JSON.

REQUIRED FIELDS:
- name: Full name as on passport
- passport_number: Passport number
- date_of_birth: Date of birth (YYYY-MM-DD format)
- place_of_birth: Place of birth
- nationality: Nationality
- date_of_issue: Date of issue (YYYY-MM-DD format)
- date_of_expiry: Date of expiry (YYYY-MM-DD format)
- place_of_issue: Place of issue

OPTIONAL FIELDS:
- gender: Gender
- address: Address
- father_name: Father's name
- spouse_name: Spouse name

Return the result as a valid JSON object with the extracted fields."""

def _get_driving_license_prompt() -> str:
    return """Extract all information from this Driving License document and return as JSON.

REQUIRED FIELDS:
- name: Full name of license holder
- license_number: Driving license number
- date_of_birth: Date of birth (YYYY-MM-DD format)
- issue_date: Date of issue (YYYY-MM-DD format)
- expiry_date: Date of expiry (YYYY-MM-DD format)
- address: Address

OPTIONAL FIELDS:
- vehicle_classes: List of vehicle classes authorized
- blood_group: Blood group
- father_name: Father's name

Return the result as a valid JSON object with the extracted fields."""

def _get_voter_id_prompt() -> str:
    return """Extract all information from this Voter ID document and return as JSON.

REQUIRED FIELDS:
- name: Full name
- voter_id_number: Voter ID number
- date_of_birth: Date of birth (YYYY-MM-DD format)
- address: Complete address

OPTIONAL FIELDS:
- father_name: Father's name
- gender: Gender
- assembly_constituency: Assembly constituency
- parliamentary_constituency: Parliamentary constituency

Return the result as a valid JSON object with the extracted fields."""

def _get_gst_return_prompt() -> str:
    return """Extract all information from this GST Return document and return as JSON.

REQUIRED FIELDS:
- gstin: GST Identification Number
- legal_name: Legal name of business
- trade_name: Trade name (if different)
- return_period: Return period (month/year)
- filing_date: Date of filing (YYYY-MM-DD format)

FINANCIAL FIELDS:
- total_sales: Total sales amount
- total_purchases: Total purchases amount
- output_tax: Output tax amount
- input_tax: Input tax credit
- tax_payable: Tax payable amount
- tax_paid: Tax paid amount

OPTIONAL FIELDS:
- address: Business address
- state: State code
- hsn_codes: List of HSN codes used

Return the result as a valid JSON object with the extracted fields."""

def _get_itr_form_prompt() -> str:
    return """Extract all information from this Income Tax Return (ITR) form and return as JSON.

REQUIRED FIELDS:
- pan_number: PAN number
- assessment_year: Assessment year
- name: Name of assessee
- filing_date: Date of filing (YYYY-MM-DD format)

INCOME FIELDS:
- total_income: Total income
- salary_income: Salary income
- business_income: Business income
- capital_gains: Capital gains
- other_income: Other income

TAX FIELDS:
- tax_payable: Tax payable
- tax_paid: Tax paid/tds
- refund_amount: Refund amount (if applicable)

OPTIONAL FIELDS:
- address: Address
- bank_accounts: List of bank account numbers
- deductions: List of deductions claimed

Return the result as a valid JSON object with the extracted fields."""

def _get_payslip_prompt() -> str:
    return """Extract all information from this Payslip document and return as JSON.

CRITICAL OUTPUT RULES:
- Output ONLY a single valid JSON object. No markdown code fences (```), no explanations, no notes, no comments.
- All numeric fields MUST be plain numbers (e.g., 47500). Do NOT output formulas like "53255 + 21302" or "(...) - (...)".
- If a numeric total is not explicitly shown in the document, calculate it and provide the final number value.
- Do NOT include any text outside the JSON object.
- DO NOT HALLUCINATE: Only extract fields that are explicitly visible in the document. If month/year are not mentioned, set them to null. Do NOT guess or invent dates.
- STRING CLEANING: Remove trailing commas, periods, and extra whitespace from all string fields. "Rajesh Kumar," should be extracted as "Rajesh Kumar" (without the comma).

CRITICAL: NET SALARY EXTRACTION - READ CAREFULLY
- The "Net Pay" or "Net Salary" field is the FINAL take-home amount shown at the bottom of the payslip
- Extract the EXACT value shown for "Net Pay" or "Net Salary" - do NOT calculate it, do NOT derive it
- Look for text like "Net Pay: INR 62935" or "Net Salary: 62935" at the bottom of the payslip
- Extract the number EXACTLY as shown - if it says "62935", extract 62935 (NOT 64535, NOT any other value)
- Do NOT subtract deductions from gross salary - use the Net Pay value directly from the document
- Do NOT use gross_salary minus deductions - use the Net Pay value that is explicitly stated
- The Net Pay is usually shown at the bottom of the payslip in a prominent location with clear labeling
- If you see "Net Pay: INR 62935", the net_salary field MUST be 62935 (not 64535, not 72346, not any calculated value)

IMPORTANT: Return all fields at the TOP LEVEL of the JSON object. Do NOT nest fields under "salary" or "optional_fields" objects.

REQUIRED FIELDS (all at top level):
- employee_name: Employee name (string) - CLEAN: remove trailing commas, periods, extra spaces
- employee_id: Employee ID/Code (string) - CLEAN: remove trailing commas, periods, extra spaces
- company_name: Company name (string) - CLEAN: remove trailing commas, periods, extra spaces
- month: Month as number 1-12 (integer) OR null if not explicitly mentioned in the document
- year: Year as YYYY format (integer) OR null if not explicitly mentioned in the document

SALARY FIELDS (all at top level):
- gross_salary: Gross salary amount (number - must be a single numeric value, not a formula). Calculate as: basic_salary + hra + sum of all allowances
- basic_salary: Basic salary amount (number)
- hra: House Rent Allowance amount (number)
- allowances: Other allowances as an object with key-value pairs, e.g. {"transport": 4382, "medical": 2419, "other": 6240} (object)
  OR if you cannot structure as object, extract as separate top-level fields: transport, medical, other (but prefer object format)
- deductions: Deductions as an object with key-value pairs, e.g. {"pf": 5083, "professional_tax": 250, "tds": 4078} (object)
  OR if you cannot structure as object, extract as separate top-level fields: pf, professional_tax, tds (but prefer object format)
- net_salary: Net salary amount (number - must be a single numeric value, not a formula). Extract EXACTLY from "Net Pay" field at bottom of payslip.

OPTIONAL FIELDS (all at top level):
- bank_account: Bank account number (string) - CLEAN: remove trailing commas, periods, extra spaces
- ifsc_code: IFSC code (string) - CLEAN: remove trailing commas, periods, extra spaces
- pf_number: Provident Fund number (string)
- esi_number: ESI number (string or null)
- tax_deductions: Tax deductions amount (number or null)

EXAMPLE STRUCTURE (with month/year if present):
{
  "employee_name": "John Doe",
  "employee_id": "EMP001",
  "company_name": "ABC Company",
  "month": 12,
  "year": 2024,
  "gross_salary": 50000,
  "basic_salary": 25000,
  "hra": 10000,
  "allowances": {"transport": 2000, "medical": 1500},
  "deductions": {"pf": 1800, "professional_tax": 200},
  "net_salary": 47500,
  "bank_account": "1234567890",
  "ifsc_code": "BANK0001234"
}

EXAMPLE STRUCTURE (without month/year if not present):
{
  "employee_name": "John Doe",
  "employee_id": "EMP001",
  "company_name": "ABC Company",
  "month": null,
  "year": null,
  "gross_salary": 50000,
  "basic_salary": 25000,
  "hra": 10000,
  "allowances": {"transport": 2000, "medical": 1500},
  "deductions": {"pf": 1800, "professional_tax": 200},
  "net_salary": 47500,
  "bank_account": "1234567890",
  "ifsc_code": "BANK0001234"
}

STRING CLEANING EXAMPLES:
- "Rajesh Kumar," → "Rajesh Kumar"
- "FINT21131," → "FINT21131"
- "Funds International," → "Funds International"
- "998877665544," → "998877665544"
- "ICIC0007788," → "ICIC0007788"
- Remove trailing commas, periods, and trim whitespace from ALL string fields.

IMPORTANT: For month and year fields, extract ONLY from the PAY PERIOD or SALARY PERIOD field (the period for which the salary is being paid). Do NOT extract from issue date, generation date, validation date, or any other date field. If the pay period is not clearly mentioned, use null for both month and year.

Return ONLY the JSON object with all fields at the top level. No additional text or formatting."""

def _get_bank_statement_prompt() -> str:
    return """Extract all information from this Bank Statement document and return as JSON.

CRITICAL TRANSACTION RULES:
- CREDIT transactions: Money coming INTO the account (salary, deposits, transfers received, refunds, interest, NEFT/RTGS/IMPS credits)
- DEBIT transactions: Money going OUT of the account (withdrawals, payments, transfers sent, fees, EMI, UPI payments, POS transactions, ATM withdrawals)
- If a transaction appears in the "Credit" column of the statement, it is a CREDIT transaction
- If a transaction appears in the "Debit" column of the statement, it is a DEBIT transaction
- The "type" field must match: if credit amount exists, type is "CREDIT"; if debit amount exists, type is "DEBIT"
- Only populate the "debit" field if it's a debit transaction (set to null for credits)
- Only populate the "credit" field if it's a credit transaction (set to null for debits)
- The balance should increase for credits and decrease for debits
- Verify balance calculations: previous_balance + credit - debit = new_balance

REQUIRED FIELDS:
- account_number: Bank account number
- account_holder_name: Account holder name
- bank_name: Bank name
- statement_period_from: Statement period start date (YYYY-MM-DD)
- statement_period_to: Statement period end date (YYYY-MM-DD)

BALANCE FIELDS:
- opening_balance: Opening balance
- closing_balance: Closing balance
- minimum_balance: Minimum balance during period

TRANSACTIONS:
- transactions: Array of transaction objects, each with:
  - date: Transaction date (YYYY-MM-DD)
  - description: Transaction description
  - debit: Debit amount (if applicable)
  - credit: Credit amount (if applicable)
  - balance: Balance after transaction
  - type: Transaction type (DEBIT/CREDIT)

OPTIONAL FIELDS:
- ifsc_code: IFSC code
- branch_name: Branch name
- account_type: Account type

Return the result as a valid JSON object with the extracted fields."""

def _get_balance_sheet_prompt() -> str:
    return """Extract all information from this Balance Sheet document and return as JSON.

REQUIRED FIELDS:
- company_name: Company name
- financial_year: Financial year
- as_on_date: Balance sheet date (YYYY-MM-DD)

ASSETS:
- total_assets: Total assets
- current_assets: Current assets
- fixed_assets: Fixed assets
- investments: Investments
- other_assets: Other assets

LIABILITIES:
- total_liabilities: Total liabilities
- current_liabilities: Current liabilities
- long_term_liabilities: Long-term liabilities
- equity: Shareholders' equity

OPTIONAL FIELDS:
- auditor_name: Auditor name
- director_names: List of director names

Return the result as a valid JSON object with the extracted fields."""

def _get_shop_registration_prompt() -> str:
    return """Extract all information from this Shop Registration Certificate and return as JSON.

REQUIRED FIELDS:
- registration_number: Registration number
- shop_name: Shop name
- owner_name: Owner name
- registration_date: Date of registration (YYYY-MM-DD)
- address: Shop address

OPTIONAL FIELDS:
- business_type: Type of business
- validity_period: Validity period
- state: State name

Return the result as a valid JSON object with the extracted fields."""

def _get_business_license_prompt() -> str:
    return """Extract all information from this Business License document and return as JSON.

REQUIRED FIELDS:
- license_number: License number
- business_name: Business name
- owner_name: Owner name
- license_type: Type of license
- issue_date: Issue date (YYYY-MM-DD)
- expiry_date: Expiry date (YYYY-MM-DD)
- address: Business address

OPTIONAL FIELDS:
- issuing_authority: Issuing authority
- business_category: Business category

Return the result as a valid JSON object with the extracted fields."""

def _get_credit_report_prompt(bureau_name: str) -> str:
    return f"""Extract all information from this {bureau_name} Credit Report and return as JSON.

REQUIRED FIELDS:
- report_date: Report date (YYYY-MM-DD)
- consumer_name: Consumer name
- date_of_birth: Date of birth (YYYY-MM-DD)
- pan_number: PAN number (if available)

CREDIT SCORE:
- credit_score: Credit score
- score_range: Score range

ACCOUNTS:
- total_accounts: Total number of accounts
- active_accounts: Number of active accounts
- closed_accounts: Number of closed accounts
- accounts: Array of account objects with:
  - account_type: Type of account
  - lender_name: Lender name
  - account_number: Account number
  - opening_date: Opening date
  - current_balance: Current balance
  - overdue_amount: Overdue amount (if any)
  - status: Account status

ENQUIRIES:
- total_enquiries: Total number of enquiries
- recent_enquiries: Number of recent enquiries

OPTIONAL FIELDS:
- address: Address
- employment_details: Employment information

Return the result as a valid JSON object with the extracted fields."""

def _get_loan_sanction_prompt() -> str:
    return """Extract all information from this Loan Sanction Letter and return as JSON.

REQUIRED FIELDS:
- loan_number: Loan number/reference
- borrower_name: Borrower name
- sanction_date: Sanction date (YYYY-MM-DD)
- loan_amount: Sanctioned loan amount
- interest_rate: Interest rate (percentage)
- loan_tenure: Loan tenure (in months/years)
- emi_amount: EMI amount

OPTIONAL FIELDS:
- lender_name: Lender name
- loan_type: Type of loan
- purpose: Loan purpose
- processing_fee: Processing fee
- prepayment_charges: Prepayment charges
- terms_and_conditions: Key terms

Return the result as a valid JSON object with the extracted fields."""

def _get_emi_schedule_prompt() -> str:
    return """Extract all information from this EMI Schedule document and return as JSON.

REQUIRED FIELDS:
- loan_number: Loan number
- borrower_name: Borrower name
- loan_amount: Loan amount
- interest_rate: Interest rate
- tenure_months: Tenure in months
- emi_amount: EMI amount

SCHEDULE:
- emi_schedule: Array of EMI objects, each with:
  - installment_number: Installment number
  - due_date: Due date (YYYY-MM-DD)
  - principal: Principal amount
  - interest: Interest amount
  - total: Total EMI amount
  - outstanding_balance: Outstanding balance

OPTIONAL FIELDS:
- start_date: Loan start date
- end_date: Loan end date
- total_interest: Total interest payable

Return the result as a valid JSON object with the extracted fields."""

def _get_loan_agreement_prompt() -> str:
    return """Extract all information from this Loan Agreement document and return as JSON.

REQUIRED FIELDS:
- agreement_number: Agreement number
- borrower_name: Borrower name
- lender_name: Lender name
- loan_amount: Loan amount
- interest_rate: Interest rate
- tenure: Loan tenure
- agreement_date: Agreement date (YYYY-MM-DD)

KEY TERMS:
- emi_amount: EMI amount
- prepayment_terms: Prepayment terms
- penalty_charges: Penalty charges
- default_terms: Default terms

OPTIONAL FIELDS:
- collateral_details: Collateral information
- guarantor_details: Guarantor information
- disbursement_date: Disbursement date

Return the result as a valid JSON object with the extracted fields."""

def _get_rent_agreement_prompt() -> str:
    return """Extract all information from this Rent Agreement document and return as JSON.

REQUIRED FIELDS:
- landlord_name: Name of the landlord
- tenant_name: Name of the tenant
- property_address: Complete property address
- rent_amount: Monthly rent amount
- security_deposit: Security deposit amount
- agreement_start_date: Agreement start date (YYYY-MM-DD)
- agreement_end_date: Agreement end date (YYYY-MM-DD)
- agreement_date: Date of agreement (YYYY-MM-DD)

OPTIONAL FIELDS:
- property_type: Type of property (House/Apartment/Shop)
- area_sqft: Area in square feet
- advance_amount: Advance payment
- terms_and_conditions: Key terms

Return the result as a valid JSON object with the extracted fields."""

def _get_cibil_score_report_prompt() -> str:
    return """Extract all information from this CIBIL Score Report and return as JSON.

REQUIRED FIELDS:
- consumer_name: Consumer name
- date_of_birth: Date of birth (YYYY-MM-DD)
- pan_number: PAN number (if available)
- report_date: Report date (YYYY-MM-DD)
- credit_score: CIBIL credit score (300-900)

ACCOUNT DETAILS:
- total_accounts: Total number of accounts
- active_accounts: Number of active accounts
- closed_accounts: Number of closed accounts
- accounts: Array of account objects with:
  - account_type: Type of account
  - lender_name: Lender name
  - account_number: Account number
  - current_balance: Current balance
  - overdue_amount: Overdue amount (if any)
  - status: Account status

ENQUIRIES:
- total_enquiries: Total number of enquiries
- recent_enquiries: Number of recent enquiries (last 6 months)

Return the result as a valid JSON object with the extracted fields."""

def _get_dealer_invoice_prompt() -> str:
    return """Extract all information from this Dealer Invoice document and return as JSON.

REQUIRED FIELDS:
- invoice_number: Invoice number
- invoice_date: Invoice date (YYYY-MM-DD)
- dealer_name: Dealer/Company name
- dealer_address: Dealer address
- customer_name: Customer name
- customer_address: Customer address (if available)

ITEMS:
- items: Array of items, each with:
  - description: Item description
  - quantity: Quantity
  - unit_price: Unit price
  - total_price: Total price

FINANCIAL:
- subtotal: Subtotal amount
- tax_amount: Tax amount
- total_amount: Total amount
- payment_terms: Payment terms

OPTIONAL FIELDS:
- gstin: GSTIN number
- hsn_code: HSN codes
- delivery_address: Delivery address

Return the result as a valid JSON object with the extracted fields."""

def _get_business_registration_prompt() -> str:
    return """Extract all information from this Business Registration document and return as JSON.

REQUIRED FIELDS:
- registration_number: Registration number
- business_name: Business/Company name
- registration_date: Date of registration (YYYY-MM-DD)
- business_type: Type of business (Proprietorship/Partnership/LLP/Private Limited/etc.)
- registered_address: Registered address

OPTIONAL FIELDS:
- gstin: GSTIN number
- pan_number: PAN number
- director_names: List of director/partner names
- authorized_capital: Authorized capital
- paid_up_capital: Paid up capital
- validity_period: Validity period

Return the result as a valid JSON object with the extracted fields."""

def _get_land_records_prompt() -> str:
    return """Extract all information from this Land Records document and return as JSON.

REQUIRED FIELDS:
- survey_number: Survey number
- village: Village name
- taluk: Taluk name
- district: District name
- state: State name
- area: Land area (in acres/hectares)
- owner_name: Owner name(s)

OPTIONAL FIELDS:
- khata_number: Khata number
- patta_number: Patta number
- land_type: Type of land (Agricultural/Residential/Commercial)
- boundaries: Land boundaries
- registration_date: Registration date (YYYY-MM-DD)
- mutation_number: Mutation number

Return the result as a valid JSON object with the extracted fields."""

def _get_medical_bills_prompt() -> str:
    return """Extract all information from this Medical Bill document and return as JSON.

REQUIRED FIELDS:
- hospital_name: Hospital/Clinic name
- patient_name: Patient name
- bill_number: Bill number
- bill_date: Bill date (YYYY-MM-DD)
- total_amount: Total bill amount

SERVICES:
- services: Array of services, each with:
  - service_name: Name of service/treatment
  - service_date: Date of service (YYYY-MM-DD)
  - amount: Service amount

FINANCIAL:
- consultation_fee: Consultation fee
- medicine_charges: Medicine charges
- lab_charges: Lab/test charges
- room_charges: Room charges (if applicable)
- other_charges: Other charges

OPTIONAL FIELDS:
- doctor_name: Doctor name
- admission_date: Admission date (if applicable)
- discharge_date: Discharge date (if applicable)
- insurance_claim_number: Insurance claim number

Return the result as a valid JSON object with the extracted fields."""

def _get_electricity_bill_prompt() -> str:
    return """Extract all information from this Electricity Bill document and return as JSON.

REQUIRED FIELDS:
- consumer_number: Consumer/Account number
- consumer_name: Consumer name
- service_address: Service address
- bill_number: Bill number
- bill_date: Bill date (YYYY-MM-DD)
- due_date: Due date (YYYY-MM-DD)
- billing_period_from: Billing period start date (YYYY-MM-DD)
- billing_period_to: Billing period end date (YYYY-MM-DD)

USAGE:
- previous_reading: Previous meter reading
- current_reading: Current meter reading
- units_consumed: Units consumed (kWh)
- load: Connected load

CHARGES:
- fixed_charges: Fixed charges
- energy_charges: Energy charges
- tax_amount: Tax amount
- total_amount: Total amount due

OPTIONAL FIELDS:
- payment_status: Payment status
- late_fee: Late fee (if applicable)

Return the result as a valid JSON object with the extracted fields."""

def _get_water_bill_prompt() -> str:
    return """Extract all information from this Water Bill document and return as JSON.

REQUIRED FIELDS:
- consumer_number: Consumer/Account number
- consumer_name: Consumer name
- service_address: Service address
- bill_number: Bill number
- bill_date: Bill date (YYYY-MM-DD)
- due_date: Due date (YYYY-MM-DD)
- billing_period_from: Billing period start date (YYYY-MM-DD)
- billing_period_to: Billing period end date (YYYY-MM-DD)

USAGE:
- previous_reading: Previous meter reading
- current_reading: Current meter reading
- units_consumed: Units consumed (in liters/cubic meters)

CHARGES:
- fixed_charges: Fixed charges
- water_charges: Water charges
- sewerage_charges: Sewerage charges (if applicable)
- tax_amount: Tax amount
- total_amount: Total amount due

OPTIONAL FIELDS:
- payment_status: Payment status
- late_fee: Late fee (if applicable)

Return the result as a valid JSON object with the extracted fields."""

def _get_offer_letter_prompt() -> str:
    return """Extract all information from this Offer Letter document and return as JSON.

IMPORTANT: Return all fields at the TOP LEVEL of the JSON object. Do NOT nest fields under category objects.

REQUIRED FIELDS (all at top level):
- company_name: Company name (string)
- candidate_name: Candidate/Employee name (string)
- offer_date: Offer date (YYYY-MM-DD format)
- position_title: Job title/Position/designation/Job role/Job Level (string)
- department: Department name (string)
- joining_date: Joining date (YYYY-MM-DD format)

COMPENSATION FIELDS (all at top level):
- salary_amount: Annual or monthly salary amount (number)
- salary_type: Salary type (ANNUAL/MONTHLY) (string)
- basic_salary: Basic salary amount (number, if specified separately)
- hra: House Rent Allowance amount (number, if specified)
- transport_allowance: Transport/Conveyance allowance (number, if specified)
- medical_allowance: Medical allowance (number, if specified)
- other_allowances: Other allowances as an object with key-value pairs, e.g. {"special_allowance": 10000, "performance_bonus": 5000} (object)
- total_ctc: Total Cost to Company (CTC) (number, if specified)
- gross_salary: Gross monthly salary (number, if specified)
- variable_pay: Variable pay or performance bonus (number, if specified)
- stock_options: Stock options or ESOPs (string or number, if specified)

EMPLOYMENT DETAILS (all at top level):
- employee_id: Employee ID (string, if mentioned)
- employment_type: Employment type (FULL_TIME/PART_TIME/CONTRACT/INTERN) (string)
- designation: Designation/Job level (string)
- reporting_manager: Reporting manager name (string, if specified)
- work_location: Work location/address (string)

BENEFITS & PERKS (all at top level):
- benefits: Benefits details as a string or object (string or object)
- health_insurance: Health insurance details (string, if specified)
- life_insurance: Life insurance coverage (string or number, if specified)
- provident_fund: PF contribution details (string, if specified)
- gratuity: Gratuity details (string, if specified)
- other_benefits: Other benefits like gym, meals, etc. (string, if specified)

TERMS & CONDITIONS (all at top level):
- notice_period: Notice period (string, e.g., "30 days", "1 month")
- probation_period: Probation period (string, e.g., "3 months", "6 months")
- contract_duration: Contract duration for contract employees (string)
- termination_terms: Termination terms and conditions (string)
- confidentiality_terms: Confidentiality terms (string)

BANK & FINANCIAL DETAILS (all at top level):
- bank_name: Bank name for salary credit (string, if specified)
- account_number: Bank account number (string, if specified)
- account_type: Account type (SAVINGS/CURRENT, if specified)
- ifsc_code: IFSC code (string, if specified)

COMPANY DETAILS (all at top level):
- company_address: Company registered address (string, if specified)
- company_website: Company website (string, if specified)
- company_email: Company contact email (string, if specified)
- company_phone: Company contact phone (string, if specified)


ADDITIONAL INFORMATION (all at top level):
- offer_validity: Offer validity period (string, if specified)
- acceptance_deadline: Acceptance deadline date (YYYY-MM-DD, if specified)
- background_verification: Background verification requirements (string, if specified)
- document_requirements: Required documents for joining (string, if specified)
- special_conditions: Any special conditions or clauses (string, if specified)
- signature_date: Date when offer was signed (YYYY-MM-DD, if visible)
- signatory_name: Name of person who signed the offer (string, if visible)
- signatory_designation: Designation of signatory (string, if visible)

EXAMPLE STRUCTURE:
{
  "company_name": "ABC Technologies Pvt Ltd",
  "candidate_name": "John Doe",
  "offer_date": "2024-01-15",
  "position_title": "Senior Software Engineer",
  "department": "Engineering",
  "joining_date": "2024-02-01",
  "salary_amount": 1200000,
  "salary_type": "ANNUAL",
  "basic_salary": 600000,
  "hra": 300000,
  "transport_allowance": 50000,
  "medical_allowance": 25000,
  "other_allowances": {"special_allowance": 150000, "performance_bonus": 75000},
  "total_ctc": 1200000,
  "gross_salary": 100000,
  "employee_id": "EMP001",
  "employment_type": "FULL_TIME",
  "designation": "Senior",
  "reporting_manager": "Jane Smith",
  "work_location": "Bangalore, Karnataka",
  "work_location_city": "Bangalore",
  "work_location_state": "Karnataka",
  "work_mode": "HYBRID",
  "benefits": "Health insurance, PF, Gratuity",
  "health_insurance": "Coverage for self and family",
  "notice_period": "30 days",
  "probation_period": "3 months",
  "bank_name": "HDFC Bank",
  "account_number": "1234567890",
  "account_type": "SAVINGS",
  "ifsc_code": "HDFC0001234",
  "company_address": "123 Tech Park, Whitefield",
  "company_city": "Bangalore",
  "hr_email": "hr@abctech.com",
  "offer_validity": "7 days",
  "acceptance_deadline": "2024-01-22"
}

Return the result as a valid JSON object with all fields at the top level. Extract as many fields as possible from the document."""

def _get_generic_prompt() -> str:
    return """Extract all relevant information from this document and return as JSON.

Extract:
- Document type
- Key identifiers (numbers, codes)
- Names and dates
- Financial amounts (if any)
- Addresses
- Any other structured data

Return the result as a valid JSON object with the extracted fields."""



