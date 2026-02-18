"""
OCR and Extraction API Endpoints
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.services.ocr_service import ocr_service
from app.services.extraction_service import extraction_service
from app.services.validation_service import validation_service
from app.services.classification_service import classification_service
from app.services.user_aggregation_service import user_aggregation_service
from app.services.risk_analysis_service import risk_analysis_service
from app.models.document import DocumentType, DocumentStatus
from app.core.database import get_database
from datetime import datetime, timezone
import logging
import asyncio
import re

logger = logging.getLogger(__name__)

def _is_valid_ocr_text(text: str) -> bool:
    """
    Check if OCR text is actual extracted text, not an error message
    
    Args:
        text: OCR text to validate
        
    Returns:
        True if text appears to be valid OCR content, False otherwise
    """
    if not text or len(text) < 10:
        return False
    
    # Common error messages from AI models that indicate OCR failure
    error_phrases = [
        "i'm unable to extract",
        "unable to extract text",
        "i cannot extract",
        "i don't have the ability",
        "i cannot see",
        "i'm not able to",
        "please provide",
        "please describe",
        "i'm unable to",
        "cannot extract text",
        "unable to process",
        "i cannot process"
    ]
    
    text_lower = text.lower()
    # If it contains error phrases, it's not valid OCR
    if any(phrase in text_lower for phrase in error_phrases):
        logger.warning(f"OCR text contains error message, marking as invalid")
        return False
    
    # Valid OCR should contain some alphanumeric content
    if not re.search(r'[A-Za-z0-9]', text):
        logger.warning(f"OCR text contains no alphanumeric characters, marking as invalid")
        return False
    
    return True

router = APIRouter()

class OCRExtractRequest(BaseModel):
    document_id: str
    document_type: Optional[str] = None
    skip_classification: bool = False

class OCRExtractResponse(BaseModel):
    document_id: str
    document_type: str
    extracted_data: Dict[str, Any]
    quality_score: float
    validation_warnings: list
    confidence_scores: Dict[str, float]
    message: str

@router.post("/", response_model=OCRExtractResponse)
async def ocr_and_extract(request: OCRExtractRequest, background_tasks: BackgroundTasks):
    """
    Perform OCR and extract structured data from document
    
    - **document_id**: Document identifier
    - **document_type**: Optional document type (if already classified)
    - **skip_classification**: Skip classification step
    """
    try:
        # Get document from database
        db = await get_database()
        doc = await db.documents.find_one({"document_id": request.document_id})
        
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Update status to PROCESSING
        await db.documents.update_one(
            {"document_id": request.document_id},
            {"$set": {"status": DocumentStatus.PROCESSING.value}}
        )
        
        # OPTIMIZATION 1: Extract OCR text ONCE and reuse it
        # Check if OCR text already exists and is valid (both length and content quality)
        ocr_text = doc.get("ocr_text")
        is_valid_ocr = _is_valid_ocr_text(ocr_text) if ocr_text else False
        
        if not is_valid_ocr:
            logger.info(f"OCR text invalid or contains error message, extracting OCR text for document {request.document_id}")
            ocr_result = await ocr_service.extract_text(doc["file_path"])
            ocr_text = ocr_result["text"]
            
            # Validate the newly extracted OCR text
            if not _is_valid_ocr_text(ocr_text):
                logger.warning(f"Newly extracted OCR text also appears invalid, but proceeding with extraction")
            
            # Update document with OCR text immediately
            await db.documents.update_one(
                {"document_id": request.document_id},
                {"$set": {"ocr_text": ocr_text}}
            )
        else:
            logger.info(f"Reusing existing valid OCR text for document {request.document_id}")
        
        # Step 1: Determine document type - ALWAYS CLASSIFY (don't skip)
        document_type = None
        
        # If document_type is explicitly provided in request, use it (skip classification)
        if request.document_type:
            try:
                document_type = DocumentType(request.document_type)
                logger.info(f"Using document_type from request: {document_type.value} for document {request.document_id}, skipping classification")
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid document type: {request.document_type}")
        
        # ALWAYS CLASSIFY to verify document type (unless explicitly skipped or document_type provided in request)
        # This ensures we verify the document type even if expected_document_type was provided
        if not document_type and not request.skip_classification:
            # OPTIMIZATION: Pass existing OCR text to classification to avoid duplicate extraction
            logger.info(f"Classifying document {request.document_id} using existing OCR text")
            classification_result = await classification_service.classify_document(
                doc["file_path"],
                ocr_text=ocr_text  # Reuse OCR text
            )
            document_type = classification_result["document_type"]
            
            # Batch update: classification + ensure OCR text is saved
            update_data = {"document_type": document_type.value}
            if not doc.get("ocr_text") or len(doc.get("ocr_text", "")) < 10:
                update_data["ocr_text"] = ocr_text
            
            await db.documents.update_one(
                {"document_id": request.document_id},
                {"$set": update_data}
            )
        elif not document_type and doc.get("document_type"):
            # Fallback: If document already has a type and we didn't classify, use it
            document_type = DocumentType(doc["document_type"])
            logger.info(f"Using existing document_type: {document_type.value} for document {request.document_id}")
        
        # Validate document type if expected type was provided
        type_mismatch_error = None
        if doc.get("expected_document_type") and document_type:
            try:
                expected_type = DocumentType(doc["expected_document_type"])
                if document_type != expected_type:
                    type_mismatch_error = (
                        f"Document type mismatch: Expected {expected_type.value}, "
                        f"but classified as {document_type.value}. "
                        f"Please upload the correct document type."
                    )
                    logger.error(f"Document type mismatch for {request.document_id}: {type_mismatch_error}")
            except ValueError:
                # Invalid expected_document_type, ignore
                pass

        # Handle UNKNOWN document type
        if not document_type or document_type == DocumentType.UNKNOWN:
            # If expected_document_type was provided, treat UNKNOWN as a mismatch error
            # This allows the process to continue and show the error to the user
            if doc.get("expected_document_type"):
                try:
                    expected_type = DocumentType(doc["expected_document_type"])
                    type_mismatch_error = (
                        f"Document type mismatch: Expected {expected_type.value}, "
                        f"but could not classify the document (classified as UNKNOWN). "
                        f"Please upload the correct document type."
                    )
                    logger.error(f"Document type mismatch for {request.document_id}: {type_mismatch_error}")
                    # Use the expected type for processing, but flag the error
                    document_type = expected_type
                except ValueError:
                    # Invalid expected_document_type, raise error
                    raise HTTPException(
                        status_code=400,
                        detail="Document type could not be determined. Please specify document_type."
                    )
            else:
                # No expected type provided, raise error
                raise HTTPException(
                    status_code=400,
                    detail="Document type could not be determined. Please specify document_type."
                )
        
        # Step 2: Extract structured data (reuse OCR text)
        extraction_result = await extraction_service.extract_structured_data(
            doc["file_path"],
            document_type,
            ocr_text=ocr_text  # Reuse OCR text
        )
        
        # Step 4: Get user_id from the document (needed for validation)
        user_id = doc.get("user_id")
        
        # Step 5: Validate extracted data (including customer profile validation)
        validation_result = await validation_service.validate_extracted_data(
            extraction_result["extracted_fields"],
            document_type,
            user_id=user_id,
            validate_against_profile=True
        )
        
        # Add document type mismatch error if applicable
        if type_mismatch_error:
            if not isinstance(validation_result.get("errors"), list):
                validation_result["errors"] = []
            validation_result["errors"].insert(0, type_mismatch_error)  # Add at the beginning
            # Mark validation as invalid
            validation_result["is_valid"] = False
        
        # Step 6: Prepare extraction record
        extraction_record = {
            "document_id": request.document_id,
            "user_id": user_id,
            "document_type": document_type.value,
            "extracted_fields": extraction_result["extracted_fields"],
            "confidence_scores": extraction_result["confidence_scores"],
            "extraction_timestamp": datetime.now(timezone.utc),
            "version": "1.0"
        }
        
        # Step 7: OPTIMIZATION 3 - Batch database operations (parallel execution)
        # Ensure validation_errors and validation_warnings are lists
        errors = validation_result.get("errors", [])
        warnings = validation_result.get("warnings", [])
        if not isinstance(errors, list):
            errors = []
        if not isinstance(warnings, list):
            warnings = []
        
        document_update = {
            "status": DocumentStatus.COMPLETED.value,
            "document_type": document_type.value,
            "extracted_data": extraction_result["extracted_fields"],
            "quality_score": validation_result.get("quality_score"),
            "validation_warnings": warnings,
            "validation_errors": errors,
            "has_type_mismatch": type_mismatch_error is not None,
            "processed_at": datetime.now(timezone.utc)
        }
        
        # Execute database operations in parallel
        await asyncio.gather(
            db.extraction_results.insert_one(extraction_record),
            db.documents.update_one(
                {"document_id": request.document_id},
                {"$set": document_update}
            )
        )
        
        # Step 8: Update user document aggregation (only extracted_fields and document_type)
        await user_aggregation_service.update_user_aggregation(
            user_id=user_id,
            document_id=request.document_id,
            document_type=document_type.value,
            extracted_fields=extraction_result["extracted_fields"]
        )
        
        # Step 9: OPTIMIZATION 4 - Make risk analysis asynchronous (don't block response)
        async def run_risk_analysis_async(
            document_id: str,
            user_id: str,
            document_type: DocumentType,
            extraction_result: Dict[str, Any],
            validation_result: Dict[str, Any]
        ):
            """Background task for risk analysis"""
            try:
                logger.info(f"Starting background risk analysis for document {document_id}")
                db = await get_database()
                
                # Get all user documents for cross-document analysis
                all_user_documents = None
                if user_id:
                    try:
                        all_user_documents = await user_aggregation_service.get_user_aggregation(user_id)
                        logger.debug(f"Retrieved {len(all_user_documents.get('documents', [])) if all_user_documents else 0} user documents for cross-document analysis")
                    except Exception as agg_err:
                        logger.warning(f"Could not fetch user documents for cross-document analysis: {agg_err}")
                
                # Ensure validation_result has required fields
                if not isinstance(validation_result, dict):
                    logger.error(f"Validation result is not a dict: {type(validation_result)}")
                    validation_result = {"warnings": [], "errors": [], "quality_score": 100}
                
                # Perform risk analysis
                logger.debug(f"Calling risk_analysis_service.analyze_risk for document {document_id}")
                risk_result = await risk_analysis_service.analyze_risk(
                    extracted_data=extraction_result["extracted_fields"],
                    document_type=document_type,
                    validation_result=validation_result,
                    user_id=user_id,
                    all_user_documents=all_user_documents,
                    document_id=document_id
                )
                
                logger.info(f"Risk analysis completed: score={risk_result.get('risk_score')}, level={risk_result.get('risk_level')}, anomalies={risk_result.get('anomalies', {}).get('anomaly_count', 0)}")
                
                # Get application_id from document
                doc = await db.documents.find_one({"document_id": document_id})
                application_id = doc.get("application_id") if doc else None
                
                # Save risk analysis result to database
                risk_record = {
                    "document_id": document_id,
                    "user_id": user_id,
                    "application_id": application_id,
                    "document_type": document_type.value,
                    "risk_score": risk_result["risk_score"],
                    "risk_level": risk_result["risk_level"],
                    "anomalies": risk_result["anomalies"],
                    "llm_reasoning": risk_result.get("llm_reasoning"),
                    "recommendations": risk_result["recommendations"],
                    "analysis_timestamp": risk_result["analysis_timestamp"]
                }
                
                # Store in risk_analyses collection and update document in parallel
                await asyncio.gather(
                    db.risk_analyses.insert_one(risk_record),
                    db.documents.update_one(
                        {"document_id": document_id},
                        {"$set": {
                            "risk_score": risk_result["risk_score"],
                            "risk_level": risk_result["risk_level"]
                        }}
                    )
                )
                
                logger.info(f"Background risk analysis completed: {document_id}, Risk: {risk_result['risk_level']} (Score: {risk_result['risk_score']})")
            except Exception as risk_err:
                # Log error but don't fail the extraction
                logger.error(f"Background risk analysis failed for {document_id}: {str(risk_err)}", exc_info=True)
                logger.error(f"Risk analysis error type: {type(risk_err).__name__}")
        
        # Schedule risk analysis as background task
        background_tasks.add_task(
            run_risk_analysis_async,
            request.document_id,
            user_id,
            document_type,
            extraction_result,
            validation_result
        )
        logger.info(f"Risk analysis scheduled as background task for {request.document_id}")
        
        logger.info(f"OCR and extraction completed: {request.document_id}")
        
        return OCRExtractResponse(
            document_id=request.document_id,
            document_type=document_type.value,
            extracted_data=extraction_result["extracted_fields"],
            quality_score=validation_result["quality_score"],
            validation_warnings=validation_result["warnings"],
            confidence_scores=extraction_result["confidence_scores"],
            message="OCR and extraction completed successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"OCR extraction failed: {e}")
        
        # Update status to FAILED
        try:
            db = await get_database()
            await db.documents.update_one(
                {"document_id": request.document_id},
                {"$set": {"status": DocumentStatus.FAILED.value}}
            )
        except:
            pass
        
        raise HTTPException(status_code=500, detail=f"OCR extraction failed: {str(e)}")

@router.get("/{document_id}")
async def get_extracted_data(document_id: str):
    """Get extracted data for a document"""
    try:
        db = await get_database()
        
        # Get document
        doc = await db.documents.find_one({"document_id": document_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get extraction result
        extraction = await db.extraction_results.find_one(
            {"document_id": document_id},
            sort=[("extraction_timestamp", -1)]
        )
        
        if not extraction:
            raise HTTPException(status_code=404, detail="Extraction result not found")
        
        extraction.pop("_id", None)
        extracted_data = extraction["extracted_fields"].copy()
        
        # For BANK_STATEMENT: Replace transactions from extraction_results with correct ones from bank_transaction_record
        if extraction["document_type"] == "BANK_STATEMENT" and extracted_data.get("transactions"):
            account_number = extracted_data.get("account_number")
            if account_number:
                # Get correct transactions from bank_transaction_record
                bank_txns = await db.bank_transaction_record.find(
                    {"account_number": account_number}
                ).sort("transaction_date", 1).to_list(length=None)
                
                if bank_txns:
                    # Convert bank_transaction_record format to extraction_results format
                    # Remove duplicates based on date + description + amount
                    seen_txns = set()
                    corrected_transactions = []
                    for txn in bank_txns:
                        # Create unique key to detect duplicates
                        txn_key = (
                            txn.get("transaction_date"),
                            str(txn.get("description", "")),
                            txn.get("debit_amount"),
                            txn.get("credit_amount")
                        )
                        
                        if txn_key not in seen_txns:
                            seen_txns.add(txn_key)
                            corrected_transactions.append({
                                "date": txn.get("transaction_date"),
                                "description": txn.get("description"),
                                "debit": txn.get("debit_amount"),
                                "credit": txn.get("credit_amount"),
                                "balance": txn.get("balance_after_transaction"),
                                "type": txn.get("transaction_type")
                            })
                    
                    # Replace transactions in extracted_data
                    extracted_data["transactions"] = corrected_transactions
                    logger.info(f"Replaced {len(corrected_transactions)} transactions from bank_transaction_record for document {document_id} (removed {len(bank_txns) - len(corrected_transactions)} duplicates)")
        
        return {
            "document_id": document_id,
            "user_id": doc.get("user_id"),
            "document_type": extraction["document_type"],
            "extracted_data": extracted_data,
            "confidence_scores": extraction["confidence_scores"],
            "quality_score": doc.get("quality_score"),
            "validation_warnings": doc.get("validation_warnings", []),
            "extraction_timestamp": extraction["extraction_timestamp"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get extracted data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/{user_id}/all")
async def get_user_extractions(user_id: str):
    """
    Get all extracted data for a specific user
    
    Returns all extraction results for the given user_id, grouped by document type
    """
    try:
        db = await get_database()
        
        # Get all extraction results for this user
        cursor = db.extraction_results.find({"user_id": user_id}).sort("extraction_timestamp", -1)
        extractions = await cursor.to_list(length=None)
        
        if not extractions:
            return {
                "user_id": user_id,
                "total_extractions": 0,
                "extractions_by_type": {},
                "all_extractions": []
            }
        
        # Remove _id from each extraction
        for extraction in extractions:
            extraction.pop("_id", None)
        
        # Get document details for each extraction
        all_extractions = []
        for extraction in extractions:
            doc = await db.documents.find_one({"document_id": extraction["document_id"]})
            if doc:
                doc.pop("_id", None)
                extracted_data = extraction["extracted_fields"].copy()
                
                # For BANK_STATEMENT: Replace transactions from extraction_results with correct ones from bank_transaction_record
                if extraction["document_type"] == "BANK_STATEMENT" and extracted_data.get("transactions"):
                    account_number = extracted_data.get("account_number")
                    if account_number:
                        # Get correct transactions from bank_transaction_record
                        bank_txns = await db.bank_transaction_record.find(
                            {"account_number": account_number}
                        ).sort("transaction_date", 1).to_list(length=None)
                        
                        if bank_txns:
                            # Convert bank_transaction_record format to extraction_results format
                            corrected_transactions = []
                            for txn in bank_txns:
                                corrected_transactions.append({
                                    "date": txn.get("transaction_date"),
                                    "description": txn.get("description"),
                                    "debit": txn.get("debit_amount"),
                                    "credit": txn.get("credit_amount"),
                                    "balance": txn.get("balance_after_transaction"),
                                    "type": txn.get("transaction_type")
                                })
                            
                            # Replace transactions in extracted_data
                            extracted_data["transactions"] = corrected_transactions
                            logger.info(f"Replaced {len(extracted_data.get('transactions', []))} transactions from bank_transaction_record for document {extraction['document_id']}")
                
                all_extractions.append({
                    "document_id": extraction["document_id"],
                    "user_id": user_id,
                    "document_type": extraction["document_type"],
                    "file_name": doc.get("file_name"),
                    "extracted_data": extracted_data,
                    "confidence_scores": extraction["confidence_scores"],
                    "quality_score": doc.get("quality_score"),
                    "validation_warnings": doc.get("validation_warnings", []),
                    "extraction_timestamp": extraction["extraction_timestamp"],
                    "uploaded_at": doc.get("uploaded_at")
                })
        
        # Group extractions by document type
        extractions_by_type = {}
        for extraction_data in all_extractions:
            doc_type = extraction_data["document_type"]
            if doc_type not in extractions_by_type:
                extractions_by_type[doc_type] = []
            extractions_by_type[doc_type].append(extraction_data)
        
        return {
            "user_id": user_id,
            "total_extractions": len(all_extractions),
            "extractions_by_type": extractions_by_type,
            "all_extractions": all_extractions
        }
        
    except Exception as e:
        logger.error(f"Failed to get user extractions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/application/{application_id}/all")
async def get_application_extractions(application_id: str):
    """
    Get all extracted data for a specific application
    
    Returns all extraction results for the given application_id, grouped by document type
    """
    try:
        db = await get_database()
        
        # Get all documents for this application
        cursor = db.documents.find({"application_id": application_id})
        docs = await cursor.to_list(length=None)
        
        if not docs:
            return {
                "application_id": application_id,
                "total_extractions": 0,
                "extractions_by_type": {},
                "all_extractions": []
            }
        
        # Get extraction results for all documents
        all_extractions = []
        for doc in docs:
            doc.pop("_id", None)
            extraction = await db.extraction_results.find_one(
                {"document_id": doc["document_id"]},
                sort=[("extraction_timestamp", -1)]
            )
            
            if extraction:
                extraction.pop("_id", None)
                extracted_data = extraction["extracted_fields"].copy()
                
                # For BANK_STATEMENT: Replace transactions from extraction_results with correct ones from bank_transaction_record
                if extraction["document_type"] == "BANK_STATEMENT" and extracted_data.get("transactions"):
                    account_number = extracted_data.get("account_number")
                    if account_number:
                        # Get correct transactions from bank_transaction_record
                        bank_txns = await db.bank_transaction_record.find(
                            {"account_number": account_number}
                        ).sort("transaction_date", 1).to_list(length=None)
                        
                        if bank_txns:
                            # Convert bank_transaction_record format to extraction_results format
                            # Remove duplicates based on date + description + amount
                            seen_txns = set()
                            corrected_transactions = []
                            for txn in bank_txns:
                                # Create unique key to detect duplicates
                                txn_key = (
                                    txn.get("transaction_date"),
                                    str(txn.get("description", "")),
                                    txn.get("debit_amount"),
                                    txn.get("credit_amount")
                                )
                                
                                if txn_key not in seen_txns:
                                    seen_txns.add(txn_key)
                                    corrected_transactions.append({
                                        "date": txn.get("transaction_date"),
                                        "description": txn.get("description"),
                                        "debit": txn.get("debit_amount"),
                                        "credit": txn.get("credit_amount"),
                                        "balance": txn.get("balance_after_transaction"),
                                        "type": txn.get("transaction_type")
                                    })
                            
                            # Replace transactions in extracted_data
                            extracted_data["transactions"] = corrected_transactions
                            logger.info(f"Replaced {len(corrected_transactions)} transactions from bank_transaction_record for document {doc['document_id']} (removed {len(bank_txns) - len(corrected_transactions)} duplicates)")
                
                all_extractions.append({
                    "document_id": doc["document_id"],
                    "application_id": application_id,
                    "user_id": doc.get("user_id"),
                    "document_type": extraction["document_type"],
                    "file_name": doc.get("file_name"),
                    "extracted_data": extracted_data,
                    "confidence_scores": extraction["confidence_scores"],
                    "quality_score": doc.get("quality_score"),
                    "validation_warnings": doc.get("validation_warnings", []),
                    "extraction_timestamp": extraction["extraction_timestamp"],
                    "uploaded_at": doc.get("uploaded_at")
                })
        
        # Group extractions by document type
        extractions_by_type = {}
        for extraction_data in all_extractions:
            doc_type = extraction_data["document_type"]
            if doc_type not in extractions_by_type:
                extractions_by_type[doc_type] = []
            extractions_by_type[doc_type].append(extraction_data)
        
        return {
            "application_id": application_id,
            "total_extractions": len(all_extractions),
            "extractions_by_type": extractions_by_type,
            "all_extractions": all_extractions
        }
        
    except Exception as e:
        logger.error(f"Failed to get application extractions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/{user_id}/summary")
async def get_user_extractions_summary(user_id: str):
    """
    Get summary of extracted data for a specific user
    
    Returns count and statistics of extraction results by document type
    """
    try:
        db = await get_database()
        
        # Aggregate extractions by type
        pipeline = [
            {"$match": {"user_id": user_id}},
            {"$group": {
                "_id": "$document_type",
                "count": {"$sum": 1},
                "latest_extraction": {"$max": "$extraction_timestamp"}
            }},
            {"$sort": {"count": -1}}
        ]
        
        result = await db.extraction_results.aggregate(pipeline).to_list(length=None)
        
        summary = {
            "user_id": user_id,
            "total_extractions": sum(item.get("count", 0) for item in result),
            "extractions_by_type": {}
        }
        
        for item in result:
            doc_type = item.get("_id", "UNKNOWN")
            summary["extractions_by_type"][doc_type] = {
                "count": item.get("count", 0),
                "latest_extraction": item.get("latest_extraction")
            }
        
        return summary
        
    except Exception as e:
        logger.error(f"Failed to get user extraction summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/user/{user_id}/aggregation")
async def get_user_document_aggregation(user_id: str):
    """
    Get all extracted details of a user's documents in a single JSON schema
    
    Returns the complete aggregation of all user's document extractions stored in a single document
    """
    try:
        aggregation = await user_aggregation_service.get_user_aggregation(user_id)
        
        if not aggregation:
            return {
                "user_id": user_id,
                "total_documents": 0,
                "documents": {},
                "documents_by_type": {},
                "message": "No document extractions found for this user"
            }
        
        return aggregation
        
    except Exception as e:
        logger.error(f"Failed to get user aggregation: {e}")
        raise HTTPException(status_code=500, detail=str(e))





