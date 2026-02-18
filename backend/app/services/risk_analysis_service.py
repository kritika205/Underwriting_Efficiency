"""
Risk Analysis Service for Underwriting
Performs anomaly detection using rule-based processes and LLM reasoning
"""
from typing import Dict, Any, List, Optional
from app.models.document import DocumentType
from app.prompts.risk_analysis_prompts import get_risk_analysis_prompt
from app.core.config import settings
from openai import AzureOpenAI
import json
import logging
from datetime import datetime, timezone
from app.services.bank_statement_analytics_service import bank_statement_analytics_service
import re

logger = logging.getLogger(__name__)

class RiskAnalysisService:
    """Risk analysis service with rule-based anomaly detection and LLM reasoning"""
    
    def __init__(self):
        self.risk_thresholds = {
            "low": 0.0,
            "medium": 30.0,
            "high": 60.0,
            "critical": 80.0
        }
        # Initialize Azure OpenAI client for LLM reasoning (with error handling)
        self.llm_client = None
        self.llm_deployment_name = None
        try:
            if (settings.AZURE_OPENAI_API_KEY and 
                settings.AZURE_OPENAI_ENDPOINT and 
                settings.AZURE_OPENAI_DEPLOYMENT_NAME):
                self.llm_client = AzureOpenAI(
                    api_key=settings.AZURE_OPENAI_API_KEY,
                    api_version=settings.AZURE_OPENAI_API_VERSION,
                    azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
                )
                self.llm_deployment_name = settings.AZURE_OPENAI_DEPLOYMENT_NAME
                logger.info("Azure OpenAI client initialized successfully")
            else:
                logger.warning("Azure OpenAI credentials not configured. LLM reasoning will be skipped.")
        except Exception as e:
            logger.warning(f"Failed to initialize Azure OpenAI client: {e}. LLM reasoning will be skipped.")
    
    async def analyze_risk(
        self,
        extracted_data: Dict[str, Any],
        document_type: DocumentType,
        validation_result: Dict[str, Any],
        user_id: Optional[str] = None,
        all_user_documents: Optional[Dict[str, Any]] = None,
        document_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive risk analysis
        
        Args:
            extracted_data: Extracted fields from document
            document_type: Type of document
            validation_result: Results from validation service
            user_id: User identifier
            all_user_documents: All documents for this user (for cross-document analysis)
            document_id: Document ID (optional, needed for bank statement analytics)
        
        Returns:
            Risk analysis result with anomalies, risk score, and LLM reasoning
        """
        try:
            # Validate inputs
            if not isinstance(extracted_data, dict):
                raise ValueError(f"extracted_data must be a dict, got {type(extracted_data)}")
            if not isinstance(validation_result, dict):
                logger.warning(f"validation_result is not a dict, using defaults. Got: {type(validation_result)}")
                validation_result = {"warnings": [], "errors": [], "quality_score": 100}
            
            logger.debug(f"Starting risk analysis for document type: {document_type.value}, user_id: {user_id}")
            
            # Step 1: Rule-based anomaly detection
            anomalies = await self._detect_anomalies(
                extracted_data,
                document_type,
                validation_result,
                user_id,
                all_user_documents,
                document_id
            )
            
            logger.debug(f"Anomaly detection completed: {anomalies.get('anomaly_count', 0)} anomalies found")
            
            # Step 2: Calculate risk score from anomalies
            risk_score = self._calculate_risk_score(anomalies, validation_result)
            logger.debug(f"Risk score calculated: {risk_score}")
            
            # Step 3: LLM reasoning on anomalies (if any)
            llm_reasoning = None
            if anomalies.get("critical_anomalies") or anomalies.get("high_anomalies"):
                logger.debug("Critical or high anomalies detected, calling LLM reasoning")
                llm_reasoning = await self._get_llm_reasoning(
                    extracted_data,
                    document_type,
                    anomalies,
                    validation_result
                )
            
            # Step 4: Generate recommendations
            recommendations = self._generate_recommendations(
                anomalies,
                risk_score,
                llm_reasoning
            )
            
            risk_level = self._get_risk_level(risk_score)
            logger.info(f"Risk analysis completed: level={risk_level}, score={risk_score}, anomalies={anomalies.get('anomaly_count', 0)}")
            
            return {
                "risk_score": risk_score,
                "risk_level": risk_level,
                "anomalies": anomalies,
                "llm_reasoning": llm_reasoning,
                "recommendations": recommendations,
                "analysis_timestamp": datetime.now(timezone.utc)
            }
            
        except Exception as e:
            logger.error(f"Risk analysis failed: {e}", exc_info=True)
            logger.error(f"Error details - type: {type(e).__name__}, args: {e.args}")
            raise Exception(f"Risk analysis failed: {str(e)}")
    
    async def _detect_anomalies(
        self,
        extracted_data: Dict[str, Any],
        document_type: DocumentType,
        validation_result: Dict[str, Any],
        user_id: Optional[str],
        all_user_documents: Optional[Dict[str, Any]],
        document_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Detect anomalies using rule-based processes"""
        anomalies = {
            "critical_anomalies": [],
            "high_anomalies": [],
            "medium_anomalies": [],
            "low_anomalies": [],
            "anomaly_count": 0
        }
        
        # Special handling for BANK_STATEMENT: Use comprehensive analytics service
        if document_type == DocumentType.BANK_STATEMENT:
            logger.info(f"BANK_STATEMENT detected - document_id: {document_id}, will use analytics service")
            if document_id:
                try:
                    logger.info(f"Calling bank_statement_analytics_service.analyze_bank_statement for document_id: {document_id}")
                    bank_analytics = await bank_statement_analytics_service.analyze_bank_statement(
                        document_id=document_id
                    )
                    logger.info(f"Bank analytics received: {list(bank_analytics.keys())}")
                    
                    # Check if analytics found transactions
                    if "error" in bank_analytics:
                        error_msg = bank_analytics.get('error', 'Unknown error')
                        logger.warning(f"Bank analytics returned error: {error_msg}")
                        # Create a medium-severity anomaly to indicate bank statement analysis couldn't be completed
                        anomalies["medium_anomalies"].append({
                            "type": "bank_statement_analysis_failed",
                            "field": "transactions",
                            "value": error_msg,
                            "reason": f"Bank statement analytics could not be completed: {error_msg}. This may indicate missing transaction data or extraction issues.",
                            "severity": "medium"
                        })
                    else:
                        logger.info(f"Bank analytics: fraud_analysis={bank_analytics.get('fraud_analysis', {}).get('total_anomalies', 0)} anomalies, "
                                  f"income_analysis salary_detected={bank_analytics.get('income_analysis', {}).get('salary_detected', False)}")
                        
                        # Convert bank analytics anomalies to risk analysis format
                        bank_anomalies = self._convert_bank_analytics_to_anomalies(bank_analytics)
                        logger.info(f"Converted bank anomalies: critical={len(bank_anomalies.get('critical', []))}, "
                                  f"high={len(bank_anomalies.get('high', []))}, medium={len(bank_anomalies.get('medium', []))}, "
                                  f"low={len(bank_anomalies.get('low', []))}")
                        
                        anomalies["critical_anomalies"].extend(bank_anomalies.get("critical", []))
                        anomalies["high_anomalies"].extend(bank_anomalies.get("high", []))
                        anomalies["medium_anomalies"].extend(bank_anomalies.get("medium", []))
                        anomalies["low_anomalies"].extend(bank_anomalies.get("low", []))
                        
                        logger.info(f"After adding bank anomalies: total critical={len(anomalies['critical_anomalies'])}, "
                                  f"high={len(anomalies['high_anomalies'])}, medium={len(anomalies['medium_anomalies'])}")
                except Exception as e:
                    logger.error(f"Bank statement analytics failed: {e}", exc_info=True)
                    # Create a medium-severity anomaly to indicate the failure
                    anomalies["medium_anomalies"].append({
                        "type": "bank_statement_analysis_error",
                        "field": "analytics",
                        "value": str(e),
                        "reason": f"Bank statement analytics service encountered an error: {str(e)}. Risk analysis completed with basic checks only.",
                        "severity": "medium"
                    })
                    # Fall through to basic detection
            else:
                logger.warning("BANK_STATEMENT detected but document_id is None - cannot run analytics")
                # Create a low-severity anomaly to indicate document_id was missing
                anomalies["low_anomalies"].append({
                    "type": "bank_statement_missing_document_id",
                    "field": "document_id",
                    "value": "None",
                    "reason": "Bank statement detected but document_id is missing. Comprehensive analytics cannot be performed.",
                    "severity": "low"
                })
        
        # Get document-specific anomaly detector
        detector = self._get_anomaly_detector(document_type)
        if detector:
            doc_anomalies = detector(extracted_data, validation_result)
            anomalies["critical_anomalies"].extend(doc_anomalies.get("critical", []))
            anomalies["high_anomalies"].extend(doc_anomalies.get("high", []))
            anomalies["medium_anomalies"].extend(doc_anomalies.get("medium", []))
            anomalies["low_anomalies"].extend(doc_anomalies.get("low", []))
        
        # Cross-document consistency checks
        if all_user_documents:
            cross_doc_anomalies = await self._check_cross_document_consistency(
                extracted_data,
                document_type,
                all_user_documents
            )
            anomalies["critical_anomalies"].extend(cross_doc_anomalies.get("critical", []))
            anomalies["high_anomalies"].extend(cross_doc_anomalies.get("high", []))
            anomalies["medium_anomalies"].extend(cross_doc_anomalies.get("medium", []))
        
        # Data quality anomalies
        quality_anomalies = self._check_data_quality_anomalies(
            extracted_data,
            validation_result
        )
        anomalies["medium_anomalies"].extend(quality_anomalies.get("medium", []))
        anomalies["low_anomalies"].extend(quality_anomalies.get("low", []))
        
        anomalies["anomaly_count"] = (
            len(anomalies["critical_anomalies"]) +
            len(anomalies["high_anomalies"]) +
            len(anomalies["medium_anomalies"]) +
            len(anomalies["low_anomalies"])
        )
        
        return anomalies
    
    def _get_anomaly_detector(self, document_type: DocumentType):
        """Get anomaly detector function for document type"""
        detectors = {
            DocumentType.AADHAAR: self._detect_aadhaar_anomalies,
            DocumentType.PAN: self._detect_pan_anomalies,
            DocumentType.PASSPORT: self._detect_passport_anomalies,
            DocumentType.PAYSLIP: self._detect_payslip_anomalies,
            DocumentType.BANK_STATEMENT: self._detect_bank_statement_anomalies,
            DocumentType.CIBIL_SCORE_REPORT: self._detect_cibil_anomalies,
            DocumentType.ITR_FORM: self._detect_itr_anomalies,
            DocumentType.GST_RETURN: self._detect_gst_anomalies,
        }
        return detectors.get(document_type)
    
    def _detect_aadhaar_anomalies(
        self,
        data: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Detect anomalies in Aadhaar documents"""
        anomalies = {"critical": [], "high": [], "medium": [], "low": []}
        
        # Check for suspicious patterns in Aadhaar number
        aadhaar = data.get("aadhaar_number", "")
        if aadhaar:
            aadhaar_clean = re.sub(r'\s+', '', str(aadhaar))
            # All same digits (e.g., 1111 1111 1111)
            if len(set(aadhaar_clean)) == 1:
                anomalies["medium"].append({
                    "type": "suspicious_aadhaar_pattern",
                    "field": "aadhaar_number",
                    "value": aadhaar,
                    "reason": "Aadhaar number contains all same digits",
                    "severity": "medium"
                })
            
            # Sequential pattern (e.g., 1234 5678 9012)
            if self._is_sequential(aadhaar_clean):
                anomalies["medium"].append({
                    "type": "sequential_aadhaar",
                    "field": "aadhaar_number",
                    "value": aadhaar,
                    "reason": "Aadhaar number appears to be sequential",
                    "severity": "medium"
                })
        
        # Date of birth inconsistencies
        dob = data.get("date_of_birth")
        if dob:
            try:
                dob_date = datetime.strptime(str(dob), "%Y-%m-%d")
                # Make dob_date timezone-aware for comparison
                dob_date = dob_date.replace(tzinfo=timezone.utc)
                age = (datetime.now(timezone.utc) - dob_date).days / 365.25
                if age < 0 or age > 120:
                    anomalies["critical"].append({
                        "type": "invalid_age",
                        "field": "date_of_birth",
                        "value": dob,
                        "reason": f"Calculated age ({age:.1f} years) is outside valid range",
                        "severity": "critical"
                    })
            except:
                pass
        
        # Name inconsistencies
        name = data.get("name", "")
        if name:
            # Very short name
            if len(name.strip()) < 3:
                anomalies["low"].append({
                    "type": "suspicious_name_length",
                    "field": "name",
                    "value": name,
                    "reason": "Name is unusually short",
                    "severity": "low"
                })
            
            # Contains numbers
            if re.search(r'\d', name):
                anomalies["medium"].append({
                    "type": "name_contains_numbers",
                    "field": "name",
                    "value": name,
                    "reason": "Name contains numeric characters",
                    "severity": "medium"
                })
        
        # Address inconsistencies
        address = data.get("address", "")
        if address and len(address) < 10:
            anomalies["medium"].append({
                "type": "incomplete_address",
                "field": "address",
                "value": address,
                "reason": "Address appears incomplete",
                "severity": "medium"
            })
        
        return anomalies
    
    def _detect_pan_anomalies(
        self,
        data: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Detect anomalies in PAN documents"""
        anomalies = {"critical": [], "high": [], "medium": [], "low": []}
        
        pan = data.get("pan_number", "")
        if pan:
            pan_clean = re.sub(r'\s+', '', str(pan).upper())
            
            # All same characters
            if len(set(pan_clean)) <= 2:
                anomalies["medium"].append({
                    "type": "suspicious_pan_pattern",
                    "field": "pan_number",
                    "value": pan,
                    "reason": "PAN number contains very few unique characters",
                    "severity": "medium"
                })
            
            # Sequential pattern
            if self._is_sequential(pan_clean[:5]):
                anomalies["medium"].append({
                    "type": "sequential_pan",
                    "field": "pan_number",
                    "value": pan,
                    "reason": "PAN number prefix appears sequential",
                    "severity": "medium"
                })
        
        # Name mismatch with father name
        name = data.get("name", "")
        father_name = data.get("father_name", "")
        if name and father_name:
            # Check if names are too similar (potential fraud)
            if self._names_too_similar(name, father_name):
                anomalies["high"].append({
                    "type": "name_similarity_issue",
                    "field": "name",
                    "value": f"Name: {name}, Father: {father_name}",
                    "reason": "Name and father's name are suspiciously similar",
                    "severity": "high"
                })
        
        return anomalies
    
    def _detect_payslip_anomalies(
        self,
        data: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Detect anomalies in Payslip documents"""
        anomalies = {"critical": [], "high": [], "medium": [], "low": []}
        
        # Salary inconsistencies
        salary_data = data.get("salary", {})
        if isinstance(salary_data, dict):
            gross = salary_data.get("gross_salary", 0)
            net = salary_data.get("net_salary", 0)
            deductions = salary_data.get("deductions", {})
            
            if gross and net:
                # Net salary greater than gross
                if net > gross:
                    anomalies["critical"].append({
                        "type": "salary_calculation_error",
                        "field": "salary",
                        "value": f"Gross: {gross}, Net: {net}",
                        "reason": "Net salary exceeds gross salary",
                        "severity": "critical"
                    })
                
                # Unusually high deductions (>50% of gross)
                total_deductions = sum(
                    v for k, v in deductions.items() if isinstance(v, (int, float))
                )
                if gross > 0 and (total_deductions / gross) > 0.5:
                    anomalies["high"].append({
                        "type": "high_deductions",
                        "field": "salary.deductions",
                        "value": f"Deductions: {total_deductions}, Gross: {gross}",
                        "reason": f"Deductions ({total_deductions/gross*100:.1f}%) are unusually high",
                        "severity": "high"
                    })
                
                # Negative salary
                if gross < 0 or net < 0:
                    anomalies["critical"].append({
                        "type": "negative_salary",
                        "field": "salary",
                        "value": f"Gross: {gross}, Net: {net}",
                        "reason": "Salary values are negative",
                        "severity": "critical"
                    })
        
        # Date inconsistencies
        month = data.get("month")
        year = data.get("year")
        if month and year:
            try:
                # Convert to integers if they're strings
                month_int = int(month) if not isinstance(month, int) else month
                year_int = int(year) if not isinstance(year, int) else year
                
                # Validate ranges
                if not (1 <= month_int <= 12):
                    anomalies["critical"].append({
                        "type": "invalid_month",
                        "field": "month",
                        "value": month,
                        "reason": f"Invalid month value: {month}",
                        "severity": "critical"
                    })
                    return anomalies
                
                if not (1900 <= year_int <= 2100):
                    anomalies["critical"].append({
                        "type": "invalid_year",
                        "field": "year",
                        "value": year,
                        "reason": f"Invalid year value: {year}",
                        "severity": "critical"
                    })
                    return anomalies
                
                current_date = datetime.now(timezone.utc)
                payslip_date = datetime(year_int, month_int, 1, tzinfo=timezone.utc)
                
                # Future-dated payslip
                if payslip_date > current_date:
                    anomalies["critical"].append({
                        "type": "future_dated_payslip",
                        "field": "month/year",
                        "value": f"{month_int}/{year_int}",
                        "reason": "Payslip is dated in the future",
                        "severity": "critical"
                    })
                
                # Very old payslip (>2 years)
                # Calculate the difference in days
                days_diff = (current_date - payslip_date).days
                if days_diff > 730:
                    anomalies["critical"].append({
                        "type": "old_payslip",
                        "field": "month/year",
                        "value": f"{month_int}/{year_int}",
                        "reason": "Payslip is more than 2 years old",
                        "severity": "critical"
                    })
            except (ValueError, TypeError) as e:
                anomalies["critical"].append({
                    "type": "date_parsing_error",
                    "field": "month/year",
                    "value": f"{month}/{year}",
                    "reason": f"Unable to parse date: {str(e)}",
                    "severity": "critical"
                })
            except Exception as e:
                # Log unexpected errors but don't crash
                logger.warning(f"Error validating payslip date: {str(e)}")
                anomalies["medium"].append({
                    "type": "date_validation_error",
                    "field": "month/year",
                    "value": f"{month}/{year}",
                    "reason": f"Error validating date: {str(e)}",
                    "severity": "medium"
                })
        
        return anomalies
    
    def _detect_bank_statement_anomalies(
        self,
        data: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Detect basic anomalies in Bank Statement documents
        
        Note: Comprehensive bank statement analytics (income, obligations, DTI, fraud detection)
        are handled by the bank_statement_analytics_service and integrated via _detect_anomalies.
        This method only handles basic validation-level checks.
        """
        anomalies = {"critical": [], "high": [], "medium": [], "low": []}
        
        # Basic validation checks only
        # Comprehensive analytics are handled by bank_statement_analytics_service
        
        return anomalies
    
    def _convert_bank_analytics_to_anomalies(self, bank_analytics: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Convert bank statement analytics results to risk analysis anomaly format"""
        anomalies = {"critical": [], "high": [], "medium": [], "low": []}
        
        logger.info("=" * 80)
        logger.info("_convert_bank_analytics_to_anomalies called")
        logger.info(f"bank_analytics keys: {list(bank_analytics.keys())}")
        
        fraud_analysis = bank_analytics.get("fraud_analysis", {})
        income_analysis = bank_analytics.get("income_analysis", {})
        dti_analysis = bank_analytics.get("dti_analysis", {})
        behavior_analysis = bank_analytics.get("behavior_analysis", {})
        obligation_analysis = bank_analytics.get("obligation_analysis", {})
        
        logger.info(f"income_analysis keys: {list(income_analysis.keys()) if income_analysis else 'None'}")
        logger.info(f"income_analysis full data: {income_analysis}")
        
        # Convert fraud anomalies
        for anomaly in fraud_analysis.get("anomalies", []):
            severity = anomaly.get("severity", "MEDIUM").lower()
            anomaly_type = anomaly.get("type", "")
            description = anomaly.get("description", "")
            
            anomaly_dict = {
                "type": anomaly_type.lower(),
                "field": "transactions",
                "value": description,
                "reason": description,
                "severity": severity
            }
            
            # Add additional context
            if anomaly_type == "ROUND_TRIPPING":
                instances = anomaly.get("instances", [])
                anomaly_dict["value"] = f"{len(instances)} round-tripping instances detected"
                anomaly_dict["reason"] = f"Large credits followed by similar debits (possible fake salary). Found {len(instances)} instances."
            elif anomaly_type == "TRANSACTION_SEQUENCE_ERROR":
                errors = anomaly.get("errors", [])
                
                if errors:
                    # Use the first error (which contains the overall balance mismatch)
                    error = errors[0]
                    opening = error.get("opening_balance", 0)
                    total_credits = error.get("total_credits", 0)
                    total_debits = error.get("total_debits", 0)
                    expected_closing = error.get("expected_balance", 0)
                    actual_closing = error.get("actual_balance", 0)
                    difference = error.get("difference", 0)
                    formula = error.get("formula", "")
                    
                    anomaly_dict["value"] = f"Balance mismatch: ₹{difference:,.2f} difference"
                    anomaly_dict["reason"] = f"Transaction sequence validation failed: {formula}, but actual closing balance is ₹{actual_closing:,.2f} (difference: ₹{difference:,.2f}). This indicates transactions may have been deleted or added manually (possible document tampering)."
                else:
                    anomaly_dict["value"] = "Balance calculation error"
                    anomaly_dict["reason"] = "Balance calculations don't match (possible tampering)"
                
                # Include error details in the anomaly for UI to display
                anomaly_dict["error_details"] = errors
            
            if severity == "critical":
                anomalies["critical"].append(anomaly_dict)
            elif severity == "high":
                anomalies["high"].append(anomaly_dict)
            elif severity == "medium":
                anomalies["medium"].append(anomaly_dict)
            else:
                anomalies["low"].append(anomaly_dict)
        
        # Income instability
        logger.info("=" * 80)
        logger.info("Starting Income Instability Check")
        salary_consistency_score = income_analysis.get("salary_consistency_score", 100)
        salary_amounts = income_analysis.get("salary_amounts", [])
        
        # Print statements as fallback (always visible)
        print("=" * 80)
        print("INCOME INSTABILITY CHECK")
        print(f"consistency_score={salary_consistency_score}")
        print(f"salary_amounts={salary_amounts}")
        print(f"salary_amounts count={len(salary_amounts) if salary_amounts else 0}")
        print(f"salary_detected={income_analysis.get('salary_detected', False)}")
        print(f"avg_monthly_salary={income_analysis.get('avg_monthly_salary', None)}")
        
        logger.info(f"Income instability check: consistency_score={salary_consistency_score}, salary_amounts={salary_amounts}, count={len(salary_amounts) if salary_amounts else 0}")
        logger.info(f"Income analysis salary_detected: {income_analysis.get('salary_detected', False)}")
        logger.info(f"Income analysis avg_monthly_salary: {income_analysis.get('avg_monthly_salary', None)}")
        
        # Check if we should flag income instability
        should_flag_instability = False
        instability_value = ""
        instability_reason = ""
        
        # Check consistency score threshold
        if salary_consistency_score < 50:
            should_flag_instability = True
            instability_value = f"Consistency score: {salary_consistency_score:.1f}"
            instability_reason = "High variation in salary amounts (salary consistency score < 50)"
            logger.info(f"Income instability flagged by consistency score: {salary_consistency_score}")
        
        # Also check for high percentage variation (even if consistency score is > 50)
        if salary_amounts and len(salary_amounts) >= 2:
            min_salary = min(salary_amounts)
            max_salary = max(salary_amounts)
            logger.info(f"Salary range check: min={min_salary}, max={max_salary}")
            if min_salary > 0:
                variation_pct = ((max_salary - min_salary) / min_salary) * 100
                logger.info(f"Salary variation percentage: {variation_pct:.1f}%")
                print(f"Salary variation check: min={min_salary}, max={max_salary}, variation={variation_pct:.1f}%", flush=True)
                # Flag if variation > 30% (lowered from 50% to catch more cases)
                # For 2 salaries, even 30% variation is significant
                threshold = 30.0 if len(salary_amounts) == 2 else 50.0
                print(f"Variation threshold: {threshold}% (using {'lower threshold for 2 salaries' if len(salary_amounts) == 2 else 'standard threshold'})", flush=True)
                if variation_pct > threshold:
                    should_flag_instability = True
                    # Use percentage variation format if it's more descriptive
                    if variation_pct > threshold or not instability_value:
                        instability_value = f"Salary range: ₹{min_salary:,.0f} - ₹{max_salary:,.0f} ({variation_pct:.1f}% variation)"
                        instability_reason = f"High variation in salary amounts: ranges from ₹{min_salary:,.0f} to ₹{max_salary:,.0f} ({variation_pct:.1f}% variation). Consistency score: {salary_consistency_score:.1f}"
                    print(f"Income instability flagged by percentage variation: {variation_pct:.1f}% > {threshold}%", flush=True)
                    logger.info(f"Income instability flagged by percentage variation: {variation_pct:.1f}%")
        else:
            logger.warning(f"Cannot check salary variation: salary_amounts={salary_amounts}, count={len(salary_amounts) if salary_amounts else 0}")
        
        if should_flag_instability:
            print(f"*** ADDING INCOME INSTABILITY ANOMALY ***")
            print(f"value={instability_value}")
            print(f"reason={instability_reason}")
            logger.info(f"Adding income_instability anomaly: value={instability_value}")
            anomalies["medium"].append({
                "type": "income_instability",
                "field": "salary",
                "value": instability_value,
                "reason": instability_reason,
                "severity": "medium"
            })
        else:
            print("*** INCOME INSTABILITY NOT FLAGGED ***")
            print(f"should_flag_instability={should_flag_instability}")
            logger.info("Income instability check passed - no anomaly created")
        
        # Salary gaps
        salary_gaps_info = income_analysis.get("salary_gaps", {})
        if salary_gaps_info.get("has_gaps", False):
            missing_months = salary_gaps_info.get("missing_months", [])
            total_salaries = salary_gaps_info.get("total_salaries_in_period", 0)
            expected_months = salary_gaps_info.get("expected_months", 0)
            statement_period = salary_gaps_info.get("statement_period", {})
            
            # Create detailed message
            # total_salaries now represents unique months with salary (not total transactions)
            total_transactions = salary_gaps_info.get("total_salary_transactions", total_salaries)
            if statement_period:
                period_str = f"{statement_period.get('from')} to {statement_period.get('to')}"
                reason = f"Missing salary payments in {len(missing_months)} month(s) during statement period ({period_str}). Found salaries in {total_salaries} out of {expected_months} month(s) ({total_transactions} total salary transaction(s))."
            else:
                reason = f"Missing salary payments in {len(missing_months)} month(s). Found salaries in {total_salaries} out of {expected_months} expected month(s) ({total_transactions} total salary transaction(s))."
            
            anomalies["medium"].append({
                "type": "salary_gaps",
                "field": "salary",
                "value": f"Missing months: {', '.join(missing_months)}",
                "reason": reason,
                "severity": "medium"
            })
        
        # Last salary date flag (only for recent statements, not historical ones)
        if income_analysis.get("salary_gap_flag", False):
            days = income_analysis.get("days_since_last_salary", 0)
            last_salary_date = income_analysis.get("last_salary_date")
            salary_gaps_info = income_analysis.get("salary_gaps", {})
            statement_period = salary_gaps_info.get("statement_period", {})
            
            # Create detailed message with statement period context
            if statement_period and last_salary_date:
                period_str = f"{statement_period.get('from')} to {statement_period.get('to')}"
                reason = f"Last salary was {days} days before statement period end ({period_str}). Statement is recent (within last 3 months), indicating possible job loss or salary delay."
            else:
                reason = f"Last salary was {days} days ago (>45 days - possible job loss). Note: This check only applies to recent statements."
            
            anomalies["high"].append({
                "type": "salary_delay",
                "field": "salary",
                "value": f"{days} days since last salary",
                "reason": reason,
                "severity": "high"
            })
        
        # DTI issues
        # DTI Risk Check: Only check if DTI > 50% (high risk threshold)
        # Note: Stated DTI comparison removed as stated_obligations is not available from customer profile
        actual_dti = dti_analysis.get("actual_dti", 0)
        if actual_dti and actual_dti > 50:
            anomalies["high"].append({
                "type": "high_dti",
                "field": "dti",
                "value": f"DTI: {actual_dti:.1f}%",
                "reason": f"Debt-to-Income ratio is {actual_dti:.1f}% (>50% threshold). High DTI indicates the customer has significant debt obligations relative to their income, which increases credit risk.",
                "severity": "high"
            })
        
        # Liquidity stress
        if behavior_analysis.get("liquidity_status") == "STRESSED":
            amb_ratio = behavior_analysis.get("amb_to_income_ratio", 0)
            anomalies["medium"].append({
                "type": "liquidity_stress",
                "field": "balance",
                "value": f"AMB/Income ratio: {amb_ratio:.1f}%",
                "reason": f"Average monthly balance is only {amb_ratio:.1f}% of monthly income (living paycheck-to-paycheck)",
                "severity": "medium"
            })
        
        # CRITICAL: Check if customer declared "No" existing loans but has ANY EMI payments
        # This checks the existing_loan field from the customer_profiles collection in the database
        customer_profile = bank_analytics.get("customer_profile", {})
        existing_loan = customer_profile.get("existing_loan")
        customer_id = customer_profile.get("customer_id")
        customer_name = customer_profile.get("full_name")
        
        # Get ALL EMI transactions (not just recurring ones) to check for contradiction
        all_emi_transactions = obligation_analysis.get("detected_emis", [])
        recurring_emis = obligation_analysis.get("recurring_emis", [])
        total_emi = obligation_analysis.get("total_monthly_emi_obligation", 0)
        
        logger.info(f"Checking existing_loan contradiction from customer_profiles collection: customer_id={customer_id}, customer_name={customer_name}, existing_loan='{existing_loan}', all_emi_transactions={len(all_emi_transactions)}, recurring_emis={len(recurring_emis)}")
        
        # Normalize existing_loan value (handle case variations: "No", "no", "NO", "N", "False", etc.)
        existing_loan_normalized = str(existing_loan).strip().upper() if existing_loan else None
        
        # CRITICAL ANOMALY: If customer declared "No" existing loans but has ANY EMI payments
        if existing_loan_normalized in ["NO", "N", "FALSE", "0"]:
            if all_emi_transactions:
                # Customer declared no loans but has EMI payments - CRITICAL contradiction
                # Parse EMI amounts (handle different formats)
                def parse_emi_amount(emi_dict):
                    amount = emi_dict.get("amount", 0)
                    if isinstance(amount, (int, float)):
                        return float(amount)
                    if isinstance(amount, str):
                        return float(amount.replace(',', '').replace('₹', '').strip() or 0)
                    return 0.0
                
                total_emi_amount = sum(parse_emi_amount(emi) for emi in all_emi_transactions)
                emi_count = len(all_emi_transactions)
                
                # Group by lender and amount for details
                emi_summary = {}
                for emi in all_emi_transactions:
                    lender = emi.get("lender_name", "Unknown")
                    amount = parse_emi_amount(emi)
                    key = f"{lender}_{round(amount)}"
                    if key not in emi_summary:
                        emi_summary[key] = {"lender": lender, "amount": amount, "count": 0, "dates": []}
                    emi_summary[key]["count"] += 1
                    if emi.get("date"):
                        emi_summary[key]["dates"].append(emi.get("date"))
                
                emi_details = ", ".join([
                    f"{info['lender']}: ₹{info['amount']:,.0f} ({info['count']} payment(s))"
                    for info in emi_summary.values()
                ])
                
                anomalies["critical"].append({
                    "type": "undeclared_loans",
                    "field": "obligations",
                    "value": f"Declared no loans but {emi_count} EMI payment(s) detected: ₹{total_emi_amount:,.0f} total",
                    "reason": f"Customer profile (customer_profiles collection) shows 'existing_loan: No' but bank statement reveals {emi_count} EMI payment(s) totaling ₹{total_emi_amount:,.0f} ({emi_details}). This is a direct contradiction - customer declared no existing loans but has EMI payments in bank statement, indicating undeclared/hidden debt obligations.",
                    "severity": "critical"
                })
                logger.warning(f"CRITICAL ANOMALY: Customer (ID: {customer_id}) declared 'existing_loan: No' in customer_profiles collection but {emi_count} EMI payment(s) detected in bank statement totaling ₹{total_emi_amount:,.0f}")
            elif recurring_emis:
                # Fallback: If detected_emis not available, use recurring_emis
                total_emi_transactions = sum(emi.get("occurrences", 1) for emi in recurring_emis)
                emi_details = ", ".join([
                    f"{emi.get('lender_name', 'Unknown')}: ₹{emi.get('emi_amount', 0):,.0f}/month ({emi.get('occurrences', 0)} payments)"
                    for emi in recurring_emis
                ])
                
                anomalies["critical"].append({
                    "type": "undeclared_loans",
                    "field": "obligations",
                    "value": f"Declared no loans but {len(recurring_emis)} recurring EMI type(s) detected ({total_emi_transactions} total payments): ₹{total_emi:,.0f}/month",
                    "reason": f"Customer profile (customer_profiles collection) shows 'existing_loan: No' but bank statement reveals {len(recurring_emis)} recurring EMI type(s) with {total_emi_transactions} total EMI payment(s) totaling ₹{total_emi:,.0f}/month ({emi_details}). This is a direct contradiction indicating undeclared/hidden debt obligations.",
                    "severity": "critical"
                })
                logger.warning(f"CRITICAL ANOMALY: Customer (ID: {customer_id}) declared 'existing_loan: No' in customer_profiles collection but {len(recurring_emis)} recurring EMI type(s) with {total_emi_transactions} total EMI payment(s) detected in bank statement totaling ₹{total_emi:,.0f}/month")
        
        # Hidden debt detection (EMIs not declared) - only if existing_loan is NOT "Yes"
        # If existing_loan is "Yes", EMIs are expected and should NOT be flagged as hidden debt
        elif recurring_emis and existing_loan_normalized not in ["YES", "Y", "TRUE", "1"]:
            # HIGH severity: EMIs detected but customer declared "Yes" for existing_loan OR field not set/unknown
            # Only flag if existing_loan is NOT explicitly "Yes"
            if existing_loan_normalized is None:
                reason = f"Detected {len(recurring_emis)} recurring EMI(s) totaling ₹{total_emi:,.0f}/month. Customer's existing_loan status is not declared in profile."
            else:
                reason = f"Detected {len(recurring_emis)} recurring EMI(s) totaling ₹{total_emi:,.0f}/month. Customer's existing_loan status is '{existing_loan}' (not clearly 'Yes')."
            
            anomalies["high"].append({
                "type": "hidden_debt",
                "field": "obligations",
                "value": f"Total EMIs: ₹{total_emi:,.0f}/month ({len(recurring_emis)} lenders)",
                "reason": reason,
                "severity": "high"
            })
            logger.info(f"HIDDEN DEBT: Customer (ID: {customer_id}) has existing_loan='{existing_loan}' but EMIs detected. Flagging as hidden debt.")
        elif recurring_emis and existing_loan_normalized in ["YES", "Y", "TRUE", "1"]:
            # Customer declared existing_loan: Yes, so EMIs are expected - do NOT flag as hidden debt
            logger.info(f"EMIs detected for customer (ID: {customer_id}) but existing_loan='Yes' - EMIs are expected, NOT flagging as hidden debt.")
        
        return anomalies
    
    def _detect_cibil_anomalies(
        self,
        data: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Detect anomalies in CIBIL Score Report"""
        anomalies = {"critical": [], "high": [], "medium": [], "low": []}
        
        # Check credit score
        credit_score_data = data.get("CREDIT_SCORE", {})
        if isinstance(credit_score_data, dict):
            score = credit_score_data.get("credit_score")
            if score:
                # Invalid score range
                if score < 300 or score > 900:
                    anomalies["critical"].append({
                        "type": "invalid_credit_score",
                        "field": "CREDIT_SCORE.credit_score",
                        "value": score,
                        "reason": f"Credit score {score} is outside valid range (300-900)",
                        "severity": "critical"
                    })
                
                # Very low score
                if score < 500:
                    anomalies["high"].append({
                        "type": "low_credit_score",
                        "field": "CREDIT_SCORE.credit_score",
                        "value": score,
                        "reason": f"Credit score {score} is very low",
                        "severity": "high"
                    })
        
        # Check for overdue accounts
        accounts = data.get("ACCOUNTS", {})
        if isinstance(accounts, dict):
            account_list = accounts.get("accounts", [])
            if isinstance(account_list, list):
                overdue_count = sum(
                    1 for acc in account_list
                    if isinstance(acc, dict) and acc.get("overdue_amount", 0) > 0
                )
                if overdue_count > 0:
                    anomalies["high"].append({
                        "type": "overdue_accounts",
                        "field": "ACCOUNTS.accounts",
                        "value": f"{overdue_count} accounts with overdue amounts",
                        "reason": f"{overdue_count} account(s) have overdue amounts",
                        "severity": "high"
                    })
        
        return anomalies
    
    def _detect_itr_anomalies(
        self,
        data: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Detect anomalies in ITR Form documents"""
        anomalies = {"critical": [], "high": [], "medium": [], "low": []}
        
        # Check assessment year
        assessment_year = data.get("assessment_year")
        if assessment_year:
            current_year = datetime.now(timezone.utc).year
            try:
                year = int(assessment_year)
                # Future assessment year
                if year > current_year:
                    anomalies["critical"].append({
                        "type": "future_assessment_year",
                        "field": "assessment_year",
                        "value": assessment_year,
                        "reason": "Assessment year is in the future",
                        "severity": "critical"
                    })
            except:
                pass
        
        return anomalies
    
    def _detect_gst_anomalies(
        self,
        data: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Detect anomalies in GST Return documents"""
        anomalies = {"critical": [], "high": [], "medium": [], "low": []}
        
        # Check GSTIN format
        gstin = data.get("gstin", "")
        if gstin:
            gstin_clean = re.sub(r'\s+', '', str(gstin).upper())
            # All same characters
            if len(set(gstin_clean)) <= 3:
                anomalies["high"].append({
                    "type": "suspicious_gstin_pattern",
                    "field": "gstin",
                    "value": gstin,
                    "reason": "GSTIN contains very few unique characters",
                    "severity": "high"
                })
        
        return anomalies
    
    def _detect_passport_anomalies(
        self,
        data: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Detect anomalies in Passport documents"""
        anomalies = {"critical": [], "high": [], "medium": [], "low": []}
        
        # Check expiry date
        expiry = data.get("date_of_expiry")
        if expiry:
            try:
                expiry_date = datetime.strptime(str(expiry), "%Y-%m-%d")
                # Make expiry_date timezone-aware for comparison
                expiry_date = expiry_date.replace(tzinfo=timezone.utc)
                if expiry_date < datetime.now(timezone.utc):
                    anomalies["high"].append({
                        "type": "expired_passport",
                        "field": "date_of_expiry",
                        "value": expiry,
                        "reason": "Passport has expired",
                        "severity": "high"
                    })
            except:
                pass
        
        return anomalies
    
    async def _check_cross_document_consistency(
        self,
        extracted_data: Dict[str, Any],
        document_type: DocumentType,
        all_user_documents: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Check consistency across user's documents"""
        anomalies = {"critical":[],"high": [], "medium": [], "low":[]}
        
        # Extract key identifiers
        current_name = self._extract_name(extracted_data, document_type)
        current_dob = extracted_data.get("date_of_birth")
        
        # Compare with other documents
        for doc_type, docs in all_user_documents.get("documents_by_type", {}).items():
            for doc_id in docs:
                doc_data = all_user_documents.get("documents", {}).get(doc_id, {})
                if isinstance(doc_data, dict):
                    doc_fields = doc_data.get("extracted_fields", {})
                    
                    # Name mismatch
                    other_name = self._extract_name(doc_fields, DocumentType(doc_data.get("document_type", "UNKNOWN")))
                    if current_name and other_name and not self._names_match(current_name, other_name):
                        anomalies["critical"].append({
                            "type": "name_mismatch_across_documents",
                            "field": "name",
                            "value": f"Current: {current_name}, Other: {other_name}",
                            "reason": f"Name mismatch with {doc_data.get('document_type')} document - critical identity verification failure",
                            "severity": "critical"
                        })
                    
                    # DOB mismatch
                    other_dob = doc_fields.get("date_of_birth")
                    if current_dob and other_dob and not self._dates_match(current_dob, other_dob):
                        anomalies["critical"].append({
                            "type": "dob_mismatch_across_documents",
                            "field": "date_of_birth",
                            "value": f"Current: {current_dob}, Other: {other_dob}",
                            "reason": f"Date of birth mismatch with {doc_data.get('document_type')} document - critical identity verification failure",
                            "severity": "critical"
                        })
        
        # Cross-document income validation: Payslip vs Bank Statement
        # Check if payslip salary is higher than bank statement salary credits (over-stated income)
        # IMPORTANT: Only run this check when analyzing PAYSLIP or BANK_STATEMENT documents
        # This prevents duplicate anomalies when the check runs for CIBIL, RENT_AGREEMENT, etc.
        payslip_docs = all_user_documents.get("documents_by_type", {}).get("PAYSLIP", [])
        bank_statement_docs = all_user_documents.get("documents_by_type", {}).get("BANK_STATEMENT", [])
        
        # Run over-stated income check when analyzing PAYSLIP or BANK_STATEMENT documents
        # But only create the anomaly once - use a flag to prevent duplicates
        # Prefer running when PAYSLIP is analyzed (has salary data readily available)
        should_check_income = document_type in [DocumentType.PAYSLIP, DocumentType.BANK_STATEMENT]
        
        print(f"\n{'='*80}", flush=True)
        print(f"🔍 OVER-STATED INCOME CHECK: Payslip vs Bank Statement", flush=True)
        print(f"{'='*80}", flush=True)
        print(f"Current document type: {document_type.value}", flush=True)
        print(f"Should check income: {should_check_income}", flush=True)
        print(f"Payslip documents found: {len(payslip_docs) if payslip_docs else 0}", flush=True)
        print(f"Bank Statement documents found: {len(bank_statement_docs) if bank_statement_docs else 0}", flush=True)
        
        if should_check_income and payslip_docs and bank_statement_docs:
            print(f"✅ Both document types present - Starting comparison...", flush=True)
            
            # Only check the first payslip with the first bank statement to avoid duplicates
            # This ensures we only create one anomaly per application, not one per document analysis
            payslip_id_to_check = payslip_docs[0] if payslip_docs else None
            bank_stmt_id_to_check = bank_statement_docs[0] if bank_statement_docs else None
            
            if payslip_id_to_check and bank_stmt_id_to_check:
                print(f"📋 Checking payslip {payslip_id_to_check} vs bank statement {bank_stmt_id_to_check} (first pair only to avoid duplicates)", flush=True)
                
                # Get payslip salary (only check first payslip)
                payslip_id = payslip_id_to_check
                payslip_data = all_user_documents.get("documents", {}).get(payslip_id, {})
                if isinstance(payslip_data, dict):
                    payslip_fields = payslip_data.get("extracted_fields", {})
                    
                    # DEBUG: Log all payslip fields to identify the issue
                    print(f"🔍 DEBUG: Payslip {payslip_id} extracted_fields keys: {list(payslip_fields.keys())}", flush=True)
                    print(f"🔍 DEBUG: Payslip {payslip_id} net_salary value: {payslip_fields.get('net_salary')} (type: {type(payslip_fields.get('net_salary'))})", flush=True)
                    print(f"🔍 DEBUG: Payslip {payslip_id} gross_salary value: {payslip_fields.get('gross_salary')} (type: {type(payslip_fields.get('gross_salary'))})", flush=True)
                    logger.info(f"DEBUG Payslip {payslip_id}: net_salary={payslip_fields.get('net_salary')}, gross_salary={payslip_fields.get('gross_salary')}, all_fields={list(payslip_fields.keys())}")
                    
                    # Try to get salary from top level first (after normalization)
                    # Then try nested under "salary" object (before normalization)
                    payslip_salary = None
                    
                    # Method 1: Check top-level fields (after normalization)
                    if payslip_fields.get("net_salary") is not None:
                        payslip_salary = payslip_fields.get("net_salary")
                        raw_value = payslip_fields.get("net_salary")
                        print(f"📄 Payslip {payslip_id}: Found net_salary at top level: ₹{payslip_salary:,.2f}", flush=True)
                        print(f"   Raw net_salary value: {raw_value} (type: {type(raw_value)})", flush=True)
                        logger.info(f"Payslip {payslip_id} net_salary: {raw_value} (raw), {payslip_salary:,.2f} (formatted)")
                    elif payslip_fields.get("gross_salary") is not None:
                        payslip_salary = payslip_fields.get("gross_salary")
                        print(f"📄 Payslip {payslip_id}: Found gross_salary at top level: ₹{payslip_salary:,.2f}", flush=True)
                        print(f"   ⚠️  WARNING: Using gross_salary instead of net_salary! This may cause incorrect comparison.", flush=True)
                        logger.warning(f"Payslip {payslip_id}: net_salary not found, using gross_salary {payslip_salary} instead")
                    else:
                        # Method 2: Check nested under "salary" object (before normalization)
                        salary_data = payslip_fields.get("salary", {})
                        if isinstance(salary_data, dict):
                            payslip_salary = salary_data.get("net_salary") or salary_data.get("gross_salary")
                            if payslip_salary:
                                print(f"📄 Payslip {payslip_id}: Found salary in nested object - net_salary={salary_data.get('net_salary')}, gross_salary={salary_data.get('gross_salary')}", flush=True)
                        elif isinstance(salary_data, (int, float)):
                            payslip_salary = salary_data
                            print(f"📄 Payslip {payslip_id}: Found salary as direct number: ₹{payslip_salary:,.2f}", flush=True)
                    
                    if not payslip_salary:
                        print(f"⚠️  Payslip {payslip_id}: No salary data found (checked top-level net_salary/gross_salary and nested salary object)", flush=True)
                    
                    if payslip_salary is not None:
                        # Ensure we have a numeric value
                        try:
                            payslip_salary = float(payslip_salary)
                            print(f"💰 Payslip Net Pay (final): ₹{payslip_salary:,.2f}", flush=True)
                            logger.info(f"Payslip {payslip_id} final net_salary value: {payslip_salary}")
                            
                            # CRITICAL VALIDATION: Check if value seems incorrect
                            # Common payslip net_salary values should be reasonable
                            # If we see values like 63435 when we expect 62935, log a warning
                            if payslip_salary == 63435.0:
                                logger.warning(f"⚠️  SUSPICIOUS VALUE DETECTED: Payslip {payslip_id} net_salary is 63435.0 - this might be incorrect (expected ~62935). Check extraction!")
                                print(f"   ⚠️  WARNING: net_salary value 63435.0 detected - this may be incorrect!", flush=True)
                            
                            # Validate: net_salary should be reasonable (between 0 and gross_salary)
                            gross_salary = payslip_fields.get("gross_salary")
                            if gross_salary:
                                gross_salary = float(gross_salary)
                                if payslip_salary > gross_salary:
                                    logger.warning(f"Payslip {payslip_id}: net_salary ({payslip_salary}) exceeds gross_salary ({gross_salary}) - this is invalid!")
                                    print(f"   ⚠️  WARNING: net_salary ({payslip_salary:,.2f}) exceeds gross_salary ({gross_salary:,.2f})!", flush=True)
                        except (ValueError, TypeError) as e:
                            logger.error(f"Payslip {payslip_id}: Could not convert payslip_salary to float: {payslip_salary}, error: {e}")
                            payslip_salary = None
                        
                        # Compare with bank statement salary credits (only check first bank statement to avoid duplicates)
                        if bank_stmt_id_to_check:
                            bank_stmt_id = bank_stmt_id_to_check
                            bank_stmt_data = all_user_documents.get("documents", {}).get(bank_stmt_id, {})
                            if isinstance(bank_stmt_data, dict):
                                # Try to get bank statement analytics from all_user_documents first
                                bank_analytics = bank_stmt_data.get("analytics", {})
                                
                                # If analytics not available, fetch from bank_statement_analytics_service
                                if not bank_analytics or not bank_analytics.get("income_analysis"):
                                    try:
                                        logger.info(f"Fetching bank statement analytics for document {bank_stmt_id} to compare with payslip")
                                        bank_analytics = await bank_statement_analytics_service.analyze_bank_statement(
                                            document_id=bank_stmt_id
                                        )
                                    except Exception as e:
                                        logger.warning(f"Could not fetch bank statement analytics for {bank_stmt_id}: {e}")
                                        bank_analytics = None
                                
                                # Only proceed if we have valid analytics
                                if bank_analytics:
                                    income_analysis = bank_analytics.get("income_analysis", {})
                                    
                                    print(f"📊 Bank Statement {bank_stmt_id}: Analytics fetched", flush=True)
                                    
                                    # Get actual salary transaction amounts (not average)
                                    # Use salary_amounts list from income_analysis (contains individual salary transaction amounts)
                                    salary_amounts = income_analysis.get("salary_amounts", [])
                                    
                                    if salary_amounts and len(salary_amounts) > 0:
                                        # Use the first salary transaction amount for comparison
                                        # (Alternatively, could use latest/most recent)
                                        bank_salary_amount = float(salary_amounts[0])
                                        print(f"💰 Bank Statement Salary (first transaction): ₹{bank_salary_amount:,.2f}", flush=True)
                                        print(f"   Total salary transactions found: {len(salary_amounts)}", flush=True)
                                        print(f"   All salary amounts: {salary_amounts}", flush=True)
                                        
                                        # Compare Payslip Net Pay (take-home salary) with Bank Statement Salary Credit
                                        # Net Pay should match the actual credit amount in bank statement
                                        # If payslip shows higher than bank credit → possible over-stated income
                                        print(f"📐 Comparison:", flush=True)
                                        print(f"   Payslip Net Pay:    ₹{payslip_salary:,.2f} (take-home salary)", flush=True)
                                        print(f"   Bank Salary Credit:  ₹{bank_salary_amount:,.2f} (actual credit in bank)", flush=True)
                                        
                                        # Direct comparison: Payslip Net Pay should match or be close to Bank Salary Credit
                                        # If payslip is significantly higher, it's over-stated income
                                        if payslip_salary > bank_salary_amount:
                                            print(f"   ❌ OVER-STATED INCOME DETECTED!", flush=True)
                                            difference = payslip_salary - bank_salary_amount
                                            difference_pct = (difference / bank_salary_amount * 100) if bank_salary_amount > 0 else 0
                                            
                                            # Check if this anomaly already exists to prevent duplicates
                                            # (can happen if both PAYSLIP and BANK_STATEMENT trigger the check)
                                            existing_anomaly = None
                                            for existing in anomalies.get("high", []):
                                                if (existing.get("type") == "over_stated_income" and 
                                                    existing.get("document_comparison", {}).get("payslip_document_id") == payslip_id and
                                                    existing.get("document_comparison", {}).get("bank_statement_document_id") == bank_stmt_id):
                                                    existing_anomaly = existing
                                                    break
                                            
                                            if not existing_anomaly:
                                                anomalies["high"].append({
                                                    "type": "over_stated_income",
                                                    "field": "salary",
                                                    "value": f"Payslip Net Pay: ₹{payslip_salary:,.2f}, Bank Salary Credit: ₹{bank_salary_amount:,.2f}",
                                                    "reason": f"Payslip shows Net Pay of ₹{payslip_salary:,.2f} but bank statement shows actual salary credit of ₹{bank_salary_amount:,.2f} (difference: ₹{difference:,.2f}, {difference_pct:.1f}% higher). Net Pay should match the bank credit amount. Possible over-stated income fraud.",
                                                    "severity": "high",
                                                    "document_comparison": {
                                                        "payslip_document_id": payslip_id,
                                                        "bank_statement_document_id": bank_stmt_id,
                                                        "payslip_salary": payslip_salary,
                                                        "bank_statement_salary": bank_salary_amount,
                                                        "difference": difference,
                                                        "difference_percentage": difference_pct,
                                                        "all_bank_salary_amounts": salary_amounts
                                                    }
                                                })
                                                logger.warning(f"Over-stated income detected: Payslip ₹{payslip_salary:,.2f} vs Bank Statement ₹{bank_salary_amount:,.2f}")
                                                print(f"   ✅ Anomaly added: HIGH severity", flush=True)
                                            else:
                                                print(f"   ℹ️  Anomaly already exists - skipping duplicate", flush=True)
                                        else:
                                            print(f"   ✅ No anomaly: Payslip Net Pay matches or is lower than Bank Salary Credit (difference: ₹{payslip_salary - bank_salary_amount:,.2f})", flush=True)
                                    else:
                                        print(f"⚠️  Bank Statement {bank_stmt_id}: No salary transactions found in income_analysis", flush=True)
                                else:
                                    print(f"⚠️  Bank Statement {bank_stmt_id}: Could not fetch analytics", flush=True)
        elif not should_check_income:
            print(f"ℹ️  Skipping over-stated income check (not analyzing PAYSLIP or BANK_STATEMENT document)", flush=True)
        else:
            if not payslip_docs:
                print(f"⚠️  No PAYSLIP documents found - skipping over-stated income check", flush=True)
            if not bank_statement_docs:
                print(f"⚠️  No BANK_STATEMENT documents found - skipping over-stated income check", flush=True)
        
        print(f"{'='*80}\n", flush=True)
        
        return anomalies
    
    def _check_data_quality_anomalies(
        self,
        extracted_data: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Check for data quality issues"""
        anomalies = {"medium": [], "low": []}
        
        # Low quality score
        quality_score = validation_result.get("quality_score", 100)
        if quality_score < 50:
            anomalies["medium"].append({
                "type": "low_quality_score",
                "field": "overall",
                "value": quality_score,
                "reason": f"Document quality score ({quality_score}) is below acceptable threshold",
                "severity": "medium"
            })
        
        # Many validation errors
        errors = validation_result.get("errors", [])
        if len(errors) > 3:
            anomalies["medium"].append({
                "type": "multiple_validation_errors",
                "field": "overall",
                "value": len(errors),
                "reason": f"Document has {len(errors)} validation errors",
                "severity": "medium"
            })
        
        # Missing critical fields
        warnings = validation_result.get("warnings", [])
        if len(warnings) > 5:
            anomalies["low"].append({
                "type": "many_warnings",
                "field": "overall",
                "value": len(warnings),
                "reason": f"Document has {len(warnings)} validation warnings",
                "severity": "low"
            })
        
        return anomalies
    
    async def _get_llm_reasoning(
        self,
        extracted_data: Dict[str, Any],
        document_type: DocumentType,
        anomalies: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Use LLM to provide reasoning on detected anomalies"""
        # Check if LLM client is available
        if not self.llm_client or not self.llm_deployment_name:
            logger.info("LLM client not available, using fallback reasoning")
            return {
                "summary": self._generate_reasoning_summary(anomalies),
                "risk_factors": self._identify_risk_factors(anomalies),
                "recommendations": self._generate_llm_recommendations(anomalies, document_type),
                "confidence": 0.70,
                "note": "LLM reasoning not available, using rule-based analysis"
            }
        
        try:
            # Get risk analysis prompt
            prompt = get_risk_analysis_prompt(
                extracted_data,
                document_type,
                anomalies,
                validation_result
            )
            
            logger.info("Calling Azure OpenAI for risk analysis reasoning")
            
            # Call Azure OpenAI for LLM reasoning
            messages = [
                {
                    "role": "system",
                    "content": "You are an expert risk analyst for underwriting and loan processing. Provide detailed risk assessment and reasoning based on document anomalies."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            response = self.llm_client.chat.completions.create(
                model=self.llm_deployment_name,
                messages=messages,
                max_tokens=2000,
                temperature=0.3  # Lower temperature for more consistent, analytical responses
            )
            
            llm_response_text = response.choices[0].message.content
            logger.info(f"LLM reasoning received, length: {len(llm_response_text)} chars")
            
            # Try to parse JSON from response
            try:
                # Extract JSON from response (may be wrapped in markdown code blocks)
                if "```json" in llm_response_text:
                    start = llm_response_text.find("```json") + 7
                    end = llm_response_text.find("```", start)
                    json_str = llm_response_text[start:end].strip()
                elif "```" in llm_response_text:
                    start = llm_response_text.find("```") + 3
                    end = llm_response_text.find("```", start)
                    json_str = llm_response_text[start:end].strip()
                else:
                    # Try to find JSON object
                    start = llm_response_text.find("{")
                    end = llm_response_text.rfind("}") + 1
                    if start >= 0 and end > start:
                        json_str = llm_response_text[start:end]
                    else:
                        json_str = llm_response_text
                
                llm_result = json.loads(json_str)
                
                # Structure the response
                reasoning = {
                    "summary": llm_result.get("risk_assessment", {}).get("risk_score_explanation", self._generate_reasoning_summary(anomalies)),
                    "risk_factors": llm_result.get("risk_assessment", {}).get("fraud_indicators", []) + 
                                   llm_result.get("risk_assessment", {}).get("data_quality_concerns", []),
                    "recommendations": llm_result.get("recommendations", {}).get("required_actions", []),
                    "risk_assessment": llm_result.get("risk_assessment", {}),
                    "anomaly_analysis": llm_result.get("anomaly_analysis", []),
                    "decision": llm_result.get("recommendations", {}).get("decision", "REVIEW"),
                    "confidence": llm_result.get("confidence", 0.85),
                    "tokens_used": response.usage.total_tokens if hasattr(response, 'usage') else None
                }
                
                logger.info(f"LLM reasoning parsed successfully, confidence: {reasoning.get('confidence')}")
                return reasoning
                
            except json.JSONDecodeError:
                # If JSON parsing fails, use structured fallback with LLM text
                logger.warning("Failed to parse LLM JSON response, using fallback")
                reasoning = {
                    "summary": llm_response_text[:500] if len(llm_response_text) > 500 else llm_response_text,
                    "risk_factors": self._identify_risk_factors(anomalies),
                    "recommendations": self._generate_llm_recommendations(anomalies, document_type),
                    "raw_llm_response": llm_response_text,
                    "confidence": 0.75
                }
                return reasoning
            
        except Exception as e:
            logger.error(f"LLM reasoning failed: {e}", exc_info=True)
            # Fallback to rule-based reasoning if LLM fails
            return {
                "summary": self._generate_reasoning_summary(anomalies),
                "risk_factors": self._identify_risk_factors(anomalies),
                "recommendations": self._generate_llm_recommendations(anomalies, document_type),
                "confidence": 0.70,
                "error": f"LLM call failed, using fallback: {str(e)}"
            }
    
    def _generate_reasoning_summary(self, anomalies: Dict[str, Any]) -> str:
        """Generate summary of anomalies"""
        critical_count = len(anomalies.get("critical_anomalies", []))
        high_count = len(anomalies.get("high_anomalies", []))
        
        if critical_count > 0:
            return f"Critical risk detected: {critical_count} critical anomaly(ies) found that require immediate attention."
        elif high_count > 0:
            return f"High risk detected: {high_count} high-severity anomaly(ies) found that need review."
        else:
            return "No critical anomalies detected. Document appears acceptable with minor issues."
    
    def _identify_risk_factors(self, anomalies: Dict[str, Any]) -> List[str]:
        """Identify key risk factors from anomalies"""
        risk_factors = []
        
        for anomaly in anomalies.get("critical_anomalies", []):
            risk_factors.append(f"CRITICAL: {anomaly.get('reason', 'Unknown issue')}")
        
        for anomaly in anomalies.get("high_anomalies", [])[:5]:  # Top 5
            risk_factors.append(f"HIGH: {anomaly.get('reason', 'Unknown issue')}")
        
        return risk_factors
    
    def _generate_llm_recommendations(
        self,
        anomalies: Dict[str, Any],
        document_type: DocumentType
    ) -> List[str]:
        """Generate recommendations based on anomalies"""
        recommendations = []
        
        if anomalies.get("critical_anomalies"):
            recommendations.append("REJECT: Document contains critical anomalies that indicate potential fraud or data quality issues.")
            recommendations.append("ACTION REQUIRED: Manual review by senior underwriter recommended.")
        
        if anomalies.get("high_anomalies"):
            recommendations.append("REVIEW: Document requires detailed manual verification.")
            recommendations.append("VERIFY: Cross-check with original physical document.")
        
        if not anomalies.get("critical_anomalies") and not anomalies.get("high_anomalies"):
            recommendations.append("ACCEPT: Document appears acceptable for processing.")
        
        return recommendations
    
    def _calculate_risk_score(
        self,
        anomalies: Dict[str, Any],
        validation_result: Dict[str, Any]
    ) -> float:
        """Calculate overall risk score (0-100)"""
        try:
            base_score = 0.0
            
            # Ensure anomalies is a dict
            if not isinstance(anomalies, dict):
                logger.warning(f"Anomalies is not a dict, using empty dict. Got: {type(anomalies)}")
                anomalies = {}
            
            # Ensure validation_result is a dict
            if not isinstance(validation_result, dict):
                logger.warning(f"Validation result is not a dict, using defaults. Got: {type(validation_result)}")
                validation_result = {"quality_score": 100}
            
            # Get anomaly lists, ensuring they are lists
            critical_anomalies = anomalies.get("critical_anomalies", [])
            high_anomalies = anomalies.get("high_anomalies", [])
            medium_anomalies = anomalies.get("medium_anomalies", [])
            low_anomalies = anomalies.get("low_anomalies", [])
            
            # Ensure all are lists
            if not isinstance(critical_anomalies, list):
                critical_anomalies = []
            if not isinstance(high_anomalies, list):
                high_anomalies = []
            if not isinstance(medium_anomalies, list):
                medium_anomalies = []
            if not isinstance(low_anomalies, list):
                low_anomalies = []
            
            # Additive risk calculation: Each flag adds points based on its severity
            # Points are designed so that flags naturally reach appropriate risk thresholds
            # Formula: Sum of (flag_count × points_per_flag) + quality_penalty
            
            # Critical anomalies: 60 points each
            # 1 critical = 60, with quality penalty (10-20) = 70-80 (CRITICAL threshold)
            # 2 critical = 120 (capped at 100), 3+ = 100 (capped)
            critical_points = len(critical_anomalies) * 60.0
            base_score += critical_points
            
            # High anomalies: 30 points each
            # 1 high = 30, 2 high = 60 (HIGH threshold), 3+ = 90+ (approaching CRITICAL)
            high_points = len(high_anomalies) * 30.0
            base_score += high_points
            
            # Medium anomalies: 10 points each
            # 1 medium = 10, 3 medium = 30 (MEDIUM threshold), 4+ = 40+ (approaching HIGH)
            medium_points = len(medium_anomalies) * 10.0
            base_score += medium_points
            
            # Low anomalies: 2 points each
            # Low severity flags contribute minimally
            low_points = len(low_anomalies) * 2.0
            base_score += low_points
            
            # Factor in validation quality
            quality_score = validation_result.get("quality_score", 100)
            
            # Ensure quality_score is a valid number
            try:
                quality_score = float(quality_score)
                # Clamp quality_score to valid range (0-100)
                quality_score = max(0.0, min(100.0, quality_score))
            except (ValueError, TypeError):
                logger.warning(f"Invalid quality_score: {quality_score}, using default 100")
                quality_score = 100.0
            
            # Quality penalty: lower quality = higher risk
            # Formula: (100 - quality_score) * 0.2
            # This means:
            # - quality_score = 100 → penalty = 0
            # - quality_score = 50 → penalty = 10
            # - quality_score = 0 → penalty = 20
            quality_penalty = (100.0 - quality_score) * 0.2
            base_score += quality_penalty
            
            # Cap at 100 and ensure it's a float
            final_score = min(100.0, max(0.0, float(base_score)))
            
            logger.debug(
                f"Risk score calculation (additive): "
                f"critical={len(critical_anomalies)}×60={critical_points:.1f}, "
                f"high={len(high_anomalies)}×30={high_points:.1f}, "
                f"medium={len(medium_anomalies)}×10={medium_points:.1f}, "
                f"low={len(low_anomalies)}×2={low_points:.1f}, "
                f"quality_penalty={quality_penalty:.2f} (quality_score={quality_score}), "
                f"total={final_score:.2f}"
            )
            
            return final_score
            
        except Exception as e:
            logger.error(f"Error calculating risk score: {e}", exc_info=True)
            # Return a safe default score if calculation fails
            return 50.0
    
    def _get_risk_level(self, risk_score: float) -> str:
        """Get risk level from score"""
        try:
            # Ensure risk_score is a valid number
            risk_score = float(risk_score)
            
            # Clamp to valid range
            risk_score = max(0.0, min(100.0, risk_score))
            
            # Determine risk level based on thresholds
            if risk_score >= self.risk_thresholds["critical"]:
                return "CRITICAL"
            elif risk_score >= self.risk_thresholds["high"]:
                return "HIGH"
            elif risk_score >= self.risk_thresholds["medium"]:
                return "MEDIUM"
            else:
                return "LOW"
        except (ValueError, TypeError) as e:
            logger.error(f"Invalid risk_score for level calculation: {risk_score}, error: {e}")
            # Return MEDIUM as a safe default
            return "MEDIUM"
    
    def _generate_recommendations(
        self,
        anomalies: Dict[str, Any],
        risk_score: float,
        llm_reasoning: Optional[Dict[str, Any]]
    ) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        risk_level = self._get_risk_level(risk_score)
        
        if risk_level == "CRITICAL":
            recommendations.append("IMMEDIATE ACTION: Document should be rejected or flagged for fraud investigation")
            recommendations.append("ESCALATE: Notify fraud prevention team")
        elif risk_level == "HIGH":
            recommendations.append("MANUAL REVIEW: Document requires detailed manual verification")
            recommendations.append("VERIFY: Request additional documentation")
        elif risk_level == "MEDIUM":
            recommendations.append("REVIEW: Document should be reviewed by underwriter")
            recommendations.append("CLARIFY: Request clarification on identified issues")
        else:
            recommendations.append("PROCEED: Document appears acceptable for standard processing")
        
        # Add LLM recommendations if available
        if llm_reasoning and llm_reasoning.get("recommendations"):
            recommendations.extend(llm_reasoning["recommendations"])
        
        return recommendations
    
    # Helper methods
    def _is_sequential(self, value: str) -> bool:
        """Check if string contains sequential pattern"""
        if len(value) < 3:
            return False
        # Check for ascending sequence
        for i in range(len(value) - 2):
            try:
                if int(value[i+1]) == int(value[i]) + 1 and int(value[i+2]) == int(value[i+1]) + 1:
                    return True
            except:
                continue
        return False
    
    def _names_too_similar(self, name1: str, name2: str) -> bool:
        """Check if two names are suspiciously similar"""
        name1_words = set(name1.lower().split())
        name2_words = set(name2.lower().split())
        # If more than 50% words match, consider suspicious
        if len(name1_words) > 0 and len(name2_words) > 0:
            overlap = len(name1_words & name2_words)
            similarity = overlap / max(len(name1_words), len(name2_words))
            return similarity > 0.5
        return False
    
    def _names_match(self, name1: str, name2: str) -> bool:
        """Check if two names match (normalized)"""
        def normalize_name(name: str) -> str:
            return re.sub(r'[^a-zA-Z\s]', '', name.lower()).strip()
        
        return normalize_name(name1) == normalize_name(name2)
    
    def _dates_match(self, date1: str, date2: str) -> bool:
        """Check if two dates match"""
        try:
            formats = ["%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"]
            for fmt in formats:
                try:
                    d1 = datetime.strptime(str(date1).strip(), fmt)
                    d2 = datetime.strptime(str(date2).strip(), fmt)
                    return d1.date() == d2.date()
                except:
                    continue
            return False
        except:
            return False
    
    def _extract_name(self, data: Dict[str, Any], document_type: DocumentType) -> Optional[str]:
        """Extract name from document data"""
        name_fields = ["name", "employee_name", "consumer_name", "account_holder_name"]
        for field in name_fields:
            if data.get(field):
                return data[field]
        return None

# Create singleton instance
risk_analysis_service = RiskAnalysisService()

