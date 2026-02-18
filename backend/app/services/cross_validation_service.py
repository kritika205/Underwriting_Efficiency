"""
Cross-Validation Service for validating extracted documents against customer datasheet
"""
from typing import Dict, Any, List, Optional
from app.models.document import DocumentType
from app.core.database import get_database
import re
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class CrossValidationService:
    """Service for cross-validating extracted documents with customer profiles"""
    
    def __init__(self):
        self.field_mappings = {
            # Document type -> (extracted_field, customer_profile_field)
            DocumentType.AADHAAR: [
                ("aadhaar_number", "aadhar_number"),
                ("name", "full_name"),
                ("date_of_birth", "date_of_birth"),
                ("address", "address"),
                ("city", "city"),
                ("state", "state"),
                ("pincode", "pincode"),
            ],
            DocumentType.PAN: [
                ("pan_number", "pan_number"),
                ("name", "full_name"),
                ("father_name", "father_name"),
                ("date_of_birth", "date_of_birth"),
            ],
            DocumentType.PASSPORT: [
                ("passport_number", "passport_number"),
                ("name", "full_name"),
                ("date_of_birth", "date_of_birth"),
            ],
            DocumentType.DRIVING_LICENSE: [
                ("license_number", "dl_number"),
                ("name", "full_name"),
                ("date_of_birth", "date_of_birth"),
                ("address", "address"),
            ],
            DocumentType.PAYSLIP: [
                ("employee_name", "full_name"),
                ("employer_name", "employer_name"),
                ("gross_salary", "monthly_salary"),
                ("net_salary", "monthly_salary"),
            ],
            DocumentType.GST_RETURN: [
                ("gstin", "gst_number"),
                ("business_name", "employer_name"),
            ],
            DocumentType.CIBIL_SCORE_REPORT: [
                ("consumer_name", "full_name"),
                ("credit_score", "cibil_score"),
            ],
            DocumentType.BANK_STATEMENT: [
                ("account_holder_name", "account_holder_name"),
                ("bank_name", "bank_name"),
                ("account_number", "account_number"),
                ("statement_period_from", "statement_period_from"),
                ("statement_period_to", "statement_period_to"),
            ],
            DocumentType.ITR_FORM: [
                ("pan_number", "pan_number"),
                ("name", "full_name"),
            ],
        }
    
    async def find_customer_profile(
        self,
        extracted_data: Dict[str, Any],
        document_type: DocumentType,
        user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find customer profile using multiple matching strategies
        
        Returns:
            Customer profile dict if found, None otherwise
        """
        db = await get_database()
        
        # Strategy 1: Match by user_id if it's a customer_id
        if user_id:
            customer = await db.customer_profiles.find_one({"customer_id": user_id})
            if customer:
                return customer
        
        # Strategy 2: Match by document-specific identifiers
        query = self._build_matching_query(extracted_data, document_type)
        if query:
            customer = await db.customer_profiles.find_one(query)
            if customer:
                return customer
        
        # Strategy 3: Match by name and other common fields
        name = self._extract_name(extracted_data, document_type)
        if name:
            # Try exact name match first (case-insensitive)
            name_normalized = self._normalize_string(name)
            customer = await db.customer_profiles.find_one({
                "full_name": {"$regex": re.escape(name_normalized), "$options": "i"}
            })
            if customer:
                return customer
            
            # Try partial name match
            name_parts = name_normalized.split()
            if len(name_parts) >= 2:
                # Match if at least 2 name parts match
                regex_pattern = "|".join([re.escape(part) for part in name_parts if len(part) > 2])
                if regex_pattern:
                    customer = await db.customer_profiles.find_one({
                        "full_name": {"$regex": regex_pattern, "$options": "i"}
                    })
                    if customer:
                        return customer
        
        return None
    
    def _build_matching_query(
        self,
        extracted_data: Dict[str, Any],
        document_type: DocumentType
    ) -> Optional[Dict[str, Any]]:
        """Build MongoDB query to find customer by extracted identifiers"""
        or_conditions = []
        
        # Aadhaar matching
        if document_type == DocumentType.AADHAAR:
            aadhaar = extracted_data.get("aadhaar_number", "")
            if aadhaar:
                aadhaar_clean = re.sub(r'\s+', '', str(aadhaar))
                or_conditions.append({"aadhar_number": {"$regex": aadhaar_clean, "$options": "i"}})
        
        # PAN matching
        if document_type in [DocumentType.PAN, DocumentType.ITR_FORM]:
            pan = extracted_data.get("pan_number", "")
            if pan:
                pan_clean = re.sub(r'\s+', '', str(pan).upper())
                or_conditions.append({"pan_number": {"$regex": pan_clean, "$options": "i"}})
        
        # Passport matching
        if document_type == DocumentType.PASSPORT:
            passport = extracted_data.get("passport_number", "")
            if passport:
                or_conditions.append({"passport_number": {"$regex": passport, "$options": "i"}})
        
        # DL matching
        if document_type == DocumentType.DRIVING_LICENSE:
            dl = extracted_data.get("license_number", "")
            if dl:
                or_conditions.append({"dl_number": {"$regex": dl, "$options": "i"}})
        
        # GST matching
        if document_type == DocumentType.GST_RETURN:
            gstin = extracted_data.get("gstin", "")
            if gstin:
                gstin_clean = re.sub(r'\s+', '', str(gstin).upper())
                or_conditions.append({"gst_number": {"$regex": gstin_clean, "$options": "i"}})
        
        # Mobile number matching (if available)
        mobile = extracted_data.get("mobile_number", "")
        if mobile:
            mobile_clean = re.sub(r'\s+', '', str(mobile))
            or_conditions.append({"mobile_number": {"$regex": mobile_clean, "$options": "i"}})
        
        if or_conditions:
            return {"$or": or_conditions}
        
        return None
    
    def _extract_name(self, extracted_data: Dict[str, Any], document_type: DocumentType) -> Optional[str]:
        """Extract name from extracted data based on document type"""
        name_fields = ["name", "employee_name", "consumer_name", "account_holder_name", 
                      "candidate_name", "patient_name", "consumer_name", "tenant_name"]
        
        for field in name_fields:
            if extracted_data.get(field):
                return extracted_data[field]
        
        return None
    
    def _normalize_string(self, value: Any) -> str:
        """Normalize string for comparison"""
        if value is None:
            return ""
        return re.sub(r'\s+', ' ', str(value).strip().upper())
    
    async def find_bank_transaction_record(
        self,
        extracted_data: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Find bank transaction record matching the extracted bank statement data
        
        Matching strategies (in order):
        1. Match by account_number (primary identifier)
        2. Match by account_holder_name (case-insensitive)
        3. Match via customer_profiles: account_holder_name -> customer_profiles.full_name -> customer_id -> bank_transaction_record.user_id
        
        Args:
            extracted_data: Extracted bank statement data
            user_id: Optional user ID (may not match due to different ID systems)
        
        Returns:
            Bank transaction record dict if found, None otherwise
        """
        db = await get_database()
        
        account_number = extracted_data.get("account_number")
        account_holder_name = extracted_data.get("account_holder_name")
        
        # Strategy 1: Match by account number (primary identifier - most reliable)
        if account_number:
            # Normalize account number (remove spaces, hyphens)
            account_number_clean = re.sub(r'[\s\-]', '', str(account_number))
            query = {"account_number": account_number_clean}
            record = await db.bank_transaction_record.find_one(query)
            if record:
                return record
        
        # Strategy 2: Match by account_holder_name (case-insensitive)
        if account_holder_name:
            name_normalized = self._normalize_string(account_holder_name)
            query = {
                "account_holder_name": {"$regex": f"^{re.escape(name_normalized)}$", "$options": "i"}
            }
            # Also include account number if available for more precise matching
            if account_number:
                account_number_clean = re.sub(r'[\s\-]', '', str(account_number))
                query["account_number"] = account_number_clean
            
            record = await db.bank_transaction_record.find_one(query)
            if record:
                return record
        
        # Strategy 3: Match via customer_profiles (intermediary matching)
        # account_holder_name -> customer_profiles.full_name -> customer_id -> bank_transaction_record.user_id
        if account_holder_name:
            # First, find customer profile by matching account_holder_name to full_name
            name_normalized = self._normalize_string(account_holder_name)
            customer = await db.customer_profiles.find_one({
                "full_name": {"$regex": f"^{re.escape(name_normalized)}$", "$options": "i"}
            })
            
            if customer:
                customer_id = customer.get("customer_id")
                if customer_id:
                    # Now find bank transaction record using customer_id as user_id
                    query = {"user_id": customer_id}
                    # Also include account_number if available for more precise matching
                    if account_number:
                        account_number_clean = re.sub(r'[\s\-]', '', str(account_number))
                        query["account_number"] = account_number_clean
                    
                    record = await db.bank_transaction_record.find_one(query)
                    if record:
                        return record
        
        return None
    
    async def cross_validate_document(
        self,
        document_id: str,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cross-validate a single document against customer profile or bank transaction records
        
        Args:
            document_id: Document ID to validate
            user_id: Optional user ID for matching
        
        Returns:
            Validation report with matches, mismatches, and score
        """
        db = await get_database()
        
        # Get extraction result
        extraction = await db.extraction_results.find_one(
            {"document_id": document_id},
            sort=[("extraction_timestamp", -1)]
        )
        
        if not extraction:
            return {
                "document_id": document_id,
                "status": "error",
                "message": "Extraction result not found",
                "validation_score": 0.0
            }
        
        document_type = DocumentType(extraction["document_type"])
        extracted_data = extraction["extracted_fields"]
        
        # Special handling for BANK_STATEMENT - validate against bank_transaction_record
        if document_type == DocumentType.BANK_STATEMENT:
            return await self._cross_validate_bank_statement(
                document_id,
                extracted_data,
                user_id or extraction.get("user_id")
            )
        
        # For other document types, use customer profile validation
        customer = await self.find_customer_profile(
            extracted_data,
            document_type,
            user_id or extraction.get("user_id")
        )
        
        if not customer:
            return {
                "document_id": document_id,
                "document_type": document_type.value,
                "status": "warning",
                "message": "Customer profile not found in datasheet",
                "validation_score": 0.0,
                "customer_found": False
            }
        
        # Perform field-by-field validation
        validation_result = self._validate_fields(
            extracted_data,
            customer,
            document_type
        )
        
        # Calculate validation score
        validation_score = self._calculate_validation_score(validation_result)
        
        return {
            "document_id": document_id,
            "document_type": document_type.value,
            "customer_id": customer.get("customer_id"),
            "customer_name": customer.get("full_name"),
            "status": "success" if validation_score >= 80 else "warning",
            "validation_score": validation_score,
            "customer_found": True,
            "matches": validation_result["matches"],
            "mismatches": validation_result["mismatches"],
            "missing_in_extraction": validation_result["missing_in_extraction"],
            "missing_in_profile": validation_result["missing_in_profile"],
            "total_fields_checked": validation_result["total_fields_checked"],
            "matched_fields": validation_result["matched_fields"]
        }
    
    async def _cross_validate_bank_statement(
        self,
        document_id: str,
        extracted_data: Dict[str, Any],
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Cross-validate bank statement against bank_transaction_record collection
        
        Args:
            document_id: Document ID
            extracted_data: Extracted bank statement data
            user_id: Optional user ID
        
        Returns:
            Validation report with matches, mismatches, and score
        """
        # Find bank transaction record
        bank_record = await self.find_bank_transaction_record(extracted_data, user_id)
        
        if not bank_record:
            return {
                "document_id": document_id,
                "document_type": "BANK_STATEMENT",
                "status": "warning",
                "message": "Bank transaction record not found in database",
                "validation_score": 0.0,
                "customer_found": False
            }
        
        # Perform field-by-field validation
        validation_result = self._validate_fields(
            extracted_data,
            bank_record,
            DocumentType.BANK_STATEMENT
        )
        
        # Calculate validation score
        validation_score = self._calculate_validation_score(validation_result)
        
        return {
            "document_id": document_id,
            "document_type": "BANK_STATEMENT",
            "status": "success" if validation_score >= 80 else "warning",
            "validation_score": validation_score,
            "customer_found": True,
            "matches": validation_result["matches"],
            "mismatches": validation_result["mismatches"],
            "missing_in_extraction": validation_result["missing_in_extraction"],
            "missing_in_profile": validation_result["missing_in_profile"],
            "total_fields_checked": validation_result["total_fields_checked"],
            "matched_fields": validation_result["matched_fields"]
        }
    
    def _validate_fields(
        self,
        extracted_data: Dict[str, Any],
        customer: Dict[str, Any],
        document_type: DocumentType
    ) -> Dict[str, Any]:
        """Validate fields between extracted data and customer profile"""
        matches = []
        mismatches = []
        missing_in_extraction = []
        missing_in_profile = []
        
        field_mappings = self.field_mappings.get(document_type, [])
        
        for extracted_field, profile_field in field_mappings:
            extracted_value = extracted_data.get(extracted_field)
            profile_value = customer.get(profile_field)
            
            if not extracted_value and not profile_value:
                continue  # Both missing, skip
            
            if not extracted_value:
                missing_in_extraction.append({
                    "field": extracted_field,
                    "profile_field": profile_field,
                    "profile_value": profile_value
                })
                continue
            
            if not profile_value:
                missing_in_profile.append({
                    "field": extracted_field,
                    "profile_field": profile_field,
                    "extracted_value": extracted_value
                })
                continue
            
            # Compare values
            if self._values_match(extracted_value, profile_value, extracted_field):
                matches.append({
                    "field": extracted_field,
                    "profile_field": profile_field,
                    "extracted_value": extracted_value,
                    "profile_value": profile_value
                })
            else:
                mismatches.append({
                    "field": extracted_field,
                    "profile_field": profile_field,
                    "extracted_value": extracted_value,
                    "profile_value": profile_value
                })
        
        total_checked = len(field_mappings)
        matched_count = len(matches)
        
        return {
            "matches": matches,
            "mismatches": mismatches,
            "missing_in_extraction": missing_in_extraction,
            "missing_in_profile": missing_in_profile,
            "total_fields_checked": total_checked,
            "matched_fields": matched_count
        }
    
    def _values_match(self, value1: Any, value2: Any, field_name: str) -> bool:
        """Check if two values match (with normalization)"""
        if value1 is None or value2 is None:
            return False
        
        # Normalize both values
        val1_norm = self._normalize_string(value1)
        val2_norm = self._normalize_string(value2)
        
        # Exact match
        if val1_norm == val2_norm:
            return True
        
        # For numeric fields, allow small variance
        if "salary" in field_name.lower() or "score" in field_name.lower():
            try:
                num1 = float(value1)
                num2 = float(value2)
                diff = abs(num1 - num2)
                # Allow 5% variance or 1000 absolute difference for salary
                if "salary" in field_name.lower():
                    return diff <= max(1000, num2 * 0.05)
                # Allow 10 point difference for scores
                if "score" in field_name.lower():
                    return diff <= 10
            except:
                pass
        
        # For name fields, check partial match
        if "name" in field_name.lower():
            # Check if one contains the other (for handling middle names)
            if val1_norm in val2_norm or val2_norm in val1_norm:
                return True
            # Check if key parts match (first and last name)
            parts1 = set(val1_norm.split())
            parts2 = set(val2_norm.split())
            if len(parts1) >= 2 and len(parts2) >= 2:
                common_parts = parts1.intersection(parts2)
                if len(common_parts) >= 2:
                    return True
        
        # For dates, normalize and compare
        if "date" in field_name.lower() or "dob" in field_name.lower():
            return self._dates_match(str(value1), str(value2))
        
        return False
    
    def _dates_match(self, date1: str, date2: str) -> bool:
        """Check if two date strings match"""
        try:
            formats = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d", "%m/%d/%Y", "%d/%m/%y", "%m/%d/%y"]
            
            def parse_date(date_str: str):
                date_str = str(date_str).strip()
                for fmt in formats:
                    try:
                        return datetime.strptime(date_str, fmt)
                    except:
                        continue
                return None
            
            d1 = parse_date(date1)
            d2 = parse_date(date2)
            
            if d1 and d2:
                return d1.date() == d2.date()
            
            # Fallback: normalized string comparison
            return self._normalize_string(date1) == self._normalize_string(date2)
        except:
            return False
    
    def _calculate_validation_score(self, validation_result: Dict[str, Any]) -> float:
        """Calculate validation score (0-100)"""
        total = validation_result["total_fields_checked"]
        if total == 0:
            return 0.0
        
        matches = validation_result["matched_fields"]
        mismatches = len(validation_result["mismatches"])
        missing_ext = len(validation_result["missing_in_extraction"])
        missing_prof = len(validation_result["missing_in_profile"])
        
        # Score calculation:
        # - Matches: +100/total per match
        # - Mismatches: -50/total per mismatch
        # - Missing in extraction: -25/total per missing
        # - Missing in profile: -10/total per missing (less penalty)
        
        score = (matches * 100.0 / total) - (mismatches * 50.0 / total) - \
                (missing_ext * 25.0 / total) - (missing_prof * 10.0 / total)
        
        return max(0.0, min(100.0, score))
    
    async def cross_validate_user_documents(
        self,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Cross-validate all documents for a user
        
        Returns:
            Summary report with all document validations
        """
        db = await get_database()
        
        # Get all extraction results for user
        extractions = await db.extraction_results.find(
            {"user_id": user_id}
        ).to_list(length=None)
        
        if not extractions:
            return {
                "user_id": user_id,
                "total_documents": 0,
                "validations": [],
                "summary": {
                    "total": 0,
                    "passed": 0,
                    "warnings": 0,
                    "errors": 0,
                    "average_score": 0.0
                }
            }
        
        validations = []
        total_score = 0.0
        
        for extraction in extractions:
            validation = await self.cross_validate_document(
                extraction["document_id"],
                user_id
            )
            validations.append(validation)
            total_score += validation.get("validation_score", 0.0)
        
        # Calculate summary
        passed = sum(1 for v in validations if v.get("validation_score", 0) >= 80)
        warnings = sum(1 for v in validations if 50 <= v.get("validation_score", 0) < 80)
        errors = sum(1 for v in validations if v.get("validation_score", 0) < 50)
        
        return {
            "user_id": user_id,
            "total_documents": len(validations),
            "validations": validations,
            "summary": {
                "total": len(validations),
                "passed": passed,
                "warnings": warnings,
                "errors": errors,
                "average_score": total_score / len(validations) if validations else 0.0
            }
        }
    
    async def cross_validate_application_documents(
        self,
        application_id: str
    ) -> Dict[str, Any]:
        """
        Cross-validate all documents for an application
        
        Returns:
            Summary report with all document validations
        """
        db = await get_database()
        
        # Get all documents for this application
        docs = await db.documents.find(
            {"application_id": application_id}
        ).to_list(length=None)
        
        if not docs:
            return {
                "application_id": application_id,
                "total_documents": 0,
                "validations": [],
                "summary": {
                    "total": 0,
                    "passed": 0,
                    "warnings": 0,
                    "errors": 0,
                    "average_score": 0.0
                }
            }
        
        validations = []
        total_score = 0.0
        
        for doc in docs:
            # Get extraction for this document
            extraction = await db.extraction_results.find_one(
                {"document_id": doc["document_id"]},
                sort=[("extraction_timestamp", -1)]
            )
            
            if extraction:
                validation = await self.cross_validate_document(
                    doc["document_id"],
                    doc.get("user_id")
                )
                validations.append(validation)
                total_score += validation.get("validation_score", 0.0)
        
        # Calculate summary
        passed = sum(1 for v in validations if v.get("validation_score", 0) >= 80)
        warnings = sum(1 for v in validations if 50 <= v.get("validation_score", 0) < 80)
        errors = sum(1 for v in validations if v.get("validation_score", 0) < 50)
        
        return {
            "application_id": application_id,
            "total_documents": len(validations),
            "validations": validations,
            "summary": {
                "total": len(validations),
                "passed": passed,
                "warnings": warnings,
                "errors": errors,
                "average_score": round(total_score / len(validations), 2) if validations else 0.0
            }
        }
    
    async def cross_validate_all_documents(
        self,
        limit: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Cross-validate all documents in the system
        
        Args:
            limit: Optional limit on number of documents to validate
        
        Returns:
            Summary report
        """
        db = await get_database()
        
        # Get all extraction results
        query = {}
        cursor = db.extraction_results.find(query).sort("extraction_timestamp", -1)
        
        if limit:
            cursor = cursor.limit(limit)
        
        extractions = await cursor.to_list(length=None)
        
        if not extractions:
            return {
                "total_documents": 0,
                "validations": [],
                "summary": {
                    "total": 0,
                    "passed": 0,
                    "warnings": 0,
                    "errors": 0,
                    "average_score": 0.0
                }
            }
        
        validations = []
        total_score = 0.0
        
        for extraction in extractions:
            validation = await self.cross_validate_document(
                extraction["document_id"],
                extraction.get("user_id")
            )
            validations.append(validation)
            total_score += validation.get("validation_score", 0.0)
        
        # Calculate summary
        passed = sum(1 for v in validations if v.get("validation_score", 0) >= 80)
        warnings = sum(1 for v in validations if 50 <= v.get("validation_score", 0) < 80)
        errors = sum(1 for v in validations if v.get("validation_score", 0) < 50)
        
        return {
            "total_documents": len(validations),
            "validations": validations,
            "summary": {
                "total": len(validations),
                "passed": passed,
                "warnings": warnings,
                "errors": errors,
                "average_score": total_score / len(validations) if validations else 0.0
            }
        }

# Singleton instance
cross_validation_service = CrossValidationService()

