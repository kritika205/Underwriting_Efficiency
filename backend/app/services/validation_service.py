"""
Document Validation Service
"""
from typing import Dict, Any, List, Optional
from app.models.document import DocumentType
import re
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Import cross-validation service (lazy import to avoid circular dependency)
_cross_validation_service = None

def get_cross_validation_service():
    """Lazy import of cross-validation service"""
    global _cross_validation_service
    if _cross_validation_service is None:
        from app.services.cross_validation_service import cross_validation_service
        _cross_validation_service = cross_validation_service
    return _cross_validation_service

class ValidationService:
    """Business rule validation service"""
    
    async def validate_extracted_data(
        self,
        extracted_data: Dict[str, Any],
        document_type: DocumentType,
        user_id: Optional[str] = None,
        validate_against_profile: bool = True
    ) -> Dict[str, Any]:
        """
        Validate extracted data against business rules and optionally against customer profile
        
        Args:
            extracted_data: Extracted data from document
            document_type: Type of document
            user_id: User ID for customer profile validation
            validate_against_profile: Whether to validate against customer profile
        
        Returns:
            Dictionary with validation results, warnings, and quality score
        """
        warnings = []
        errors = []
        
        # Get validation rules for document type
        validator = self._get_validator(document_type)
        
        if validator:
            validation_result = validator(extracted_data)
            warnings.extend(validation_result.get("warnings", []))
            errors.extend(validation_result.get("errors", []))
        
        # Validate against customer profile if user_id provided
        profile_validation = {}
        if validate_against_profile and user_id:
            profile_validation = await self.validate_against_customer_profile(
                extracted_data,
                document_type,
                user_id
            )
            warnings.extend(profile_validation.get("warnings", []))
            errors.extend(profile_validation.get("errors", []))
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(
            extracted_data,
            warnings,
            errors,
            document_type
        )
        
        result = {
            "is_valid": len(errors) == 0,
            "warnings": warnings,
            "errors": errors,
            "quality_score": quality_score
        }
        
        # Add profile validation details if available
        if profile_validation:
            result["profile_validation"] = {
                "customer_found": profile_validation.get("customer_found", False),
                "mismatches": profile_validation.get("mismatches", [])
            }
        
        return result
    
    def _get_validator(self, document_type: DocumentType):
        """Get validator function for document type"""
        validators = {
            DocumentType.AADHAAR: self._validate_aadhaar,
            DocumentType.PAN: self._validate_pan,
            DocumentType.PASSPORT: self._validate_passport,
            DocumentType.DRIVING_LICENSE: self._validate_driving_license,
            DocumentType.VOTER_ID: self._validate_voter_id,
            DocumentType.BANK_STATEMENT: self._validate_bank_statement,
            DocumentType.PAYSLIP: self._validate_payslip,
            DocumentType.GST_RETURN: self._validate_gst_return,
            DocumentType.ITR_FORM: self._validate_itr_form,
            DocumentType.RENT_AGREEMENT: self._validate_rent_agreement,
            DocumentType.CIBIL_SCORE_REPORT: self._validate_cibil_score_report,
            DocumentType.DEALER_INVOICE: self._validate_dealer_invoice,
            DocumentType.BUSINESS_REGISTRATION: self._validate_business_registration,
            DocumentType.LAND_RECORDS: self._validate_land_records,
            DocumentType.MEDICAL_BILLS: self._validate_medical_bills,
            DocumentType.ELECTRICITY_BILL: self._validate_electricity_bill,
            DocumentType.WATER_BILL: self._validate_water_bill
        }
        return validators.get(document_type)
    
    def _validate_aadhaar(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate Aadhaar document"""
        warnings = []
        errors = []
        
        # Check Aadhaar number format (12 digits, may have spaces)
        aadhaar = data.get("aadhaar_number", "")
        if aadhaar:
            aadhaar_clean = re.sub(r'\s+', '', str(aadhaar))
            if not re.match(r'^\d{12}$', aadhaar_clean):
                errors.append("Invalid Aadhaar number format")
        
        # Check required fields
        required_fields = ["name", "aadhaar_number", "date_of_birth"]
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Missing required field: {field}")
        
        # Check date format
        dob = data.get("date_of_birth")
        if dob and not self._is_valid_date(dob):
            warnings.append("Date of birth format may be incorrect")
        
        return {"warnings": warnings, "errors": errors}
    
    def _validate_pan(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate PAN document"""
        warnings = []
        errors = []
        
        # Check PAN format (5 letters, 4 digits, 1 letter)
        pan = data.get("pan_number", "")
        if pan:
            pan_clean = re.sub(r'\s+', '', str(pan).upper())
            if not re.match(r'^[A-Z]{5}\d{4}[A-Z]{1}$', pan_clean):
                errors.append("Invalid PAN number format")
        
        required_fields = ["name", "pan_number", "father_name"]
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Missing required field: {field}")
        
        return {"warnings": warnings, "errors": errors}
    
    def _validate_passport(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate Passport document"""
        warnings = []
        errors = []
        
        # Check passport number format
        passport_no = data.get("passport_number", "")
        if passport_no:
            if len(str(passport_no)) < 6:
                warnings.append("Passport number seems too short")
        
        required_fields = ["name", "passport_number", "date_of_birth", "nationality"]
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Missing required field: {field}")
        
        return {"warnings": warnings, "errors": errors}
    
    def _validate_driving_license(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate Driving License"""
        warnings = []
        errors = []
        
        required_fields = ["name", "license_number", "date_of_birth"]
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Missing required field: {field}")
        
        return {"warnings": warnings, "errors": errors}
    
    def _validate_voter_id(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate Voter ID"""
        warnings = []
        errors = []
        
        required_fields = ["name", "voter_id_number"]
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Missing required field: {field}")
        
        return {"warnings": warnings, "errors": errors}
    
    def _validate_bank_statement(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate Bank Statement"""
        warnings = []
        errors = []
        
        # Check for account number
        if not data.get("account_number"):
            warnings.append("Account number not found")
        
        # Check for transactions
        transactions = data.get("transactions", [])
        if not transactions or len(transactions) == 0:
            warnings.append("No transactions found in statement")
        
        return {"warnings": warnings, "errors": errors}
    
    def _validate_payslip(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate Payslip"""
        warnings = []
        errors = []
        
        # Handle nested structure if present (for backward compatibility)
        # Check if salary fields are nested under "salary" object
        if "salary" in data and isinstance(data["salary"], dict):
            salary_data = data["salary"]
            # Check nested location
            gross_salary = data.get("gross_salary") or salary_data.get("gross_salary")
            net_salary = data.get("net_salary") or salary_data.get("net_salary")
        else:
            gross_salary = data.get("gross_salary")
            net_salary = data.get("net_salary")
        
        # Required fields - month and year are optional (may not be present in all payslips)
        required_fields = ["employee_name", "employee_id"]
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Missing required field: {field}")
        
        # Month and year are optional - only validate format if present
        month = data.get("month")
        year = data.get("year")
        
        # Check salary amount (check both top-level and nested)
        if not gross_salary and not net_salary:
            warnings.append("Salary amount not found")
        
        # Validate month and year if present
        month = data.get("month")
        if month is not None:
            try:
                month_int = int(month) if not isinstance(month, int) else month
                if month_int < 1 or month_int > 12:
                    warnings.append(f"Invalid month value: {month}")
            except (ValueError, TypeError):
                warnings.append(f"Month should be a number between 1-12, got: {month}")
        
        year = data.get("year")
        if year is not None:
            try:
                year_int = int(year) if not isinstance(year, int) else year
                if year_int < 1900 or year_int > 2100:
                    warnings.append(f"Year seems invalid: {year}")
            except (ValueError, TypeError):
                warnings.append(f"Year should be a valid 4-digit number, got: {year}")
        
        return {"warnings": warnings, "errors": errors}
    
    def _validate_gst_return(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate GST Return"""
        warnings = []
        errors = []
        
        # Check GSTIN format
        gstin = data.get("gstin", "")
        if gstin:
            gstin_clean = re.sub(r'\s+', '', str(gstin).upper())
            if not re.match(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$', gstin_clean):
                warnings.append("GSTIN format may be incorrect")
        
        return {"warnings": warnings, "errors": errors}
    
    def _validate_itr_form(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate ITR Form"""
        warnings = []
        errors = []
        
        required_fields = ["pan_number", "assessment_year"]
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Missing required field: {field}")
        
        return {"warnings": warnings, "errors": errors}
    
    def _is_valid_date(self, date_str: str) -> bool:
        """Check if date string is valid"""
        try:
            # Try common date formats
            formats = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"]
            for fmt in formats:
                try:
                    datetime.strptime(str(date_str), fmt)
                    return True
                except:
                    continue
            return False
        except:
            return False
    
    def _calculate_quality_score(
        self,
        extracted_data: Dict[str, Any],
        warnings: List[str],
        errors: List[str],
        document_type: DocumentType
    ) -> float:
        """Calculate quality score (0-100)"""
        base_score = 100.0
        
        # Deduct for errors
        base_score -= len(errors) * 15
        
        # Deduct for warnings
        base_score -= len(warnings) * 5
        
        # Deduct for missing fields
        required_fields = self._get_required_fields(document_type)
        missing_fields = [f for f in required_fields if not extracted_data.get(f)]
        base_score -= len(missing_fields) * 10
        
        # Ensure score is between 0 and 100
        return max(0.0, min(100.0, base_score))
    
    def _validate_rent_agreement(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate Rent Agreement"""
        warnings = []
        errors = []
        
        required_fields = ["landlord_name", "tenant_name", "property_address", "rent_amount", "agreement_start_date"]
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Missing required field: {field}")
        
        # Validate dates
        if data.get("agreement_start_date") and not self._is_valid_date(data["agreement_start_date"]):
            warnings.append("Agreement start date format may be incorrect")
        
        if data.get("agreement_end_date") and not self._is_valid_date(data["agreement_end_date"]):
            warnings.append("Agreement end date format may be incorrect")
        
        return {"warnings": warnings, "errors": errors}
    
    def _validate_cibil_score_report(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate CIBIL Score Report"""
        warnings = []
        errors = []
        
        required_fields = ["consumer_name", "credit_score", "report_date"]
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Missing required field: {field}")
        
        # Validate credit score range
        credit_score = data.get("credit_score")
        if credit_score:
            try:
                score = float(credit_score)
                if score < 300 or score > 900:
                    warnings.append("Credit score outside valid range (300-900)")
            except:
                warnings.append("Credit score format may be incorrect")
        
        return {"warnings": warnings, "errors": errors}
    
    def _validate_dealer_invoice(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate Dealer Invoice"""
        warnings = []
        errors = []
        
        required_fields = ["invoice_number", "invoice_date", "dealer_name", "total_amount"]
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Missing required field: {field}")
        
        # Validate amounts
        if data.get("total_amount"):
            try:
                amount = float(data["total_amount"])
                if amount <= 0:
                    warnings.append("Total amount should be positive")
            except:
                warnings.append("Total amount format may be incorrect")
        
        return {"warnings": warnings, "errors": errors}
    
    def _validate_business_registration(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate Business Registration"""
        warnings = []
        errors = []
        
        required_fields = ["registration_number", "business_name", "registration_date"]
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Missing required field: {field}")
        
        return {"warnings": warnings, "errors": errors}
    
    def _validate_land_records(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate Land Records"""
        warnings = []
        errors = []
        
        required_fields = ["survey_number", "village", "district", "owner_name"]
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Missing required field: {field}")
        
        return {"warnings": warnings, "errors": errors}
    
    def _validate_medical_bills(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate Medical Bills"""
        warnings = []
        errors = []
        
        required_fields = ["hospital_name", "patient_name", "bill_date", "total_amount"]
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Missing required field: {field}")
        
        return {"warnings": warnings, "errors": errors}
    
    def _validate_electricity_bill(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate Electricity Bill"""
        warnings = []
        errors = []
        
        required_fields = ["consumer_number", "consumer_name", "bill_date", "total_amount"]
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Missing required field: {field}")
        
        return {"warnings": warnings, "errors": errors}
    
    def _validate_water_bill(self, data: Dict[str, Any]) -> Dict[str, List[str]]:
        """Validate Water Bill"""
        warnings = []
        errors = []
        
        required_fields = ["consumer_number", "consumer_name", "bill_date", "total_amount"]
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Missing required field: {field}")
        
        return {"warnings": warnings, "errors": errors}
    
    def _get_required_fields(self, document_type: DocumentType) -> List[str]:
        """Get required fields for document type"""
        field_map = {
            DocumentType.AADHAAR: ["name", "aadhaar_number", "date_of_birth"],
            DocumentType.PAN: ["name", "pan_number"],
            DocumentType.PASSPORT: ["name", "passport_number", "date_of_birth"],
            DocumentType.DRIVING_LICENSE: ["name", "license_number"],
            DocumentType.VOTER_ID: ["name", "voter_id_number"],
            DocumentType.BANK_STATEMENT: ["account_number"],
            DocumentType.PAYSLIP: ["employee_name", "employee_id"],  # month and year are optional
            DocumentType.RENT_AGREEMENT: ["landlord_name", "tenant_name", "rent_amount"],
            DocumentType.CIBIL_SCORE_REPORT: ["consumer_name", "credit_score"],
            DocumentType.DEALER_INVOICE: ["invoice_number", "invoice_date", "total_amount"],
            DocumentType.BUSINESS_REGISTRATION: ["registration_number", "business_name"],
            DocumentType.LAND_RECORDS: ["survey_number", "owner_name"],
            DocumentType.MEDICAL_BILLS: ["hospital_name", "patient_name", "total_amount"],
            DocumentType.ELECTRICITY_BILL: ["consumer_number", "total_amount"],
            DocumentType.WATER_BILL: ["consumer_number", "total_amount"]
        }
        return field_map.get(document_type, [])
    
    async def validate_against_customer_profile(
        self,
        extracted_data: Dict[str, Any],
        document_type: DocumentType,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Validate extracted data against customer profile in database
        Uses enhanced cross-validation service for better matching
        
        Returns:
            Dictionary with validation results, warnings, and mismatches
        """
        warnings = []
        errors = []
        mismatches = []
        
        try:
            # Use cross-validation service for better customer matching
            cross_val_service = get_cross_validation_service()
            customer = await cross_val_service.find_customer_profile(
                extracted_data,
                document_type,
                user_id
            )
            
            if not customer:
                warnings.append("Customer profile not found in database - skipping cross-reference validation")
                return {
                    "is_valid": True,
                    "warnings": warnings,
                    "errors": errors,
                    "mismatches": mismatches,
                    "customer_found": False
                }
            
            # Perform field validation using cross-validation service
            validation_result = cross_val_service._validate_fields(
                extracted_data,
                customer,
                document_type
            )
            
            # Convert validation result to warnings/errors
            for mismatch in validation_result["mismatches"]:
                field = mismatch["field"]
                mismatches.append(
                    f"{field} mismatch: extracted '{mismatch['extracted_value']}' "
                    f"vs database '{mismatch['profile_value']}'"
                )
                # Critical fields should be errors
                if field in ["aadhaar_number", "pan_number", "passport_number", "license_number", "gstin"]:
                    errors.append(f"{field} does not match customer profile")
                else:
                    warnings.append(f"{field} may not match customer profile")
            
            for missing in validation_result["missing_in_extraction"]:
                warnings.append(f"{missing['field']} not found in extracted data")
            
            # Calculate validation score
            validation_score = cross_val_service._calculate_validation_score(validation_result)
            
            return {
                "is_valid": len(errors) == 0,
                "warnings": warnings,
                "errors": errors,
                "mismatches": mismatches,
                "customer_found": True,
                "validation_score": validation_score
            }
            
        except Exception as e:
            logger.error(f"Error validating against customer profile: {e}")
            warnings.append(f"Error during customer profile validation: {str(e)}")
            return {
                "is_valid": True,
                "warnings": warnings,
                "errors": errors,
                "mismatches": mismatches,
                "customer_found": False
            }
    
    def _dates_match(self, date1: str, date2: str) -> bool:
        """Check if two date strings match (handles different formats)"""
        try:
            formats = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%y"]
            
            def parse_date(date_str: str):
                for fmt in formats:
                    try:
                        return datetime.strptime(str(date_str).strip(), fmt)
                    except:
                        continue
                return None
            
            d1 = parse_date(date1)
            d2 = parse_date(date2)
            
            if d1 and d2:
                return d1.date() == d2.date()
            
            # Fallback: string comparison after normalization
            return str(date1).strip() == str(date2).strip()
        except:
            return False

validation_service = ValidationService()



