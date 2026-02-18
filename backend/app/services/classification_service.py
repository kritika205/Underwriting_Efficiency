"""
Document Classification Service
"""
from typing import Dict, Any, Optional
from app.models.document import DocumentType
from app.services.ocr_service import ocr_service
from app.prompts.classification_prompts import get_classification_prompt
import logging

logger = logging.getLogger(__name__)

class ClassificationService:
    """Document classification service using Azure OpenAI"""
    
    async def classify_document(
        self, 
        file_path: str,
        ocr_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Classify document type
        
        Args:
            file_path: Path to document
            ocr_text: Optional pre-extracted OCR text
        
        Returns:
            Classification result with document type and confidence
        """
        try:
            # If OCR text not provided, extract it
            if not ocr_text:
                logger.info("Extracting OCR text for classification")
                ocr_result = await ocr_service.extract_text(
                    file_path,
                    prompt="Extract all visible text from this document. Focus on document headers, titles, and key identifiers."
                )
                ocr_text = ocr_result["text"]
                logger.info(f"OCR text extracted, length: {len(ocr_text)} chars, preview: {ocr_text[:200]}...")
            
            # Get classification prompt
            prompt = get_classification_prompt(ocr_text)
            
            # OPTIMIZATION: If we have good OCR text, use text-based classification (faster)
            # Only use image-based classification if OCR text is insufficient
            if ocr_text and len(ocr_text) > 50:
                logger.info("Using text-based classification (faster)")
                classification_result = await self._classify_from_text(ocr_text, prompt)
            else:
                # Fallback to image-based classification for better accuracy
                logger.info("Using image-based classification for better accuracy")
                classification_result = await ocr_service.extract_text(
                    file_path,
                    prompt=prompt
                )
            
            # Parse classification result
            classification_text = classification_result["text"] if isinstance(classification_result, dict) else classification_result
            logger.info(f"Classification response received: {classification_text[:300]}...")
            
            document_type, confidence = self._parse_classification(classification_text)
            
            logger.info(f"Classified as: {document_type.value} with confidence: {confidence}")
            
            return {
                "document_type": document_type,
                "confidence": confidence,
                "classification_text": classification_text,
                "ocr_text": ocr_text
            }
            
        except Exception as e:
            logger.error(f"Classification failed: {e}", exc_info=True)
            return {
                "document_type": DocumentType.UNKNOWN,
                "confidence": 0.0,
                "error": str(e)
            }
    
    async def _classify_from_text(self, ocr_text: str, prompt: str) -> Dict[str, Any]:
        """
        Classify document using only text (faster than image-based classification)
        This avoids the overhead of image processing when OCR text is already available
        """
        try:
            from app.core.config import settings
            from openai import AzureOpenAI
            
            client = AzureOpenAI(
                api_key=settings.AZURE_OPENAI_API_KEY,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
            )
            
            response = client.chat.completions.create(
                model=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                max_tokens=500,  # Classification needs fewer tokens
                temperature=0.0  # More deterministic for classification
            )
            
            return {
                "text": response.choices[0].message.content,
                "model": settings.AZURE_OPENAI_DEPLOYMENT_NAME
            }
        except Exception as e:
            logger.error(f"Text-based classification failed: {e}")
            # Fallback to image-based if text-based fails
            raise
    
    def _parse_classification(self, classification_text: str) -> tuple:
        """
        Parse classification result from AI response
        
        Returns:
            Tuple of (DocumentType, confidence)
        """
        import re
        
        # Normalize the text
        text_upper = classification_text.upper()
        logger.info(f"Parsing classification from response (first 200 chars): {text_upper[:200]}")
        
        # Try to extract explicit DOCUMENT_TYPE: pattern first
        doc_type_match = re.search(r'DOCUMENT_TYPE:\s*(\w+)', text_upper)
        if doc_type_match:
            doc_type_str = doc_type_match.group(1)
            logger.info(f"Found explicit document type in response: {doc_type_str}")
            
            # Map to DocumentType enum
            explicit_mapping = {
                "AADHAAR": DocumentType.AADHAAR,
                "PAN": DocumentType.PAN,
                "PASSPORT": DocumentType.PASSPORT,
                "DRIVING_LICENSE": DocumentType.DRIVING_LICENSE,
                "DRIVING": DocumentType.DRIVING_LICENSE,
                "VOTER_ID": DocumentType.VOTER_ID,
                "VOTER": DocumentType.VOTER_ID,
                "GST_RETURN": DocumentType.GST_RETURN,
                "GST": DocumentType.GST_RETURN,
                "ITR_FORM": DocumentType.ITR_FORM,
                "ITR": DocumentType.ITR_FORM,
                "PAYSLIP": DocumentType.PAYSLIP,
                "BANK_STATEMENT": DocumentType.BANK_STATEMENT,
                "BALANCE_SHEET": DocumentType.BALANCE_SHEET,
                "SHOP_REGISTRATION": DocumentType.SHOP_REGISTRATION,
                "BUSINESS_LICENSE": DocumentType.BUSINESS_LICENSE,
                "CIBIL": DocumentType.CIBIL_SCORE_REPORT,
                "CRIF": DocumentType.CRIF,
                "EXPERIAN": DocumentType.EXPERIAN,
                "EQUIFAX": DocumentType.EQUIFAX,
                "LOAN_SANCTION_LETTER": DocumentType.LOAN_SANCTION_LETTER,
                "LOAN_SANCTION": DocumentType.LOAN_SANCTION_LETTER,
                "EMI_SCHEDULE": DocumentType.EMI_SCHEDULE,
                "LOAN_AGREEMENT": DocumentType.LOAN_AGREEMENT,
                "RENT_AGREEMENT": DocumentType.RENT_AGREEMENT,
                "RENTAL": DocumentType.RENT_AGREEMENT,
                "RENTAL_AGREEMENT": DocumentType.RENT_AGREEMENT,  
                "LEASE": DocumentType.RENT_AGREEMENT, 
                "LEASE_AGREEMENT": DocumentType.RENT_AGREEMENT, 
                "TENANCY": DocumentType.RENT_AGREEMENT,,
                "CIBIL_SCORE_REPORT": DocumentType.CIBIL_SCORE_REPORT,
                "CIBIL_SCORE": DocumentType.CIBIL_SCORE_REPORT,
                "CREDIT_SCORE": DocumentType.CIBIL_SCORE_REPORT,
                "DEALER_INVOICE": DocumentType.DEALER_INVOICE,
                "INVOICE": DocumentType.DEALER_INVOICE,
                "BUSINESS_REGISTRATION": DocumentType.BUSINESS_REGISTRATION,
                "COMPANY_REGISTRATION": DocumentType.BUSINESS_REGISTRATION,
                "LAND_RECORDS": DocumentType.LAND_RECORDS,
                "LAND_RECORD": DocumentType.LAND_RECORDS,
                "LAND": DocumentType.LAND_RECORDS,
                "MEDICAL_BILLS": DocumentType.MEDICAL_BILLS,
                "MEDICAL_BILL": DocumentType.MEDICAL_BILLS,
                "HOSPITAL": DocumentType.MEDICAL_BILLS,
                "ELECTRICITY_BILL": DocumentType.ELECTRICITY_BILL,
                "ELECTRICITY": DocumentType.ELECTRICITY_BILL,
                "WATER_BILL": DocumentType.WATER_BILL,
                "WATER": DocumentType.WATER_BILL,
                "OFFER_LETTER": DocumentType.OFFER_LETTER,
                "OFFER": DocumentType.OFFER_LETTER,
                "EMPLOYMENT_LETTER": DocumentType.OFFER_LETTER,
                "JOB_OFFER": DocumentType.OFFER_LETTER
            }
            
            if doc_type_str in explicit_mapping:
                # Try to extract confidence
                confidence = 0.9
                conf_match = re.search(r'CONFIDENCE:\s*(\d+\.?\d*)', text_upper)
                if conf_match:
                    confidence = float(conf_match.group(1))
                    if confidence > 1.0:
                        confidence = confidence / 100.0
                
                logger.info(f"Parsed document type: {explicit_mapping[doc_type_str].value}, confidence: {confidence}")
                return explicit_mapping[doc_type_str], confidence
        
        # Fallback: keyword matching
        type_mapping = {
            "AADHAAR": DocumentType.AADHAAR,
            "PAN": DocumentType.PAN,
            "PASSPORT": DocumentType.PASSPORT,
            "DRIVING": DocumentType.DRIVING_LICENSE,
            "DRIVER": DocumentType.DRIVING_LICENSE,
            "VOTER": DocumentType.VOTER_ID,
            "GST": DocumentType.GST_RETURN,
            "ITR": DocumentType.ITR_FORM,
            "INCOME TAX": DocumentType.ITR_FORM,
            "PAYSLIP": DocumentType.PAYSLIP,
            "SALARY": DocumentType.PAYSLIP,
            "BANK STATEMENT": DocumentType.BANK_STATEMENT,
            "BALANCE SHEET": DocumentType.BALANCE_SHEET,
            "SHOP REGISTRATION": DocumentType.SHOP_REGISTRATION,
            "BUSINESS LICENSE": DocumentType.BUSINESS_LICENSE,
            "CIBIL": DocumentType.CIBIL_SCORE_REPORT,
            "CRIF": DocumentType.CRIF,
            "EXPERIAN": DocumentType.EXPERIAN,
            "EQUIFAX": DocumentType.EQUIFAX,
            "LOAN SANCTION": DocumentType.LOAN_SANCTION_LETTER,
            "EMI SCHEDULE": DocumentType.EMI_SCHEDULE,
            "LOAN AGREEMENT": DocumentType.LOAN_AGREEMENT,
            "RENT AGREEMENT": DocumentType.RENT_AGREEMENT,
            "RENTAL AGREEMENT": DocumentType.RENT_AGREEMENT,
            "LEASE AGREEMENT": DocumentType.RENT_AGREEMENT,
            "TENANCY": DocumentType.RENT_AGREEMENT,
            "RENTAL": DocumentType.RENT_AGREEMENT,
            "CIBIL SCORE": DocumentType.CIBIL_SCORE_REPORT,
            "CREDIT SCORE": DocumentType.CIBIL_SCORE_REPORT,
            "DEALER INVOICE": DocumentType.DEALER_INVOICE,
            "INVOICE": DocumentType.DEALER_INVOICE,
            "BUSINESS REGISTRATION": DocumentType.BUSINESS_REGISTRATION,
            "COMPANY REGISTRATION": DocumentType.BUSINESS_REGISTRATION,
            "LAND RECORD": DocumentType.LAND_RECORDS,
            "LAND": DocumentType.LAND_RECORDS,
            "MEDICAL BILL": DocumentType.MEDICAL_BILLS,
            "HOSPITAL": DocumentType.MEDICAL_BILLS,
            "ELECTRICITY BILL": DocumentType.ELECTRICITY_BILL,
            "ELECTRICITY": DocumentType.ELECTRICITY_BILL,
            "WATER BILL": DocumentType.WATER_BILL,
            "WATER": DocumentType.WATER_BILL,
            "OFFER LETTER": DocumentType.OFFER_LETTER,
            "OFFER": DocumentType.OFFER_LETTER,
            "EMPLOYMENT LETTER": DocumentType.OFFER_LETTER,
            "JOB OFFER": DocumentType.OFFER_LETTER
        }
        
        # Find matching document type
        for keyword, doc_type in type_mapping.items():
            if keyword in text_upper:
                confidence = 0.85
                logger.info(f"Found keyword '{keyword}' in response, mapping to {doc_type.value}")
                return doc_type, confidence
        
        logger.warning(f"Could not classify document from response, returning UNKNOWN")
        return DocumentType.UNKNOWN, 0.5

classification_service = ClassificationService()


