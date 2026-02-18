"""
Script to fix credit/debit misclassifications in existing bank statement transactions
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def fix_transactions_in_extraction_results(document_id: str = None):
    """Fix credit/debit misclassifications in extraction_results"""
    try:
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        db = client[settings.MONGODB_DB_NAME]
        
        # Test connection
        await db.list_collection_names()
        logger.info("Connected to database successfully")
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")
        return
    
    try:
        # Keywords that indicate CREDIT transactions
        CREDIT_KEYWORDS = [
            "SALARY", "SAL", "DEPOSIT", "CREDIT", "NEFT", "IMPS", "RTGS", 
            "INTEREST", "REFUND", "REVERSAL"
        ]
        
        # Keywords that indicate DEBIT transactions
        DEBIT_KEYWORDS = [
            "EMI", "LOAN", "WITHDRAWAL", "WDL", "PAYMENT", "UPI", "ATM", 
            "DEBIT", "CHARGE", "FEE", "PENALTY", "NACH", "AUTO DEBIT"
        ]
        
        # Find all bank statement extraction results
        query = {"document_type": "BANK_STATEMENT"}
        if document_id:
            query["document_id"] = document_id
        
        extractions = await db.extraction_results.find(query).to_list(length=None)
        logger.info(f"Found {len(extractions)} bank statement extraction(s) to check")
        
        total_fixed = 0
        for extraction in extractions:
            doc_id = extraction.get("document_id")
            extracted_fields = extraction.get("extracted_fields", {})
            transactions = extracted_fields.get("transactions", [])
            
            if not transactions:
                continue
            
            logger.info(f"\nProcessing document: {doc_id} ({len(transactions)} transactions)")
            fixed_count = 0
            needs_update = False
            
            for txn in transactions:
                if not isinstance(txn, dict):
                    continue
                
                description = str(txn.get("description", "")).upper()
                debit_val = txn.get("debit")
                credit_val = txn.get("credit")
                txn_type = txn.get("type", "").upper()
                
                # Parse amounts
                try:
                    debit_amount = float(debit_val) if debit_val and str(debit_val).lower() not in ["null", "none", ""] else 0
                except (ValueError, TypeError):
                    debit_amount = 0
                
                try:
                    credit_amount = float(credit_val) if credit_val and str(credit_val).lower() not in ["null", "none", ""] else 0
                except (ValueError, TypeError):
                    credit_amount = 0
                
                # Check keywords
                is_credit_by_desc = any(keyword in description for keyword in CREDIT_KEYWORDS)
                is_debit_by_desc = any(keyword in description for keyword in DEBIT_KEYWORDS)
                
                # Fix CREDIT transactions marked as DEBIT
                if is_credit_by_desc and not is_debit_by_desc:
                    if debit_amount > 0 and credit_amount == 0:
                        logger.info(f"  Fixing: {description} - debit={debit_val} -> credit")
                        txn["credit"] = debit_val
                        txn["debit"] = None
                        txn["type"] = "CREDIT"
                        fixed_count += 1
                        needs_update = True
                    elif txn_type == "DEBIT" and debit_amount > 0:
                        logger.info(f"  Fixing: {description} - type DEBIT -> CREDIT")
                        txn["credit"] = debit_val
                        txn["debit"] = None
                        txn["type"] = "CREDIT"
                        fixed_count += 1
                        needs_update = True
                
                # Fix DEBIT transactions marked as CREDIT
                elif is_debit_by_desc and not is_credit_by_desc:
                    if credit_amount > 0 and debit_amount == 0:
                        logger.info(f"  Fixing: {description} - credit={credit_val} -> debit")
                        txn["debit"] = credit_val
                        txn["credit"] = None
                        txn["type"] = "DEBIT"
                        fixed_count += 1
                        needs_update = True
                    elif txn_type == "CREDIT" and credit_amount > 0:
                        logger.info(f"  Fixing: {description} - type CREDIT -> DEBIT")
                        txn["debit"] = credit_val
                        txn["credit"] = None
                        txn["type"] = "DEBIT"
                        fixed_count += 1
                        needs_update = True
            
            if needs_update:
                # Update extraction_results
                await db.extraction_results.update_one(
                    {"_id": extraction["_id"]},
                    {"$set": {"extracted_fields": extracted_fields}}
                )
                
                # Update documents collection
                await db.documents.update_one(
                    {"document_id": doc_id},
                    {"$set": {"extracted_data": extracted_fields}}
                )
                
                logger.info(f"  ✓ Updated {doc_id}: Fixed {fixed_count} transactions")
                total_fixed += fixed_count
            else:
                logger.info(f"  - No fixes needed for {doc_id}")
        
        logger.info(f"\n{'='*60}")
        logger.info(f"Total: Fixed {total_fixed} transactions across {len(extractions)} documents")
        
    finally:
        client.close()


if __name__ == "__main__":
    import sys
    print("Starting fix_transaction_credit_debit script...", flush=True)
    document_id = sys.argv[1] if len(sys.argv) > 1 else None
    
    if document_id:
        print(f"Fixing transactions for document: {document_id}", flush=True)
        logger.info(f"Fixing transactions for document: {document_id}")
    else:
        print("Fixing transactions for ALL bank statements", flush=True)
        logger.info("Fixing transactions for ALL bank statements")
    
    try:
        asyncio.run(fix_transactions_in_extraction_results(document_id))
        print("Script completed successfully", flush=True)
    except Exception as e:
        print(f"Script failed with error: {e}", flush=True)
        logger.error(f"Script failed: {e}", exc_info=True)
