"""
Structured Data Extraction Service
"""
from typing import Dict, Any, Optional
from app.models.document import DocumentType
from app.services.ocr_service import ocr_service
from app.prompts.extraction_prompts import get_extraction_prompt
from app.core.config import settings
from openai import AzureOpenAI
import json
import logging
import re

logger = logging.getLogger(__name__)

class ExtractionService:
    """Structured data extraction service"""
    
    async def extract_structured_data(
        self,
        file_path: str,
        document_type: DocumentType,
        ocr_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract structured data from document
        
        Args:
            file_path: Path to document
            document_type: Classified document type
            ocr_text: Optional pre-extracted OCR text
        
        Returns:
            Extracted structured data with confidence scores
        """
        try:
            # Get extraction prompt for document type
            prompt = get_extraction_prompt(document_type)
            
            # OPTIMIZATION: Use text-based extraction if OCR text is available
            # This avoids redundant image processing and API calls
            if ocr_text and len(ocr_text.strip()) > 10:
                logger.info("Using text-based extraction (faster, no image processing)")
                try:
                    extraction_result = await self._extract_from_text(ocr_text, prompt)
                except Exception as text_extraction_error:
                    logger.warning(f"Text-based extraction failed: {text_extraction_error}, falling back to image-based extraction")
                    # Fallback to image-based extraction if text-based fails
                    extraction_result = await ocr_service.extract_text(
                        file_path,
                        prompt=prompt
                    )
            else:
                # Fallback to image-based extraction if OCR text not available
                logger.info("OCR text not available or insufficient, using image-based extraction")
                extraction_result = await ocr_service.extract_text(
                    file_path,
                    prompt=prompt
                )
            
            # Parse JSON from response
            extracted_text = extraction_result["text"]
            structured_data = self._parse_extraction_response(extracted_text)
            
            # Normalize data structure (flatten nested structures for specific document types)
            structured_data = self._normalize_extracted_data(
                structured_data,
                document_type
            )
            
            # Post-process bank statement transactions to fix credit/debit misclassifications
            if document_type == DocumentType.BANK_STATEMENT:
                structured_data = self._fix_bank_statement_transactions(structured_data)
            
            # Calculate confidence scores
            confidence_scores = self._calculate_confidence_scores(
                structured_data,
                document_type
            )
            
            return {
                "extracted_fields": structured_data,
                "confidence_scores": confidence_scores,
                "raw_response": extracted_text
            }
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            raise Exception(f"Data extraction failed: {str(e)}")
    
    def _fix_bank_statement_transactions(self, structured_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Post-process bank statement transactions to fix credit/debit misclassifications.
        OCR sometimes incorrectly classifies credits as debits (e.g., salary as debit).
        """
        if not structured_data.get("transactions"):
            logger.info("No transactions found in structured_data, skipping post-processing")
            return structured_data
        
        transactions = structured_data["transactions"]
        logger.info(f"Post-processing {len(transactions)} bank statement transactions")
        fixed_count = 0
        
        # Keywords that indicate CREDIT transactions (money coming IN)
        CREDIT_KEYWORDS = [
            "SALARY", "SAL", "DEPOSIT", "CREDIT", "NEFT", "IMPS", "RTGS", 
            "INTEREST", "REFUND", "REVERSAL", "CREDIT CARD PAYMENT RECEIVED"
        ]
        
        # Keywords that indicate DEBIT transactions (money going OUT)
        DEBIT_KEYWORDS = [
            "EMI", "LOAN", "WITHDRAWAL", "WDL", "PAYMENT", "UPI", "ATM", 
            "DEBIT", "CHARGE", "FEE", "PENALTY", "NACH", "AUTO DEBIT"
        ]
        
        for txn in transactions:
            if not isinstance(txn, dict):
                continue
            
            description = str(txn.get("description", "")).upper()
            debit_val = txn.get("debit")
            credit_val = txn.get("credit")
            txn_type = txn.get("type", "").upper()
            
            # Parse amounts (handle both string and numeric values)
            try:
                debit_amount = float(debit_val) if debit_val and str(debit_val).lower() not in ["null", "none", ""] else 0
            except (ValueError, TypeError):
                debit_amount = 0
            
            try:
                credit_amount = float(credit_val) if credit_val and str(credit_val).lower() not in ["null", "none", ""] else 0
            except (ValueError, TypeError):
                credit_amount = 0
            
            # Check if description indicates credit but transaction is marked as debit
            is_credit_by_desc = any(keyword in description for keyword in CREDIT_KEYWORDS)
            is_debit_by_desc = any(keyword in description for keyword in DEBIT_KEYWORDS)
            
            # Fix: If description says CREDIT (e.g., SALARY, DEPOSIT) but has debit amount
            if is_credit_by_desc and not is_debit_by_desc:
                if debit_amount > 0 and credit_amount == 0:
                    # Swap: debit should be credit
                    logger.warning(f"Fixing misclassified CREDIT transaction: {description} (was debit={debit_amount})")
                    print(f"POST-PROCESSING FIX: {description} - Swapping debit={debit_val} to credit", flush=True)
                    txn["credit"] = debit_val
                    txn["debit"] = None
                    txn["type"] = "CREDIT"
                    fixed_count += 1
                elif txn_type == "DEBIT" and debit_amount > 0 and credit_amount == 0:
                    # Type is wrong, swap amounts and fix type
                    logger.warning(f"Fixing transaction type and amounts: {description} (was DEBIT with debit={debit_amount}, should be CREDIT)")
                    print(f"POST-PROCESSING FIX: {description} - Swapping debit={debit_val} to credit, type DEBIT->CREDIT", flush=True)
                    txn["credit"] = debit_val
                    txn["debit"] = None
                    txn["type"] = "CREDIT"
                    fixed_count += 1
            
            # Fix: If description says DEBIT (e.g., EMI, PAYMENT) but has credit amount
            elif is_debit_by_desc and not is_credit_by_desc:
                if credit_amount > 0 and debit_amount == 0:
                    # Swap: credit should be debit
                    logger.warning(f"Fixing misclassified DEBIT transaction: {description} (was credit={credit_amount})")
                    txn["debit"] = credit_val
                    txn["credit"] = None
                    txn["type"] = "DEBIT"
                    fixed_count += 1
                elif txn_type == "CREDIT" and debit_amount == 0:
                    # Type is wrong, fix it
                    logger.warning(f"Fixing transaction type: {description} (was CREDIT, should be DEBIT)")
                    txn["type"] = "DEBIT"
                    fixed_count += 1
        
        if fixed_count > 0:
            logger.info(f"✓ Fixed {fixed_count} misclassified bank statement transactions")
            print(f"POST-PROCESSING SUMMARY: Fixed {fixed_count} out of {len(transactions)} transactions", flush=True)
        else:
            logger.info(f"No transactions needed fixing ({len(transactions)} transactions checked)")
            print(f"POST-PROCESSING SUMMARY: No fixes needed for {len(transactions)} transactions", flush=True)
        
        return structured_data
    
    async def _extract_from_text(self, ocr_text: str, prompt: str) -> Dict[str, Any]:
        """
        Extract structured data using only text (faster than image-based extraction)
        This avoids the overhead of image processing when OCR text is already available.
        
        Args:
            ocr_text: Pre-extracted OCR text from the document
            prompt: Extraction prompt for the document type
        
        Returns:
            Dictionary with extracted text and metadata (same format as ocr_service.extract_text)
        """
        try:
            client = AzureOpenAI(
                api_key=settings.AZURE_OPENAI_API_KEY,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
            )
            
            # Combine extraction prompt with OCR text
            # The prompt should instruct the model to extract structured data from the provided text
            full_prompt = f"""{prompt}

Extracted OCR Text from Document:
{ocr_text}

Please extract the structured data from the OCR text above and return it as JSON."""
            
            logger.info(f"Calling Azure OpenAI for text-based extraction (OCR text length: {len(ocr_text)} chars)")
            
            response = client.chat.completions.create(
                model=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=[
                    {"role": "user", "content": full_prompt}
                ],
                max_tokens=4000,  # Extraction needs more tokens than classification
                temperature=0.0,  # Deterministic for data extraction
                top_p=0.95
            )
            
            extracted_text = response.choices[0].message.content
            logger.info(f"Text-based extraction successful, extracted text length: {len(extracted_text)} chars")
            
            # Return in the same format as ocr_service.extract_text for compatibility
            return {
                "text": extracted_text,
                "model": settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                "tokens_used": response.usage.total_tokens,
                "confidence": 0.95  # Text-based extraction has high confidence
            }
            
        except Exception as e:
            logger.error(f"Text-based extraction failed: {e}", exc_info=True)
            raise Exception(f"Text-based extraction failed: {str(e)}")
    
    def _sanitize_formulas_in_json(self, json_str: str) -> str:
        """
        Sanitize JSON string by evaluating simple arithmetic expressions in numeric fields.
        This handles cases where the AI returns formulas like "53255 + 21302" instead of numbers.
        Only processes simple addition/subtraction/multiplication/division expressions.
        """
        try:
            # Pattern to match numeric fields with arithmetic expressions
            # Matches: "field": "number + number" or "field": "(number + number) - number"
            formula_pattern = r'"([^"]+)":\s*"([^"]*)"'
            
            def evaluate_simple_expression(match):
                field_name = match.group(1)
                value = match.group(2).strip()
                
                # Check if it looks like a formula (contains +, -, *, /, or parentheses)
                if any(op in value for op in ['+', '-', '*', '/']) and not value.startswith('"'):
                    try:
                        # Only evaluate if it's a simple arithmetic expression
                        # Remove spaces and check if it's safe to evaluate
                        cleaned = value.replace(' ', '')
                        # Only allow digits, operators, parentheses, and decimal points
                        if re.match(r'^[\d\+\-\*\/\(\)\.\s]+$', cleaned):
                            # Use eval with limited scope for safety
                            result = eval(cleaned, {"__builtins__": {}}, {})
                            if isinstance(result, (int, float)):
                                return f'"{field_name}": {result}'
                    except (SyntaxError, ZeroDivisionError, TypeError):
                        pass
                
                # Return original if not a formula or evaluation failed
                return match.group(0)
            
            # Replace formulas in string values
            sanitized = re.sub(formula_pattern, evaluate_simple_expression, json_str)
            
            # Also handle formulas that are not in quotes (direct numeric expressions)
            # Pattern: "field": number + number (without quotes around the expression)
            direct_formula_pattern = r'"([^"]+)":\s*([\d\s\+\-\*\/\(\)]+)(?=,|\s*})'
            
            def evaluate_direct_formula(match):
                field_name = match.group(1)
                expression = match.group(2).strip()
                
                # Check if it's a formula (contains operators)
                if any(op in expression for op in ['+', '-', '*', '/']):
                    try:
                        cleaned = expression.replace(' ', '')
                        if re.match(r'^[\d\+\-\*\/\(\)\.]+$', cleaned):
                            result = eval(cleaned, {"__builtins__": {}}, {})
                            if isinstance(result, (int, float)):
                                return f'"{field_name}": {result}'
                    except (SyntaxError, ZeroDivisionError, TypeError):
                        pass
                
                return match.group(0)
            
            sanitized = re.sub(direct_formula_pattern, evaluate_direct_formula, sanitized)
            
            return sanitized
            
        except Exception as e:
            logger.warning(f"Error sanitizing formulas in JSON: {e}")
            return json_str  # Return original on error
    
    def _parse_extraction_response(self, response_text: str) -> Dict[str, Any]:
        """Parse JSON from AI response"""
        if not response_text or not isinstance(response_text, str):
            logger.warning("Empty or invalid response text")
            return {"raw_text": response_text or ""}
        
        try:
            # Try to extract JSON from response
            # Look for JSON code blocks
            json_str = None
            if "```json" in response_text:
                start = response_text.find("```json") + 7
                end = response_text.find("```", start)
                if end > start:
                    json_str = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.find("```") + 3
                end = response_text.find("```", start)
                if end > start:
                    json_str = response_text[start:end].strip()
            else:
                # Try to find JSON object
                start = response_text.find("{")
                end = response_text.rfind("}") + 1
                if start >= 0 and end > start:
                    json_str = response_text[start:end]
            
            # If we found a JSON string, try to parse it
            if json_str:
                try:
                    parsed = json.loads(json_str)
                    
                    # If parsing succeeded but result is a string, try parsing again (nested JSON)
                    if isinstance(parsed, str):
                        try:
                            nested_parsed = json.loads(parsed)
                            if isinstance(nested_parsed, dict):
                                return nested_parsed
                        except (json.JSONDecodeError, TypeError):
                            pass
                    
                    return parsed
                except json.JSONDecodeError:
                    # If initial parse fails, try sanitizing formulas and parsing again
                    logger.info("Initial JSON parse failed, attempting to sanitize formulas")
                    sanitized_json = self._sanitize_formulas_in_json(json_str)
                    try:
                        parsed = json.loads(sanitized_json)
                        logger.info("Successfully parsed JSON after sanitizing formulas")
                        return parsed
                    except json.JSONDecodeError:
                        # If sanitization didn't help, continue to fallback logic below
                        pass
            
            # If no JSON structure found, try parsing the entire text
            try:
                return json.loads(response_text.strip())
            except json.JSONDecodeError:
                # Try sanitizing the entire response
                sanitized = self._sanitize_formulas_in_json(response_text.strip())
                try:
                    return json.loads(sanitized)
                except json.JSONDecodeError:
                    pass
            
        except json.JSONDecodeError as e:
            # If JSON parsing fails, try to extract any partial JSON structure
            logger.warning(f"Failed to parse JSON: {e}")
            
            # Try to find and extract any valid JSON objects within the text using regex
            json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
            matches = re.findall(json_pattern, response_text, re.DOTALL)
            
            if matches:
                # Try the longest match first (most likely to be complete)
                for match in sorted(matches, key=len, reverse=True):
                    try:
                        parsed = json.loads(match)
                        if isinstance(parsed, dict) and len(parsed) > 0:
                            logger.info(f"Successfully parsed partial JSON with {len(parsed)} fields")
                            return parsed
                    except json.JSONDecodeError:
                        # Try sanitizing this match
                        try:
                            sanitized_match = self._sanitize_formulas_in_json(match)
                            parsed = json.loads(sanitized_match)
                            if isinstance(parsed, dict) and len(parsed) > 0:
                                logger.info(f"Successfully parsed partial JSON after sanitizing formulas")
                                return parsed
                        except json.JSONDecodeError:
                            continue
            
            # Last resort: return as raw_text
            logger.error(f"Could not parse JSON from response, returning as raw_text. Response length: {len(response_text)}")
            return {"raw_text": response_text}
    
    def _normalize_extracted_data(
        self,
        extracted_data: Dict[str, Any],
        document_type: DocumentType
    ) -> Dict[str, Any]:
        """
        Normalize extracted data structure
        Flattens nested structures for all document types to prevent [object Object] issues
        """
        normalized = extracted_data.copy()
        
        # Clean string fields: remove trailing commas, periods, and extra whitespace
        def clean_string(value: Any) -> Any:
            if isinstance(value, str):
                # Remove trailing commas, periods, and whitespace
                cleaned = value.rstrip(',.').strip()
                return cleaned
            return value
        
        # Recursively clean all string values in the dictionary
        def clean_dict(data: Dict[str, Any]) -> Dict[str, Any]:
            cleaned = {}
            for key, value in data.items():
                if isinstance(value, str):
                    cleaned[key] = clean_string(value)
                elif isinstance(value, dict):
                    cleaned[key] = clean_dict(value)
                elif isinstance(value, list):
                    cleaned[key] = [clean_string(item) if isinstance(item, str) else item for item in value]
                else:
                    cleaned[key] = value
            return cleaned
        
        normalized = clean_dict(normalized)
        
        # Document-specific normalization
        if document_type == DocumentType.PAYSLIP:
            # Flatten salary object if present
            if "salary" in normalized and isinstance(normalized["salary"], dict):
                salary_data = normalized.pop("salary")
                for key, value in salary_data.items():
                    if key not in normalized:  # Don't overwrite existing top-level fields
                        normalized[key] = value
            
            # Flatten optional_fields object if present
            if "optional_fields" in normalized and isinstance(normalized["optional_fields"], dict):
                optional_data = normalized.pop("optional_fields")
                for key, value in optional_data.items():
                    if key not in normalized:  # Don't overwrite existing top-level fields
                        normalized[key] = value
            
            # Consolidate allowances: If separate fields exist, combine them into an allowances object
            allowance_fields = ["transport", "medical", "other", "conveyance", "special_allowance", 
                              "children_education_allowance", "lta", "medical_allowance"]
            allowances_dict = {}
            fields_to_remove = []
            
            # Start with existing allowances object if present
            if "allowances" in normalized and isinstance(normalized["allowances"], dict):
                allowances_dict = normalized["allowances"].copy()
            
            # Collect separate allowance fields and merge into object
            for field in allowance_fields:
                if field in normalized and normalized[field] is not None:
                    # Use field name as key, but normalize some names
                    key = field
                    if field == "medical_allowance":
                        key = "medical"
                    # Only add if not already in allowances object
                    if key not in allowances_dict:
                        allowances_dict[key] = normalized[field]
                        fields_to_remove.append(field)
            
            # Update or create allowances object
            if allowances_dict:
                normalized["allowances"] = allowances_dict
                # Remove individual allowance fields
                for field in fields_to_remove:
                    normalized.pop(field, None)
            
            # Consolidate deductions: If separate fields exist, combine them into a deductions object
            deduction_fields = ["pf", "professional_tax", "tds", "esi", "income_tax"]
            deductions_dict = {}
            deduction_fields_to_remove = []
            
            # Start with existing deductions object if present
            if "deductions" in normalized and isinstance(normalized["deductions"], dict):
                deductions_dict = normalized["deductions"].copy()
            
            # Collect separate deduction fields and merge into object
            for field in deduction_fields:
                if field in normalized and normalized[field] is not None:
                    # Only add if not already in deductions object
                    if field not in deductions_dict:
                        deductions_dict[field] = normalized[field]
                        deduction_fields_to_remove.append(field)
            
            # Update or create deductions object
            if deductions_dict:
                normalized["deductions"] = deductions_dict
                # Remove individual deduction fields
                for field in deduction_fields_to_remove:
                    normalized.pop(field, None)
        
        # Generic normalization: Flatten common nested structures that appear across document types
        # These are often returned by the generic prompt or when AI doesn't follow structure exactly
        common_nested_keys = [
            "key_identifiers", "names", "dates", "financial_amounts", 
            "addresses", "structured_data", "optional_fields", "metadata",
            "personal_info", "contact_info", "identification", "financial_info"
        ]
        
        for key in common_nested_keys:
            if key in normalized and isinstance(normalized[key], dict):
                nested_data = normalized.pop(key)
                for nested_key, nested_value in nested_data.items():
                    # Use a more descriptive key if it doesn't conflict
                    final_key = nested_key if nested_key not in normalized else f"{key}_{nested_key}"
                    normalized[final_key] = nested_value
        
        # Recursively flatten any remaining nested dictionaries (one level deep)
        # This catches any other unexpected nested structures
        keys_to_check = list(normalized.keys())
        for key in keys_to_check:
            value = normalized[key]
            if isinstance(value, dict) and key not in common_nested_keys:
                # Only flatten if it's a simple object (not an array of objects, etc.)
                # Check if it looks like a data container (has string keys, not numeric)
                if all(isinstance(k, str) for k in value.keys()):
                    nested_data = normalized.pop(key)
                    for nested_key, nested_value in nested_data.items():
                        final_key = nested_key if nested_key not in normalized else f"{key}_{nested_key}"
                        normalized[final_key] = nested_value
        
        return normalized
    
    def _calculate_confidence_scores(
        self,
        extracted_data: Dict[str, Any],
        document_type: DocumentType
    ) -> Dict[str, float]:
        """Calculate confidence scores for extracted fields"""
        confidence_scores = {}
        
        for field, value in extracted_data.items():
            if value is None or value == "":
                confidence_scores[field] = 0.0
            elif isinstance(value, str):
                # Higher confidence for longer, structured values
                if len(value) > 5:
                    confidence_scores[field] = 0.85
                else:
                    confidence_scores[field] = 0.70
            elif isinstance(value, (int, float)):
                confidence_scores[field] = 0.90
            elif isinstance(value, dict):
                # Recursive confidence for nested objects
                confidence_scores[field] = 0.80
            else:
                confidence_scores[field] = 0.75
        
        return confidence_scores

extraction_service = ExtractionService()






