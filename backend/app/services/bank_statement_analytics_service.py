"""
Bank Statement Analytics Service
Comprehensive analysis of bank statements for underwriting
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from app.core.database import get_database
import re
import statistics
import logging
import sys

logger = logging.getLogger(__name__)


class BankStatementAnalyticsService:
    """Service for analyzing bank statement transactions"""
    
    def __init__(self):
        # Keywords for salary detection (expanded for Indian bank statements)
        self.salary_keywords = [
            "SAL", "SALARY", "PAYROLL", "WAGES", "PAY", "REMITTANCE",
            "SALARY CREDIT", "SAL CREDIT", "SALARY PAYMENT", "SALARY TRANSFER",
            "SALARY NEFT", "SALARY RTGS", "SALARY IMPS", "SALARY UPI"
        ]
        
        # Keywords for EMI detection
        self.emi_keywords = ["EMI", "LOAN", "NACH", "ECS", "AUTO DEBIT"]
        
        # Common lenders/NBFCs
        self.lender_keywords = [
            "BAJAJ", "HDFC", "ICICI", "SBI", "AXIS", "KOTAK", "YES BANK",
            "FULLERTON", "HOME CREDIT", "CAPITAL FIRST", "ADITYA BIRLA",
            "MONEY VIEW", "SMARTCOIN", "CASHE", "KISAN", "FEDERAL", "PNB",
            "NBFC"  # Add NBFC as a lender keyword for generic NBFC loans
        ]
        
        # Keywords for credit card payments
        self.cc_keywords = ["CREDIT CARD", "CC PAYMENT", "CREDIT CARD PAYMENT", 
                           "CARD PAYMENT", "VISA", "MASTERCARD", "AMEX", "RUPAY"]
    
    def _parse_amount(self, value: Any) -> float:
        """
        Safely parse amount value, handling commas, currency symbols, and strings
        
        Args:
            value: Amount value (can be string, int, float, or None)
        
        Returns:
            float: Parsed amount value, or 0.0 if invalid
        """
        if value is None:
            return 0.0
        
        # If already a number, return as float
        if isinstance(value, (int, float)):
            return float(value)
        
        # If string, clean it first
        if isinstance(value, str):
            # Remove commas, currency symbols, and whitespace
            cleaned = value.replace(',', '').replace('₹', '').replace('$', '').replace(' ', '').strip()
            try:
                return float(cleaned)
            except (ValueError, TypeError):
                logger.warning(f"Could not parse amount: {value}")
                return 0.0
        
        return 0.0
    
    async def analyze_bank_statement(
        self,
        account_number: Optional[str] = None,
        document_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Perform comprehensive bank statement analysis
        
        Args:
            account_number: Account number to analyze
            document_id: Document ID of bank statement
            user_id: User ID (optional)
        
        Returns:
            Comprehensive analytics report
        """
        logger.info(f"analyze_bank_statement called: document_id={document_id}, account_number={account_number}, user_id={user_id}")
        db = await get_database()
        
        transactions = []
        
        # First, try to get transactions from bank_transaction_record
        # If account_number is provided, query by account_number to get ALL transactions for that account
        # (not just from one document_id, as salary transactions might be in different documents)
        if account_number:
            logger.info(f"Querying bank_transaction_record with account_number: {account_number} (to get all transactions for account)")
            transactions = await db.bank_transaction_record.find({"account_number": account_number}).sort("transaction_date", 1).to_list(length=None)
            logger.info(f"Found {len(transactions)} transactions in bank_transaction_record for account_number: {account_number}")
            
            # Log unique document_ids found
            if transactions:
                unique_doc_ids = set(txn.get("document_id") for txn in transactions if txn.get("document_id"))
                logger.info(f"Transactions span {len(unique_doc_ids)} document(s): {unique_doc_ids}")
                # Count salary transactions
                salary_txns = [txn for txn in transactions if "SALARY" in str(txn.get("description", "")).upper() or "SAL" in str(txn.get("description", "")).upper()]
                logger.info(f"Found {len(salary_txns)} transaction(s) mentioning SALARY in account")
                for sal_txn in salary_txns:
                    logger.info(f"  - Salary txn: {sal_txn.get('credit_amount')} on {sal_txn.get('transaction_date')} from doc {sal_txn.get('document_id')}")
        
        # If no transactions found by account_number, try by document_id
        elif document_id:
            logger.info(f"Querying bank_transaction_record with document_id: {document_id}")
            transactions = await db.bank_transaction_record.find({"document_id": document_id}).sort("transaction_date", 1).to_list(length=None)
            logger.info(f"Found {len(transactions)} transactions in bank_transaction_record for document_id: {document_id}")
            
            # CRITICAL: If we found transactions, extract account_number and re-query to get ALL transactions
            # This ensures we get transactions from ALL documents for this account, not just one document_id
            if transactions:
                extracted_account = transactions[0].get("account_number")
                if extracted_account:
                    logger.info(f"Extracted account_number '{extracted_account}' from transactions. Re-querying to get ALL transactions for this account.")
                    all_account_txns = await db.bank_transaction_record.find({"account_number": extracted_account}).sort("transaction_date", 1).to_list(length=None)
                    if len(all_account_txns) > len(transactions):
                        logger.info(f"Found {len(all_account_txns)} total transactions for account (vs {len(transactions)} from document_id). Using all account transactions.")
                        transactions = all_account_txns
                        # Log unique document_ids and salary transactions
                        unique_doc_ids = set(txn.get("document_id") for txn in transactions if txn.get("document_id"))
                        logger.info(f"Transactions span {len(unique_doc_ids)} document(s): {unique_doc_ids}")
                        salary_txns = [txn for txn in transactions if "SALARY" in str(txn.get("description", "")).upper() or "SAL" in str(txn.get("description", "")).upper()]
                        logger.info(f"Found {len(salary_txns)} transaction(s) mentioning SALARY in account")
                        for sal_txn in salary_txns:
                            logger.info(f"  - Salary txn: ₹{sal_txn.get('credit_amount')} on {sal_txn.get('transaction_date')} from doc {sal_txn.get('document_id')}")
        
        # If no transactions found in bank_transaction_record, try to get from extraction_results (for uploaded statements)
        # BUT: After getting from extraction_results, ALWAYS try to get from bank_transaction_record by account_number
        # (bank_transaction_record is the source of truth and has all transactions)
        if not transactions and document_id:
            logger.info(f"No transactions in bank_transaction_record, checking extraction_results for document_id: {document_id}")
            extraction = await db.extraction_results.find_one(
                {"document_id": document_id},
                sort=[("extraction_timestamp", -1)]
            )
            
            if extraction:
                extracted_fields = extraction.get("extracted_fields", {})
                extracted_account = extracted_fields.get("account_number")
                extracted_transactions = extracted_fields.get("transactions", [])
                logger.info(f"Found {len(extracted_transactions)} transactions in extraction_results")
                
                # CRITICAL: Before using extraction_results, try to get transactions from bank_transaction_record by account_number
                # This ensures we get ALL transactions, not just what's in extraction_results
                if extracted_account:
                    logger.info(f"Found account_number '{extracted_account}' in extraction_results. Checking bank_transaction_record for ALL transactions.")
                    bank_txns = await db.bank_transaction_record.find({"account_number": extracted_account}).sort("transaction_date", 1).to_list(length=None)
                    if bank_txns:
                        logger.info(f"Found {len(bank_txns)} transactions in bank_transaction_record for account_number '{extracted_account}'. Using bank_transaction_record (more complete than extraction_results).")
                        
                        # Deduplicate transactions from bank_transaction_record before using them
                        seen_txns = set()
                        deduplicated_txns = []
                        for txn in bank_txns:
                            txn_key = (
                                txn.get("transaction_date"),
                                str(txn.get("description", "")).strip()[:100],
                                round(self._parse_amount(txn.get("credit_amount", 0) or 0), 2),
                                round(self._parse_amount(txn.get("debit_amount", 0) or 0), 2)
                            )
                            if txn_key not in seen_txns:
                                seen_txns.add(txn_key)
                                deduplicated_txns.append(txn)
                        
                        if len(deduplicated_txns) < len(bank_txns):
                            logger.warning(f"Deduplicated bank_transaction_record: {len(bank_txns)} -> {len(deduplicated_txns)} transactions (removed {len(bank_txns) - len(deduplicated_txns)} duplicates)")
                            print(f"⚠️  DEDUPLICATION at fetch: Removed {len(bank_txns) - len(deduplicated_txns)} duplicates from bank_transaction_record", flush=True)
                        
                        transactions = deduplicated_txns
                        # Log unique document_ids and salary transactions
                        unique_doc_ids = set(txn.get("document_id") for txn in transactions if txn.get("document_id"))
                        logger.info(f"Transactions span {len(unique_doc_ids)} document(s): {unique_doc_ids}")
                        salary_txns = [txn for txn in transactions if "SALARY" in str(txn.get("description", "")).upper() or "SAL" in str(txn.get("description", "")).upper()]
                        logger.info(f"Found {len(salary_txns)} transaction(s) mentioning SALARY in account")
                        for sal_txn in salary_txns:
                            logger.info(f"  - Salary txn: ₹{sal_txn.get('credit_amount')} on {sal_txn.get('transaction_date')} from doc {sal_txn.get('document_id')}")
                
                # Only use extraction_results if bank_transaction_record has no data
                if not transactions and extracted_transactions:
                    for txn in extracted_transactions:
                        # Convert format: extracted transactions use "date", "debit", "credit", "balance"
                        # bank_transaction_record uses "transaction_date", "debit_amount", "credit_amount", "balance_after_transaction"
                        # Determine transaction type: prioritize explicit type, then check amounts
                        # If credit amount exists and is non-zero, it's a CREDIT; if debit exists and is non-zero, it's a DEBIT
                        debit_val = txn.get("debit") or txn.get("debit_amount")
                        credit_val = txn.get("credit") or txn.get("credit_amount")
                        
                        # Parse amounts to check if they're actually non-zero
                        debit_parsed = self._parse_amount(debit_val) if debit_val else 0
                        credit_parsed = self._parse_amount(credit_val) if credit_val else 0
                        
                        description = str(txn.get("description", "")).upper()
                        
                        # CRITICAL FIX: If description contains "SALARY" and has debit but no credit,
                        # it's likely a misclassified credit (extraction error - salary should always be credit)
                        if ("SALARY" in description or "SAL" in description):
                            if debit_parsed > 0 and credit_parsed == 0:
                                # Swap: the "debit" value is actually the credit
                                print(f"*** FIXING MISCLASSIFIED SALARY: swapping debit={debit_val} to credit ***", flush=True)
                                credit_val = debit_val
                                debit_val = None
                                credit_parsed = debit_parsed
                                debit_parsed = 0
                            # Salary transactions are always CREDITS
                            transaction_type = "CREDIT"
                        # Determine type: use explicit type if provided, otherwise infer from amounts
                        elif txn.get("type"):
                            transaction_type = txn.get("type").upper()
                            # Override if type says DEBIT but we have a credit amount (data inconsistency)
                            if transaction_type == "DEBIT" and credit_parsed > 0 and debit_parsed == 0:
                                transaction_type = "CREDIT"
                        elif credit_parsed > 0:
                            transaction_type = "CREDIT"
                        elif debit_parsed > 0:
                            transaction_type = "DEBIT"
                        else:
                            transaction_type = "CREDIT"  # Default fallback
                        
                        converted_txn = {
                            "transaction_id": f"txn_extracted_{hash(str(txn))}",
                            "document_id": document_id,
                            "account_number": extracted_fields.get("account_number"),
                            "account_holder_name": extracted_fields.get("account_holder_name"),
                            "bank_name": extracted_fields.get("bank_name"),
                            "transaction_date": txn.get("date") or txn.get("transaction_date"),
                            "description": txn.get("description", ""),
                            "transaction_type": transaction_type,
                            "debit_amount": debit_val,
                            "credit_amount": credit_val,
                            "balance_after_transaction": txn.get("balance") or txn.get("balance_after_transaction"),
                            "statement_period_from": extracted_fields.get("statement_period_from"),
                            "statement_period_to": extracted_fields.get("statement_period_to"),
                        }
                        transactions.append(converted_txn)
                        
                        # Log salary-related transactions for debugging
                        description_upper = str(converted_txn.get("description", "")).upper()
                        if "SALARY" in description_upper or "SAL" in description_upper:
                            print(f"*** SALARY TRANSACTION CONVERTED: type={transaction_type}, credit={credit_val}, debit={debit_val}, desc='{converted_txn.get('description')}', date={converted_txn.get('transaction_date')}' ***", flush=True)
                        
                        # Also log ALL transactions to see what we're processing
                        if len(transactions) <= 10:  # Log first 10 transactions
                            print(f"Transaction #{len(transactions)}: type={transaction_type}, credit={credit_val}, debit={debit_val}, desc='{converted_txn.get('description')}'", flush=True)
                    logger.info(f"Converted {len(transactions)} transactions from extraction_results format")
                    
                    # Note: We already checked bank_transaction_record by account_number before this conversion (lines 150-164)
                    # So if we're here, it means bank_transaction_record had no data and we're using extraction_results as fallback
        
        # If we got transactions from document_id but account_number is available, 
        # also try to get transactions by account_number to ensure we have ALL transactions
        if transactions and account_number and document_id:
            # Check if we should also query by account_number to get all transactions
            # (in case salary transactions are in different documents)
            account_txns = await db.bank_transaction_record.find({"account_number": account_number}).sort("transaction_date", 1).to_list(length=None)
            if len(account_txns) > len(transactions):
                logger.info(f"Found more transactions by account_number ({len(account_txns)}) than by document_id ({len(transactions)}). Using account_number query.")
                transactions = account_txns
                # Log unique document_ids and salary transactions
                unique_doc_ids = set(txn.get("document_id") for txn in transactions if txn.get("document_id"))
                logger.info(f"Transactions span {len(unique_doc_ids)} document(s): {unique_doc_ids}")
                salary_txns = [txn for txn in transactions if "SALARY" in str(txn.get("description", "")).upper() or "SAL" in str(txn.get("description", "")).upper()]
                logger.info(f"Found {len(salary_txns)} transaction(s) mentioning SALARY in account")
                for sal_txn in salary_txns:
                    logger.info(f"  - Salary txn: {sal_txn.get('credit_amount')} on {sal_txn.get('transaction_date')} from doc {sal_txn.get('document_id')}")
        
        # Fallback to account_number or user_id if still no transactions
        if not transactions:
            query = {}
            if account_number:
                query["account_number"] = account_number
                logger.info(f"Querying bank_transaction_record with account_number: {account_number}")
            elif user_id:
                query["user_id"] = user_id
                logger.info(f"Querying bank_transaction_record with user_id: {user_id}")
            else:
                logger.error("No identifier provided and no transactions found: must provide account_number, document_id, or user_id")
                return {
                    "error": "No transactions found",
                    "account_number": account_number,
                    "document_id": document_id
                }
            
            if query:
                transactions = await db.bank_transaction_record.find(query).sort("transaction_date", 1).to_list(length=None)
                logger.info(f"Found {len(transactions)} transactions for fallback query: {query}")
        
        if not transactions:
            logger.warning(f"No transactions found in any source")
            return {
                "error": "No transactions found",
                "account_number": account_number,
                "document_id": document_id
            }
        
        logger.info(f"Total transactions to analyze: {len(transactions)}")
        
        # Get account info from first transaction
        first_txn = transactions[0]
        extracted_account_number = first_txn.get("account_number")
        
        # Try to get opening/closing balance from extraction_results if available
        opening_balance = None
        closing_balance = None
        if document_id:
            extraction = await db.extraction_results.find_one({"document_id": document_id})
            if extraction and extraction.get("extracted_fields"):
                extracted_fields = extraction.get("extracted_fields", {})
                # Try nested balance object first
                balance_info = extracted_fields.get("balance", {})
                if isinstance(balance_info, dict):
                    opening_balance = balance_info.get("opening_balance")
                    closing_balance = balance_info.get("closing_balance")
                # If not found, try direct fields
                if opening_balance is None:
                    opening_balance = extracted_fields.get("opening_balance")
                if closing_balance is None:
                    closing_balance = extracted_fields.get("closing_balance")
                logger.info(f"Retrieved balances from extraction_results: opening={opening_balance}, closing={closing_balance}")
        
        account_info = {
            "account_number": extracted_account_number,
            "account_holder_name": first_txn.get("account_holder_name"),
            "bank_name": first_txn.get("bank_name"),
            "statement_period_from": first_txn.get("statement_period_from"),
            "statement_period_to": first_txn.get("statement_period_to"),
            "opening_balance": opening_balance,
            "closing_balance": closing_balance,
        }
        
        # CRITICAL: If we got transactions by document_id but account_number is available,
        # re-query by account_number to ensure we get ALL transactions (including salaries from other documents)
        if extracted_account_number and document_id and not account_number:
            logger.info(f"Extracted account_number from transactions: {extracted_account_number}. Re-querying to get ALL transactions for this account.")
            all_account_txns = await db.bank_transaction_record.find({"account_number": extracted_account_number}).sort("transaction_date", 1).to_list(length=None)
            if len(all_account_txns) > len(transactions):
                logger.info(f"Found {len(all_account_txns)} total transactions for account (vs {len(transactions)} from document_id). Using all account transactions.")
                transactions = all_account_txns
                # Log salary transactions found
                salary_txns = [txn for txn in transactions if "SALARY" in str(txn.get("description", "")).upper() or "SAL" in str(txn.get("description", "")).upper()]
                logger.info(f"Total salary transactions found: {len(salary_txns)}")
                for sal_txn in salary_txns:
                    logger.info(f"  - Salary: ₹{sal_txn.get('credit_amount')} on {sal_txn.get('transaction_date')} (doc: {sal_txn.get('document_id')})")
        
        # Get customer profile from customer_profiles collection for DTI calculation and contradiction checks
        customer_profile = None
        if user_id:
            logger.info(f"Querying customer_profiles collection with customer_id: {user_id}")
            customer_profile = await db.customer_profiles.find_one({"customer_id": user_id})
            if customer_profile:
                logger.info(f"Found customer profile: existing_loan={customer_profile.get('existing_loan')}, full_name={customer_profile.get('full_name')}")
            else:
                logger.warning(f"No customer profile found in customer_profiles collection for customer_id: {user_id}")
        elif first_txn.get("account_holder_name"):
            # Try to find by name
            account_holder = first_txn.get("account_holder_name")
            logger.info(f"Querying customer_profiles collection with account_holder_name: {account_holder}")
            customer_profile = await db.customer_profiles.find_one({
                "full_name": {"$regex": account_holder, "$options": "i"}
            })
            if customer_profile:
                logger.info(f"Found customer profile by name: existing_loan={customer_profile.get('existing_loan')}, full_name={customer_profile.get('full_name')}")
            else:
                logger.warning(f"No customer profile found in customer_profiles collection for account_holder_name: {account_holder}")
        
        # Perform all analyses
        print("=" * 80)
        print(f"About to call _analyze_income with {len(transactions)} transactions")
        print(f"First transaction sample: {transactions[0] if transactions else 'NO TRANSACTIONS'}")
        logger.info(f"Calling _analyze_income with {len(transactions)} transactions")
        
        # Get statement period for salary gap detection
        statement_from = account_info.get("statement_period_from")
        statement_to = account_info.get("statement_period_to")
        income_analysis = self._analyze_income(transactions, statement_from, statement_to)
        
        print(f"After _analyze_income: salary_detected={income_analysis.get('salary_detected')}, salary_amounts={income_analysis.get('salary_amounts')}")
        logger.info(f"Income analysis result: salary_detected={income_analysis.get('salary_detected')}, salary_count={len(income_analysis.get('salary_amounts', []))}")
        
        obligation_analysis = self._analyze_obligations(transactions)
        dti_analysis = self._calculate_dti(income_analysis, obligation_analysis, customer_profile)
        behavior_analysis = self._analyze_banking_behavior(transactions, income_analysis)
        # Pass statement period and account_info to fraud detection
        statement_from = account_info.get("statement_period_from")
        fraud_analysis = self._detect_fraud_anomalies(transactions, income_analysis, statement_from, account_info)
        
        # Include customer profile info (specifically existing_loan) for contradiction detection
        # This comes from the customer_profiles collection in the database
        customer_profile_info = {}
        if customer_profile:
            existing_loan_value = customer_profile.get("existing_loan")
            customer_profile_info = {
                "existing_loan": existing_loan_value,
                "customer_id": customer_profile.get("customer_id"),
                "full_name": customer_profile.get("full_name")
            }
            logger.info(f"Including customer_profile info in analytics: existing_loan='{existing_loan_value}', customer_id={customer_profile_info.get('customer_id')}")
        else:
            logger.warning("No customer_profile found - cannot check existing_loan contradiction with EMIs")
        
        return {
            "account_info": account_info,
            "total_transactions": len(transactions),
            "analysis_period": {
                "from": account_info["statement_period_from"],
                "to": account_info["statement_period_to"]
            },
            "income_analysis": income_analysis,
            "obligation_analysis": obligation_analysis,
            "dti_analysis": dti_analysis,
            "behavior_analysis": behavior_analysis,
            "fraud_analysis": fraud_analysis,
            "customer_profile": customer_profile_info,  # Include for contradiction checks
            "analytics_timestamp": datetime.now().isoformat()
        }
    
    def _analyze_income(self, transactions: List[Dict[str, Any]], statement_from: Optional[str] = None, statement_to: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyze income patterns from transactions
        
        IMPORTANT: Only transactions with "SALARY" or "SAL" in the description are counted as salaries.
        This ensures that CASH DEPOSIT, transfers, or other credits are NEVER mistakenly counted as salaries.
        
        Args:
            transactions: List of transaction dictionaries
            statement_from: Statement period start date (YYYY-MM-DD format)
            statement_to: Statement period end date (YYYY-MM-DD format)
        """
        salary_credits = []
        salary_dates = []
        all_credits = []
        
        print("=" * 80, flush=True)
        print(f"_analyze_income called with {len(transactions)} transactions", flush=True)
        print(f"Salary keywords: {self.salary_keywords}", flush=True)
        print("NOTE: Only transactions with SALARY/SAL in description will be counted as salaries", flush=True)
        sys.stdout.flush()
        
        credit_count = 0
        salary_candidate_count = 0  # Track credits that mention SALARY but might not match keywords
        
        for txn in transactions:
            transaction_type = txn.get("transaction_type")
            credit_amount = txn.get("credit_amount")
            
            # Try multiple possible field names for description
            description = (
                txn.get("description") or 
                txn.get("narration") or 
                txn.get("particulars") or 
                txn.get("remarks") or 
                txn.get("transaction_description") or
                ""
            )
            
            if transaction_type == "CREDIT" and credit_amount:
                credit_count += 1
                amount = self._parse_amount(credit_amount)
                description_upper = str(description).upper()
                date_str = txn.get("transaction_date")
                
                all_credits.append({
                    "date": date_str,
                    "amount": amount,
                    "description": description
                })
                
                # Check if description contains "SALARY" or "SAL" (for tracking)
                has_salary_word = "SALARY" in description_upper or "SAL" in description_upper
                if has_salary_word:
                    salary_candidate_count += 1
                
                # Check if it's a salary credit using keyword matching
                is_salary = any(keyword in description_upper for keyword in self.salary_keywords)
                
                # Log ALL credits that mention SALARY (regardless of keyword match)
                if has_salary_word:
                    print(f"CREDIT #{credit_count} (SALARY MENTIONED): amount={amount}, description='{description}', is_salary={is_salary}, date={date_str}", flush=True)
                elif credit_count <= 10:  # Log first 10 non-salary credits for debugging
                    print(f"CREDIT #{credit_count}: amount={amount}, description='{description}', is_salary={is_salary}", flush=True)
                
                if is_salary:
                    print(f"*** SALARY DETECTED: {amount} - {description} (date: {date_str}) ***", flush=True)
                    salary_credits.append(amount)
                    if date_str:
                        try:
                            salary_dates.append(datetime.fromisoformat(date_str.replace('Z', '+00:00')))
                        except:
                            try:
                                salary_dates.append(datetime.strptime(date_str, "%Y-%m-%d"))
                            except:
                                pass
                elif has_salary_word:
                    # This is a transaction that mentions SALARY but didn't match keywords - log for debugging
                    print(f"*** WARNING: Transaction mentions SALARY but didn't match keywords: {amount} - {description} ***", flush=True)
        
        print(f"Total CREDIT transactions: {credit_count}", flush=True)
        print(f"Total credits mentioning SALARY/SAL: {salary_candidate_count}", flush=True)
        print(f"Total salary credits detected (by keywords): {len(salary_credits)}", flush=True)
        
        if salary_candidate_count > len(salary_credits):
            print(f"*** WARNING: {salary_candidate_count - len(salary_credits)} transaction(s) mention SALARY but were not detected as salaries ***", flush=True)
        
        # Pattern-based salary detection (if keyword-based detection found nothing)
        # IMPORTANT: Only use pattern-based detection as fallback, and STILL require "SALARY" in description
        # This ensures we NEVER count non-salary transactions (like CASH DEPOSIT) as salaries
        if len(salary_credits) == 0 and len(all_credits) >= 2:
            print("No salaries detected by keywords, trying pattern-based detection (with SALARY keyword requirement)...", flush=True)
            # Filter credits to only those with SALARY in description before pattern detection
            salary_candidate_credits = [
                credit for credit in all_credits 
                if "SALARY" in str(credit.get("description", "")).upper() or "SAL" in str(credit.get("description", "")).upper()
            ]
            if salary_candidate_credits:
                pattern_salary_credits = self._detect_salary_by_pattern(salary_candidate_credits)
                if pattern_salary_credits:
                    print(f"Pattern-based detection found {len(pattern_salary_credits)} potential salary credits (all with SALARY in description)", flush=True)
                    # pattern_salary_credits is a list of all salary amounts (including duplicates)
                    salary_credits = pattern_salary_credits
                    # Extract dates for pattern-detected salaries
                    # Match credits by amount and add their dates
                    pattern_amounts_set = set(pattern_salary_credits)
                    for credit in salary_candidate_credits:
                        if credit["amount"] in pattern_amounts_set:
                            date_str = credit.get("date")
                            if date_str:
                                try:
                                    salary_dates.append(datetime.fromisoformat(date_str.replace('Z', '+00:00')))
                                except:
                                    try:
                                        salary_dates.append(datetime.strptime(date_str, "%Y-%m-%d"))
                                    except:
                                        pass
            else:
                print("No credits with SALARY keyword found for pattern-based detection", flush=True)
        
        print(f"Total salary credits detected (final): {len(salary_credits)}", flush=True)
        print(f"Salary amounts (before deduplication): {salary_credits}", flush=True)
        
        # DEDUPLICATION: Remove duplicate salary transactions
        # IMPORTANT: Only remove TRUE duplicates (same transaction_id, or same exact transaction on same date)
        # Different months with same salary amount are NOT duplicates - they are valid separate transactions
        # Example: 30,000 in January and 30,000 in February are both valid and should be counted
        unique_salary_data = []
        seen_transaction_ids = set()  # Primary deduplication: by transaction_id
        seen_salary_keys = set()  # Fallback deduplication: by date+amount+description (for same-day duplicates)
        
        # Re-process transactions to create unique salary entries
        for txn in transactions:
            transaction_type = txn.get("transaction_type")
            credit_amount = txn.get("credit_amount")
            transaction_id = txn.get("transaction_id")  # Use transaction_id for deduplication
            description = (
                txn.get("description") or 
                txn.get("narration") or 
                txn.get("particulars") or 
                txn.get("remarks") or 
                txn.get("transaction_description") or
                ""
            )
            
            if transaction_type == "CREDIT" and credit_amount:
                description_upper = str(description).upper()
                is_salary = any(keyword in description_upper for keyword in self.salary_keywords)
                
                if is_salary:
                    amount = self._parse_amount(credit_amount)
                    date_str = txn.get("transaction_date")
                    
                    if date_str:
                        try:
                            date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                        except:
                            try:
                                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                            except:
                                continue
                        
                        # Deduplicate by same date + amount + description (catches duplicates even with different transaction_ids)
                        # This prevents counting the same salary transaction twice on the same day
                        desc_normalized = " ".join(description_upper.split())
                        unique_key = (date_obj.strftime("%Y-%m-%d"), amount, desc_normalized)
                        
                        if unique_key not in seen_salary_keys:
                            seen_salary_keys.add(unique_key)
                            # Also track transaction_id if available (for logging)
                            if transaction_id:
                                seen_transaction_ids.add(transaction_id)
                            unique_salary_data.append({
                                "date": date_obj,
                                "amount": amount,
                                "description": description,
                                "transaction_id": transaction_id
                            })
                        else:
                            # Duplicate detected - log it
                            logger.debug(f"Duplicate salary transaction skipped: {date_obj.strftime('%Y-%m-%d')} - ₹{amount} - {description}")
        
        # Update salary_credits and salary_dates with deduplicated data
        salary_credits = [s["amount"] for s in unique_salary_data]
        salary_dates = [s["date"] for s in unique_salary_data]
        
        print(f"Salary amounts (after deduplication): {salary_credits}", flush=True)
        print(f"Total unique salary transactions: {len(salary_credits)}", flush=True)
        print(f"NOTE: Same salary amount in different months is VALID (not a duplicate)", flush=True)
        print(f"NOTE: Salary variation will be flagged as an anomaly if variation > threshold", flush=True)
        if len(salary_credits) < len([s for s in transactions if "SALARY" in str(s.get("description", "")).upper()]):
            duplicates_removed = len([s for s in transactions if "SALARY" in str(s.get("description", "")).upper()]) - len(salary_credits)
            print(f"Removed {duplicates_removed} duplicate salary transaction(s) (same transaction_id or same-day duplicates)", flush=True)
        
        sys.stdout.flush()
        logger.info(f"Income analysis: {credit_count} credits, {len(salary_credits)} unique salaries detected (after deduplication)")
        
        # Calculate salary metrics
        avg_monthly_salary = statistics.mean(salary_credits) if salary_credits else None
        salary_std_dev = statistics.stdev(salary_credits) if len(salary_credits) > 1 else 0
        
        # Salary consistency score (lower std dev = more consistent = better score)
        salary_consistency_score = 100.0
        if avg_monthly_salary and salary_std_dev:
            cv = (salary_std_dev / avg_monthly_salary) * 100  # Coefficient of variation
            salary_consistency_score = max(0, 100 - cv)  # Inverse relationship
        
        # Last salary date
        last_salary_date = max(salary_dates) if salary_dates else None
        days_since_last_salary = None
        salary_gap_flag = False
        
        # Calculate days since last salary relative to statement period end (not today's date)
        # This is only meaningful for recent statements, not historical ones
        if last_salary_date and statement_to:
            try:
                # Parse statement end date
                if isinstance(statement_to, str):
                    statement_end = datetime.strptime(statement_to, "%Y-%m-%d")
                else:
                    statement_end = statement_to
                
                # Calculate days from last salary to statement period end
                last_salary_clean = last_salary_date.replace(tzinfo=None) if last_salary_date.tzinfo else last_salary_date
                statement_end_clean = statement_end.replace(tzinfo=None) if statement_end.tzinfo else statement_end
                days_since_last_salary = (statement_end_clean - last_salary_clean).days
                
                # Only flag as "salary delay" if statement period is recent (within last 3 months)
                # For historical statements, this check doesn't make sense
                days_since_statement_end = (datetime.now() - statement_end_clean).days
                if days_since_statement_end <= 90:  # Statement is within last 3 months
                    salary_gap_flag = days_since_last_salary > 45
                else:
                    # Historical statement - don't flag salary delay based on today's date
                    salary_gap_flag = False
                    days_since_last_salary = None  # Not meaningful for historical statements
                    
            except Exception as e:
                logger.warning(f"Error calculating days_since_last_salary: {e}")
                days_since_last_salary = None
        
        # Salary gaps detection (for statement period)
        salary_gaps = self._detect_salary_gaps(salary_dates, statement_from, statement_to)
        
        # Log salary gap information
        print("=" * 80, flush=True)
        print("SALARY GAP DETECTION", flush=True)
        print(f"Statement period: {statement_from} to {statement_to}", flush=True)
        print(f"Months with salary: {salary_gaps.get('total_salaries_in_period', 0)} out of {salary_gaps.get('expected_months', 0)} months", flush=True)
        print(f"Total salary transactions: {salary_gaps.get('total_salary_transactions', 0)}", flush=True)
        print(f"Expected months in period: {salary_gaps.get('expected_months', 0)}", flush=True)
        if salary_gaps.get("has_gaps", False):
            missing = salary_gaps.get("missing_months", [])
            print(f"*** SALARY GAPS DETECTED: Missing salaries in {len(missing)} month(s): {', '.join(missing)} ***", flush=True)
        else:
            print("No salary gaps detected - all expected months have salary payments", flush=True)
        print("=" * 80, flush=True)
        
        # Group salaries by month (for reference)
        monthly_salaries = {}
        for date, amount in zip(salary_dates, salary_credits):
            month_key = date.strftime("%Y-%m")
            if month_key not in monthly_salaries:
                monthly_salaries[month_key] = []
            monthly_salaries[month_key].append(amount)
        
        return {
            "salary_detected": len(salary_credits) > 0,
            "total_salary_credits": len(salary_credits),
            "average_monthly_salary": round(avg_monthly_salary, 2) if avg_monthly_salary else None,
            "salary_amounts": salary_credits,
            "salary_consistency_score": round(salary_consistency_score, 2),
            "salary_standard_deviation": round(salary_std_dev, 2) if salary_std_dev else 0,
            "last_salary_date": last_salary_date.isoformat() if last_salary_date else None,
            "days_since_last_salary": days_since_last_salary,
            "salary_gap_flag": salary_gap_flag,
            "salary_gaps": salary_gaps,
            "monthly_salary_count": len(monthly_salaries),
            "missing_salary_months": salary_gaps.get("missing_months", []),
            "all_credits": all_credits[-20:]  # Last 20 credits for reference
        }
    
    def _detect_salary_by_pattern(self, all_credits: List[Dict[str, Any]]) -> List[float]:
        """
        Detect salary credits by pattern: regular monthly credits with similar amounts
        Returns list of salary amounts detected
        """
        if len(all_credits) < 2:
            return []
        
        # Parse dates and sort by date
        credits_with_dates = []
        for credit in all_credits:
            date_str = credit.get("date")
            if date_str:
                try:
                    date_obj = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                except:
                    try:
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                    except:
                        continue
                credits_with_dates.append({
                    "date": date_obj,
                    "amount": credit["amount"],
                    "description": credit.get("description", "")
                })
        
        if len(credits_with_dates) < 2:
            return []
        
        # Sort by date
        credits_with_dates.sort(key=lambda x: x["date"])
        
        # Group credits by similar amounts (within 20% variation)
        # Strategy: Find groups of credits with similar amounts that appear regularly
        potential_salaries = []
        
        # First, group all credits by similar amounts
        amount_groups = {}
        avg_amount = statistics.mean([c["amount"] for c in credits_with_dates])
        
        for credit in credits_with_dates:
            amount = credit["amount"]
            # Group amounts within 20% of each other
            found_group = False
            for group_avg in amount_groups.keys():
                amount_diff_pct = abs(amount - group_avg) / min(amount, group_avg) * 100 if min(amount, group_avg) > 0 else 100
                if amount_diff_pct <= 20:
                    amount_groups[group_avg].append(credit)
                    found_group = True
                    break
            if not found_group:
                amount_groups[amount] = [credit]
        
        # For each group, check if credits occur regularly (monthly pattern)
        for group_avg, group_credits in amount_groups.items():
            if len(group_credits) < 2:
                continue
            
            # Sort by date
            group_credits.sort(key=lambda x: x["date"])
            
            # Check if they occur monthly (25-35 days apart) or at least 2+ credits exist
            # For salary detection, if we have 2+ credits of same/similar amount, it's likely salary
            # even if not exactly monthly (could be bi-monthly, quarterly bonus, etc.)
            monthly_count = 0
            for i in range(len(group_credits) - 1):
                days_diff = (group_credits[i+1]["date"] - group_credits[i]["date"]).days
                # Monthly: 25-35 days, or bi-monthly: 55-65 days, or quarterly: 85-95 days
                if (25 <= days_diff <= 35) or (55 <= days_diff <= 65) or (85 <= days_diff <= 95):
                    monthly_count += 1
            
            # If we have 2+ credits with similar amounts, treat as potential salary
            # (even if not perfectly monthly - could be irregular but consistent amounts)
            if len(group_credits) >= 2:
                for credit in group_credits:
                    # Add ALL amounts (including duplicates) so we can calculate variation
                    potential_salaries.append(credit["amount"])
                    print(f"Pattern-detected salary: ₹{credit['amount']:,.0f} on {credit['date'].strftime('%Y-%m-%d')} - {credit['description']}", flush=True)
        
        # Return all amounts (including duplicates) - don't remove duplicates!
        # We need all amounts to calculate variation properly
        return potential_salaries
    
    def _detect_salary_gaps(self, salary_dates: List[datetime], statement_from: Optional[str] = None, statement_to: Optional[str] = None) -> Dict[str, Any]:
        """
        Detect gaps in salary payments within the statement period
        
        Args:
            salary_dates: List of salary transaction dates
            statement_from: Statement period start date (YYYY-MM-DD format)
            statement_to: Statement period end date (YYYY-MM-DD format)
        """
        if not salary_dates:
            return {"has_gaps": True, "missing_months": [], "message": "No salary transactions found"}
        
        salary_dates_sorted = sorted(salary_dates)
        missing_months = []
        
        # Parse statement period dates
        period_start = None
        period_end = None
        
        if statement_from:
            try:
                period_start = datetime.strptime(statement_from, "%Y-%m-%d")
            except:
                try:
                    period_start = datetime.fromisoformat(statement_from.replace('Z', '+00:00'))
                    period_start = period_start.replace(tzinfo=None)
                except:
                    pass
        
        if statement_to:
            try:
                period_end = datetime.strptime(statement_to, "%Y-%m-%d")
            except:
                try:
                    period_end = datetime.fromisoformat(statement_to.replace('Z', '+00:00'))
                    period_end = period_end.replace(tzinfo=None)
                except:
                    pass
        
        # If no statement period provided, use last 6 months from latest salary date
        if not period_start or not period_end:
            if salary_dates_sorted:
                period_end = max(salary_dates_sorted).replace(tzinfo=None) if salary_dates_sorted[-1].tzinfo else salary_dates_sorted[-1]
                period_start = period_end - timedelta(days=180)  # 6 months back
            else:
                period_end = datetime.now()
                period_start = period_end - timedelta(days=180)
        
        # Filter salaries within the statement period
        relevant_dates = [
            d.replace(tzinfo=None) if d.tzinfo else d 
            for d in salary_dates_sorted 
            if period_start <= (d.replace(tzinfo=None) if d.tzinfo else d) <= period_end
        ]
        
        if len(relevant_dates) == 0:
            return {"has_gaps": True, "missing_months": [], "message": "No salaries found in statement period"}
        
        # Group by month (use set to get unique months - handles cases where multiple salaries on same day)
        months_with_salary = set(d.strftime("%Y-%m") for d in relevant_dates)
        
        # Count unique months with salary (not total transactions)
        # This represents how many months have salary payments, not how many individual transactions
        unique_months_with_salary = len(months_with_salary)
        
        # Also count total salary transactions for reference
        total_salary_transactions = len(relevant_dates)
        
        # Find all months in the statement period
        current_month = period_start.replace(day=1)
        end_month = period_end.replace(day=1)
        
        expected_months = []
        while current_month <= end_month:
            month_key = current_month.strftime("%Y-%m")
            expected_months.append(month_key)
            # Move to next month
            if current_month.month == 12:
                current_month = current_month.replace(year=current_month.year + 1, month=1)
            else:
                current_month = current_month.replace(month=current_month.month + 1)
        
        # Find missing months
        missing_months = [month for month in expected_months if month not in months_with_salary]
        
        return {
            "has_gaps": len(missing_months) > 0,
            "missing_months": missing_months,
            "total_salaries_in_period": unique_months_with_salary,  # Count of unique months with salary (not total transactions)
            "total_salary_transactions": total_salary_transactions,  # Total number of salary transactions (for reference)
            "expected_months": len(expected_months),
            "months_with_salary": len(months_with_salary),
            "statement_period": {
                "from": period_start.strftime("%Y-%m-%d"),
                "to": period_end.strftime("%Y-%m-%d")
            }
        }
    
    def _analyze_obligations(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze EMI and debt obligations"""
        emis = []
        cc_payments = []
        
        logger.info(f"Analyzing obligations from {len(transactions)} transactions")
        
        for txn in transactions:
            if txn.get("transaction_type") == "DEBIT" and txn.get("debit_amount"):
                amount = self._parse_amount(txn.get("debit_amount", 0))
                description = str(txn.get("description", "")).upper()
                date_str = txn.get("transaction_date")
                
                # IMPORTANT: Check for credit card payment FIRST to avoid double-counting
                # Credit card payments should NOT be counted as EMIs, even if they contain lender names
                is_cc = any(keyword in description for keyword in self.cc_keywords)
                if is_cc:
                    cc_payments.append({
                        "date": date_str,
                        "amount": amount,
                        "description": txn.get("description")
                    })
                    logger.debug(f"Credit card payment detected: {date_str}, amount={amount}, description='{txn.get('description')}'")
                    continue  # Skip EMI detection for credit card payments
                
                # Check for EMI (only if not a credit card payment)
                is_emi = any(keyword in description for keyword in self.emi_keywords)
                is_lender = any(lender in description for lender in self.lender_keywords)
                
                if is_emi or is_lender:
                    # Extract lender name
                    lender_name = self._extract_lender_name(description)
                    
                    emis.append({
                        "date": date_str,
                        "amount": amount,
                        "description": txn.get("description"),
                        "lender_name": lender_name,
                        "transaction_id": txn.get("transaction_id")
                    })
                    logger.debug(f"EMI detected: {date_str}, amount={amount}, description='{txn.get('description')}', lender={lender_name}")
        
        logger.info(f"Total EMI transactions detected (before deduplication): {len(emis)}")
        if emis:
            logger.info(f"EMI details: {[(e['date'], e['amount'], e['lender_name'], e.get('transaction_id', 'no_id')) for e in emis[:10]]}")
        
        # DEDUPLICATION: Remove duplicate EMI transactions (same transaction_id or same date+amount+description)
        # This handles cases where the same transaction appears multiple times
        unique_emis = []
        seen_emi_ids = set()  # Primary deduplication: by transaction_id
        seen_emi_keys = set()  # Fallback deduplication: by date+amount+description
        
        for emi in emis:
            transaction_id = emi.get("transaction_id")
            date_str = emi.get("date")
            amount = emi.get("amount")
            description = str(emi.get("description", "")).upper()
            
            # PRIMARY: Deduplicate by transaction_id (most accurate)
            if transaction_id:
                if transaction_id not in seen_emi_ids:
                    seen_emi_ids.add(transaction_id)
                    unique_emis.append(emi)
            else:
                # FALLBACK: If no transaction_id, deduplicate by same date + amount + description
                normalized_amount = round(float(amount))
                desc_normalized = " ".join(description.split())
                unique_key = (date_str, normalized_amount, desc_normalized)
                
                if unique_key not in seen_emi_keys:
                    seen_emi_keys.add(unique_key)
                    unique_emis.append(emi)
        
        logger.info(f"Total unique EMI transactions (after deduplication): {len(unique_emis)}")
        if len(unique_emis) < len(emis):
            duplicates_removed = len(emis) - len(unique_emis)
            logger.info(f"Removed {duplicates_removed} duplicate EMI transaction(s)")
        
        # Group EMIs by lender and amount (to identify recurring EMIs)
        # Normalize amounts to handle float/int/string variations (round to nearest rupee)
        # This ensures 20000.0, 20000, and "20000" all group together
        emi_groups = {}
        for emi in unique_emis:  # Use deduplicated list
            # Normalize amount to integer (round to handle floating point issues like 20000.0 vs 20000)
            normalized_amount = round(float(emi['amount']))
            key = f"{emi['lender_name']}_{normalized_amount}"
            if key not in emi_groups:
                emi_groups[key] = []
            emi_groups[key].append(emi)
        
        logger.info(f"EMI groups created: {len(emi_groups)} groups")
        for key, group in emi_groups.items():
            logger.info(f"  Group '{key}': {len(group)} transactions, amounts={[e['amount'] for e in group]}")
        
        # Identify recurring EMIs (same amount, monthly pattern)
        recurring_emis = []
        for key, group in emi_groups.items():
            if len(group) >= 2:  # At least 2 occurrences
                amounts = [e["amount"] for e in group]
                if len(set(amounts)) == 1:  # All same amount
                    # Extract day of month for each EMI payment
                    emi_days = []
                    emi_dates_parsed = []
                    bounces = []
                    
                    for emi_txn in group:
                        date_str = emi_txn.get("date")
                        if date_str:
                            try:
                                if isinstance(date_str, str):
                                    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                                else:
                                    date_obj = date_str
                                day_of_month = date_obj.day
                                emi_days.append(day_of_month)
                                emi_dates_parsed.append(date_obj)
                                
                                # Check for bounces (NACH return, insufficient funds, etc.)
                                description = str(emi_txn.get("description", "")).upper()
                                if any(bounce_keyword in description for bounce_keyword in ["RETURN", "BOUNCE", "INSUFFICIENT", "FAILED", "REJECTED"]):
                                    bounces.append({
                                        "date": date_str,
                                        "description": emi_txn.get("description"),
                                        "reason": "NACH return or insufficient funds"
                                    })
                            except:
                                pass
                    
                    # Calculate most common day of month (EMI payment day)
                    most_common_day = None
                    if emi_days:
                        from collections import Counter
                        day_counts = Counter(emi_days)
                        most_common_day = day_counts.most_common(1)[0][0]
                    
                    recurring_emis.append({
                        "lender_name": group[0]["lender_name"],
                        "emi_amount": group[0]["amount"],
                        "occurrences": len(group),
                        "dates": [e["date"] for e in group],
                        "emi_payment_day": most_common_day,  # Day of month when EMI is typically paid
                        "payment_days": list(set(emi_days)) if emi_days else [],  # All unique payment days
                        "bounces": bounces,  # Any bounced/failed payments
                        "bounce_count": len(bounces),
                        "is_recurring": True
                    })
                    logger.info(f"Recurring EMI identified: {group[0]['lender_name']}, amount=₹{group[0]['amount']:,.0f}, occurrences={len(group)}, payment_day={most_common_day}, bounces={len(bounces)}")
        
        logger.info(f"Total recurring EMIs: {len(recurring_emis)}")
        
        # Calculate total monthly EMI obligation (average of all EMIs)
        total_monthly_emi = sum(r["emi_amount"] for r in recurring_emis)
        
        # Analyze credit card payments
        avg_monthly_cc_payment = statistics.mean([cc["amount"] for cc in cc_payments]) if cc_payments else 0
        
        # Credit card payment pattern analysis
        cc_payment_analysis = {
            "total_payments": len(cc_payments),
            "average_monthly_payment": round(avg_monthly_cc_payment, 2) if cc_payments else 0,
            "payment_pattern": None,  # "MINIMUM_ONLY", "FULL_PAYMENT", "MIXED", "VARIABLE"
            "minimum_payment_ratio": None,  # Ratio of minimum payments to total
            "payment_consistency": None  # How consistent are the payment amounts
        }
        
        if cc_payments:
            cc_amounts = [cc["amount"] for cc in cc_payments]
            min_payment = min(cc_amounts)
            max_payment = max(cc_amounts)
            avg_payment = avg_monthly_cc_payment
            
            # Detect payment pattern
            # If all payments are similar (within 10%), likely full payment
            # If payments vary significantly, might be minimum payments or variable amounts
            if len(cc_amounts) > 1:
                std_dev = statistics.stdev(cc_amounts) if len(cc_amounts) > 1 else 0
                cv = (std_dev / avg_payment * 100) if avg_payment > 0 else 0
                
                # If coefficient of variation is low (< 15%), payments are consistent (likely full payment)
                # If high variation, might be minimum payments or variable spending
                if cv < 15:
                    cc_payment_analysis["payment_pattern"] = "FULL_PAYMENT"
                    cc_payment_analysis["payment_consistency"] = "HIGH"
                elif cv > 50:
                    cc_payment_analysis["payment_pattern"] = "VARIABLE"
                    cc_payment_analysis["payment_consistency"] = "LOW"
                else:
                    cc_payment_analysis["payment_pattern"] = "MIXED"
                    cc_payment_analysis["payment_consistency"] = "MEDIUM"
                
                # Estimate if paying minimum (typically minimum is 5% of outstanding, but we can't know outstanding)
                # If payments are very small relative to average, might be minimum payments
                # This is a heuristic - actual minimum payment detection would need credit limit/outstanding data
                if min_payment < avg_payment * 0.3:  # If minimum payment is less than 30% of average
                    cc_payment_analysis["payment_pattern"] = "MINIMUM_ONLY"
            
            logger.info(f"Credit card payment analysis: pattern={cc_payment_analysis['payment_pattern']}, avg=₹{avg_monthly_cc_payment:,.0f}, consistency={cc_payment_analysis['payment_consistency']}")
        
        return {
            "total_emi_transactions": len(unique_emis),  # Use deduplicated count
            "detected_emis": unique_emis,  # Return deduplicated EMIs (all EMI transactions)
            "recurring_emis": recurring_emis,  # Recurring EMIs with details (lender, amount, payment day, bounces, etc.)
            "total_monthly_emi_obligation": round(total_monthly_emi, 2),  # Sum of all recurring EMIs
            "credit_card_payments": cc_payments,  # All credit card payment transactions
            "total_cc_payments": len(cc_payments),
            "average_monthly_cc_payment": round(avg_monthly_cc_payment, 2) if cc_payments else 0,
            "credit_card_payment_analysis": cc_payment_analysis,  # Payment pattern analysis (minimum vs full)
            "total_monthly_obligations": round(total_monthly_emi + avg_monthly_cc_payment, 2)  # Total for DTI calculation
        }
    
    def _extract_lender_name(self, description: str) -> str:
        """Extract lender name from transaction description"""
        description_upper = description.upper()
        for lender in self.lender_keywords:
            if lender in description_upper:
                return lender
        return "UNKNOWN LENDER"
    
    def _calculate_dti(
        self,
        income_analysis: Dict[str, Any],
        obligation_analysis: Dict[str, Any],
        customer_profile: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calculate Debt-to-Income ratio according to specification:
        DTI = (Total Monthly Obligations) / (Net Monthly Income) × 100
        
        Where:
        - Total Monthly Obligations = Sum of all EMIs + Average Credit Card Payments
        - Net Monthly Income = Average Monthly Salary from bank statement
        """
        # Actual DTI (from bank statement)
        actual_net_income = income_analysis.get("average_monthly_salary") or 0
        actual_monthly_obligations = obligation_analysis.get("total_monthly_obligations", 0)
        
        # Ensure values are numeric
        if actual_net_income is None:
            actual_net_income = 0
        if actual_monthly_obligations is None:
            actual_monthly_obligations = 0
        
        # DTI Formula: (Total Monthly Obligations / Net Monthly Income) × 100
        actual_dti = (actual_monthly_obligations / actual_net_income * 100) if actual_net_income > 0 else 0
        
        # Log DTI calculation for debugging
        logger.info(f"DTI Calculation: Obligations=₹{actual_monthly_obligations:,.2f}, Income=₹{actual_net_income:,.2f}, DTI={actual_dti:.2f}%")
        if actual_dti > 50:
            logger.warning(f"HIGH DTI DETECTED: {actual_dti:.2f}% (>50% threshold)")
        
        # Stated DTI calculation removed - stated_obligations not available from customer profile
        # Only actual DTI from bank statement is calculated and used for risk assessment
        stated_dti = None
        stated_income = None
        stated_obligations = None
        
        # DTI Trend Analysis: Check if DTI is increasing over time
        # This compares DTI in first half vs second half of statement period
        dti_trend = None
        
        # Get monthly salary data from income_analysis
        # Note: We need to pass monthly salary data through income_analysis for trend analysis
        # For now, we'll use a simplified approach: compare if obligations increased while income stayed same
        recurring_emis = obligation_analysis.get("recurring_emis", [])
        monthly_emi_total = sum(emi.get("emi_amount", 0) for emi in recurring_emis)
        monthly_cc_payment = obligation_analysis.get("average_monthly_cc_payment", 0)
        monthly_obligations = monthly_emi_total + monthly_cc_payment
        
        # Simple trend: If we have salary amounts, check if income decreased or obligations increased
        salary_amounts = income_analysis.get("salary_amounts", [])
        if len(salary_amounts) >= 4 and actual_net_income > 0:
            # Compare first half vs second half of salaries
            first_half_salaries = salary_amounts[:len(salary_amounts)//2]
            second_half_salaries = salary_amounts[len(salary_amounts)//2:]
            
            first_half_avg = statistics.mean(first_half_salaries) if first_half_salaries else actual_net_income
            second_half_avg = statistics.mean(second_half_salaries) if second_half_salaries else actual_net_income
            
            first_half_dti = (monthly_obligations / first_half_avg * 100) if first_half_avg > 0 else 0
            second_half_dti = (monthly_obligations / second_half_avg * 100) if second_half_avg > 0 else 0
            
            dti_change = second_half_dti - first_half_dti
            is_increasing = dti_change > 5  # Flag if DTI increased by more than 5%
            
            dti_trend = {
                "first_half_dti": round(first_half_dti, 2),
                "second_half_dti": round(second_half_dti, 2),
                "dti_change": round(dti_change, 2),
                "is_increasing": is_increasing,
                "trend": "INCREASING" if is_increasing else "STABLE" if abs(dti_change) <= 5 else "DECREASING",
                "first_half_income": round(first_half_avg, 2),
                "second_half_income": round(second_half_avg, 2)
            }
            
            if is_increasing:
                logger.warning(f"DTI trend: INCREASING - First half: {first_half_dti:.1f}%, Second half: {second_half_dti:.1f}% (change: +{dti_change:.1f}%)")
        
        # Flags - Only HIGH_DTI flag (DTI > 50%)
        # Removed ACTUAL_EXCEEDS_STATED and DTI_INCREASING as stated DTI is not available
        flags = []
        if actual_dti is not None and actual_dti > 50:
            flags.append("HIGH_DTI")
        
        # Ensure actual_dti is a number for comparisons
        if actual_dti is None:
            actual_dti = 0
        
        return {
            "actual_dti": round(actual_dti, 2),
            "actual_net_income": round(actual_net_income, 2),
            "actual_monthly_obligations": round(actual_monthly_obligations, 2),
            "stated_dti": round(stated_dti, 2) if stated_dti else None,
            "stated_income": round(stated_income, 2) if stated_income else None,
            "stated_monthly_obligations": round(stated_obligations, 2) if stated_obligations else None,
            "dti_trend": dti_trend,  # Trend analysis (increasing/decreasing over time)
            "flags": flags,
            "dti_status": "HIGH_RISK" if actual_dti > 50 else "MEDIUM_RISK" if actual_dti > 30 else "LOW_RISK"
        }
    
    def _analyze_banking_behavior(
        self,
        transactions: List[Dict[str, Any]],
        income_analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze banking behavior patterns"""
        balances = []
        debits = []
        credits = []
        cash_withdrawals = []
        
        for txn in transactions:
            if txn.get("balance_after_transaction"):
                balances.append(self._parse_amount(txn.get("balance_after_transaction", 0)))
            
            description = str(txn.get("description", "")).upper()
            
            if txn.get("transaction_type") == "DEBIT":
                debits.append(txn)
                # Check for cash withdrawal
                if any(keyword in description for keyword in ["ATM", "CASH", "WITHDRAWAL", "WD"]):
                    if txn.get("debit_amount"):
                        cash_withdrawals.append({
                            "date": txn.get("transaction_date"),
                            "amount": self._parse_amount(txn.get("debit_amount", 0)),
                            "description": txn.get("description")
                        })
            
            elif txn.get("transaction_type") == "CREDIT":
                credits.append(txn)
        
        # Calculate metrics
        avg_monthly_balance = statistics.mean(balances) if balances else 0
        min_balance = min(balances) if balances else 0
        max_balance = max(balances) if balances else 0
        
        # Compare AMB to income
        avg_income = income_analysis.get("average_monthly_salary", 0) or 0
        if avg_income is None or avg_income <= 0:
            avg_income = 0
        amb_to_income_ratio = (avg_monthly_balance / avg_income * 100) if avg_income > 0 else 0
        
        # Transaction counts
        total_debits = len(debits)
        total_credits = len(credits)
        total_transactions = len(transactions)
        
        # Cash withdrawal analysis
        avg_cash_withdrawal = statistics.mean([w["amount"] for w in cash_withdrawals if w.get("amount") is not None]) if cash_withdrawals else 0
        large_cash_withdrawals = [w for w in cash_withdrawals if w.get("amount") is not None and w["amount"] > 50000]
        
        return {
            "average_monthly_balance": round(avg_monthly_balance, 2),
            "minimum_balance": round(min_balance, 2),
            "maximum_balance": round(max_balance, 2),
            "amb_to_income_ratio": round(amb_to_income_ratio, 2),
            "liquidity_status": "STRESSED" if amb_to_income_ratio < 10 else "MODERATE" if amb_to_income_ratio < 50 else "HEALTHY",
            "total_debits": total_debits,
            "total_credits": total_credits,
            "total_transactions": total_transactions,
            "average_transactions_per_month": round(total_transactions / 6, 2) if total_transactions > 0 else 0,
            "cash_withdrawals": {
                "total_count": len(cash_withdrawals),
                "average_amount": round(avg_cash_withdrawal, 2),
                "large_withdrawals": large_cash_withdrawals,
                "total_amount": round(sum(w["amount"] for w in cash_withdrawals), 2)
            }
        }
    
    def _detect_fraud_anomalies(
        self,
        transactions: List[Dict[str, Any]],
        income_analysis: Dict[str, Any],
        statement_from: Optional[str] = None,
        account_info: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Detect fraud and anomalies"""
        anomalies = []
        
        # 1. Round-tripping detection
        round_tripping_instances = self._detect_round_tripping(transactions)
        if round_tripping_instances:
            anomalies.append({
                "type": "ROUND_TRIPPING",
                "severity": "HIGH",
                "description": "Large credits followed by similar debits detected (possible fake salary)",
                "instances": round_tripping_instances
            })
        
        # 2. Transaction sequence validation
        # Pass account_info to get opening/closing balances from statement header
        print("\n" + "="*80, flush=True)
        print("🔍 TRANSACTION SEQUENCE VALIDATION - STARTING", flush=True)
        print("="*80, flush=True)
        logger.info("Starting Transaction Sequence Validation...")
        print(f"📊 Total transactions to validate: {len(transactions)}", flush=True)
        if account_info:
            print(f"📋 Account Info available: {account_info.get('account_number', 'N/A')}", flush=True)
            print(f"   Statement Period: {account_info.get('statement_period_from', 'N/A')} to {account_info.get('statement_period_to', 'N/A')}", flush=True)
            print(f"   Opening Balance in account_info: {account_info.get('opening_balance', 'NOT FOUND')}", flush=True)
            print(f"   Closing Balance in account_info: {account_info.get('closing_balance', 'NOT FOUND')}", flush=True)
        else:
            print("⚠️  WARNING: account_info is None - will try to calculate from transactions", flush=True)
        
        sequence_errors = self._validate_transaction_sequence(transactions, statement_from, account_info)
        
        print("="*80, flush=True)
        print(f"✅ TRANSACTION SEQUENCE VALIDATION - COMPLETED: {len(sequence_errors)} error(s) found", flush=True)
        print("="*80, flush=True)
        logger.info(f"Transaction Sequence Validation completed: {len(sequence_errors)} error(s) found")
        
        if sequence_errors:
            logger.warning(f"Transaction Sequence Error detected: {len(sequence_errors)} error(s)")
            print(f"\n🚨 TRANSACTION SEQUENCE ERROR DETECTED!", flush=True)
            print(f"   Creating CRITICAL anomaly with {len(sequence_errors)} error(s)", flush=True)
            for i, error in enumerate(sequence_errors, 1):
                print(f"   Error {i}: Difference = ₹{error.get('difference', 0):,.2f}", flush=True)
            print("="*80 + "\n", flush=True)
            anomalies.append({
                "type": "TRANSACTION_SEQUENCE_ERROR",
                "severity": "CRITICAL",
                "description": "Balance calculations don't match (possible tampering)",
                "errors": sequence_errors
            })
        else:
            logger.info("Transaction Sequence Validation passed: No errors found")
            print(f"\n✅ TRANSACTION SEQUENCE VALIDATION: PASSED - No errors (balances match correctly)", flush=True)
            print("="*80 + "\n", flush=True)
        
        # 3. Income instability
        consistency_score = income_analysis.get("salary_consistency_score", 100)
        if consistency_score is not None and consistency_score < 50:
            anomalies.append({
                "type": "INCOME_INSTABILITY",
                "severity": "MEDIUM",
                "description": "High variation in salary amounts",
                "consistency_score": income_analysis.get("salary_consistency_score")
            })
        
        # 4. Missing salary months
        # NOTE: Salary gaps are already handled in risk_analysis_service with detailed information
        # Including statement period, missing months, etc. So we skip creating a duplicate here.
        # The risk analysis service will create a more detailed "salary_gaps" anomaly.
        
        return {
            "total_anomalies": len(anomalies),
            "anomalies": anomalies,
            "risk_level": "CRITICAL" if any(a["severity"] == "CRITICAL" for a in anomalies) else 
                         "HIGH" if any(a["severity"] == "HIGH" for a in anomalies) else
                         "MEDIUM" if any(a["severity"] == "MEDIUM" for a in anomalies) else "LOW"
        }
    
    def _detect_round_tripping(self, transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Detect round-tripping patterns (large credit -> similar debit)"""
        instances = []
        
        # Sort transactions by date to ensure chronological order
        sorted_txns = sorted(transactions, key=lambda x: x.get("transaction_date", ""))
        
        for i, txn in enumerate(sorted_txns):
            try:
                if txn.get("transaction_type") == "CREDIT" and txn.get("credit_amount"):
                    credit_amount = self._parse_amount(txn.get("credit_amount", 0))
                    credit_date_str = txn.get("transaction_date")
                    
                    if credit_amount > 50000:  # Large credit
                        try:
                            credit_date = datetime.fromisoformat(credit_date_str.replace('Z', '+00:00'))
                        except:
                            try:
                                credit_date = datetime.strptime(credit_date_str, "%Y-%m-%d")
                            except:
                                continue
                        
                        # Look for similar debit within 5 days
                        for j in range(i+1, min(i+50, len(sorted_txns))):  # Check next 50 transactions
                            next_txn = sorted_txns[j]
                            if next_txn.get("transaction_type") == "DEBIT" and next_txn.get("debit_amount"):
                                debit_amount = self._parse_amount(next_txn.get("debit_amount", 0))
                                debit_date_str = next_txn.get("transaction_date")
                                
                                try:
                                    debit_date = datetime.fromisoformat(debit_date_str.replace('Z', '+00:00'))
                                except:
                                    try:
                                        debit_date = datetime.strptime(debit_date_str, "%Y-%m-%d")
                                    except:
                                        continue
                                
                                days_diff = (debit_date - credit_date).days
                                
                                if 0 < days_diff <= 5:  # Within 5 days
                                    # Check if amounts are similar (within 10%)
                                    # Avoid division by zero
                                    if credit_amount > 0:
                                        amount_diff_pct = abs(credit_amount - debit_amount) / credit_amount * 100
                                        if amount_diff_pct < 10:  # Similar amounts
                                            instances.append({
                                                "credit_date": credit_date_str,
                                                "credit_amount": credit_amount,
                                                "credit_description": txn.get("description"),
                                                "debit_date": debit_date_str,
                                                "debit_amount": debit_amount,
                                                "debit_description": next_txn.get("description"),
                                                "days_diff": days_diff,
                                                "amount_diff_pct": round(amount_diff_pct, 2)
                                            })
                                            break  # Found matching debit, move to next credit
            except Exception as e:
                logger.warning(f"Error detecting round-tripping for transaction {i}: {e}")
                continue
        
        return instances
    
    def _validate_transaction_sequence(self, transactions: List[Dict[str, Any]], statement_from: Optional[str] = None, account_info: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Validate transaction sequence using the formula:
        Opening Balance + Total Credits - Total Debits = Closing Balance
        
        If mismatch → transactions deleted/added manually (possible tampering)
        """
        errors = []
        
        if not transactions:
            return errors
        
        # Remove duplicate transactions to avoid double-counting
        # Use a composite key: date + description + credit + debit (most reliable)
        seen_transactions = set()
        unique_txns = []
        duplicate_count = 0
        
        for txn in transactions:
            # Create a unique key based on date, description, and amounts
            # This catches duplicates even if transaction_id is missing or duplicated
            txn_date = txn.get("transaction_date")
            description = str(txn.get("description", "")).strip()[:100]  # First 100 chars
            credit_amt = round(self._parse_amount(txn.get("credit_amount", 0) or 0), 2)
            debit_amt = round(self._parse_amount(txn.get("debit_amount", 0) or 0), 2)
            
            # Create composite key - this uniquely identifies a transaction
            txn_key = (
                txn_date,
                description,
                credit_amt,
                debit_amt
            )
            
            if txn_key not in seen_transactions:
                seen_transactions.add(txn_key)
                unique_txns.append(txn)
            else:
                duplicate_count += 1
                logger.debug(f"Duplicate transaction skipped: {txn_date} - {description} - Credit: {credit_amt}, Debit: {debit_amt}")
        
        if duplicate_count > 0:
            logger.info(f"Removed {duplicate_count} duplicate transaction(s) for validation ({len(transactions)} -> {len(unique_txns)})")
            print(f"🔍 DEDUPLICATION: Removed {duplicate_count} duplicate(s) ({len(transactions)} -> {len(unique_txns)} transactions)", flush=True)
        
        # Filter to statement period if provided
        if statement_from:
            try:
                statement_from_date = datetime.strptime(statement_from, "%Y-%m-%d") if isinstance(statement_from, str) else statement_from
                statement_to_date = None
                if account_info and account_info.get("statement_period_to"):
                    statement_to_date = datetime.strptime(account_info.get("statement_period_to"), "%Y-%m-%d") if isinstance(account_info.get("statement_period_to"), str) else account_info.get("statement_period_to")
                
                original_count = len(unique_txns)
                filtered_txns = []
                for txn in unique_txns:
                    txn_date_str = txn.get("transaction_date")
                    if not txn_date_str:
                        continue
                    txn_date = datetime.strptime(txn_date_str, "%Y-%m-%d") if isinstance(txn_date_str, str) else txn_date_str
                    
                    # Include if within statement period
                    if txn_date >= statement_from_date:
                        if statement_to_date is None or txn_date <= statement_to_date:
                            filtered_txns.append(txn)
                
                unique_txns = filtered_txns
                logger.info(f"Filtered to {len(unique_txns)} transactions within statement period ({statement_from} to {account_info.get('statement_period_to') if account_info else 'N/A'}, was {original_count})")
                print(f"FILTERED TRANSACTIONS: {original_count} -> {len(unique_txns)} (period: {statement_from} to {account_info.get('statement_period_to') if account_info else 'N/A'})", flush=True)
            except Exception as e:
                logger.warning(f"Failed to filter by statement period: {e}")
                print(f"FILTERING FAILED: {e}", flush=True)
        
        if not unique_txns:
            return errors
        
        # Get opening balance from account_info or calculate from first transaction
        opening_balance = None
        if account_info and account_info.get("opening_balance"):
            opening_balance = self._parse_amount(account_info.get("opening_balance"))
            logger.info(f"Using opening balance from account_info: ₹{opening_balance:,.2f}")
            print(f"OPENING BALANCE: From account_info = ₹{opening_balance:,.2f}", flush=True)
        else:
            # Calculate from first transaction
            sorted_txns = sorted(unique_txns, key=lambda x: x.get("transaction_date", ""))
            if sorted_txns:
                first_txn = sorted_txns[0]
                first_txn_balance = self._parse_amount(first_txn.get("balance_after_transaction", 0) or 0)
                first_txn_credit = self._parse_amount(first_txn.get("credit_amount", 0) or 0)
                first_txn_debit = self._parse_amount(first_txn.get("debit_amount", 0) or 0)
                if first_txn_balance:
                    opening_balance = first_txn_balance - first_txn_credit + first_txn_debit
                    logger.info(f"Calculated opening balance from first transaction: ₹{opening_balance:,.2f}")
                    print(f"OPENING BALANCE: Calculated from first txn = ₹{opening_balance:,.2f} (Balance={first_txn_balance:,.2f}, Credit={first_txn_credit:,.2f}, Debit={first_txn_debit:,.2f})", flush=True)
        
        if opening_balance is None:
            logger.warning("Cannot validate - opening balance not available")
            print(f"TRANSACTION SEQUENCE VALIDATION: SKIPPED - Opening balance not available", flush=True)
            return errors
        
        # Get closing balance from account_info or from last transaction
        closing_balance = None
        if account_info and account_info.get("closing_balance"):
            closing_balance = self._parse_amount(account_info.get("closing_balance"))
            logger.info(f"Using closing balance from account_info: ₹{closing_balance:,.2f}")
            print(f"CLOSING BALANCE: From account_info = ₹{closing_balance:,.2f}", flush=True)
        else:
            # Get from last transaction
            sorted_txns = sorted(unique_txns, key=lambda x: x.get("transaction_date", ""))
            if sorted_txns:
                closing_balance = self._parse_amount(sorted_txns[-1].get("balance_after_transaction", 0) or 0)
                logger.info(f"Using closing balance from last transaction: ₹{closing_balance:,.2f}")
                print(f"CLOSING BALANCE: From last transaction = ₹{closing_balance:,.2f} (Date: {sorted_txns[-1].get('transaction_date')})", flush=True)
        
        if closing_balance is None:
            logger.warning("Cannot validate - closing balance not available")
            print(f"TRANSACTION SEQUENCE VALIDATION: SKIPPED - Closing balance not available", flush=True)
            return errors
        
        # Calculate total credits and debits
        # Only count non-null, non-zero values (transactions should have either credit OR debit, not both)
        total_credits = 0
        total_debits = 0
        credit_count = 0
        debit_count = 0
        
        for txn in unique_txns:
            credit_val = txn.get("credit_amount")
            debit_val = txn.get("debit_amount")
            
            # Parse amounts - only count if not None and not 0
            if credit_val is not None:
                credit_parsed = self._parse_amount(credit_val)
                if credit_parsed > 0:
                    total_credits += credit_parsed
                    credit_count += 1
            
            if debit_val is not None:
                debit_parsed = self._parse_amount(debit_val)
                if debit_parsed > 0:
                    total_debits += debit_parsed
                    debit_count += 1
        
        logger.info(f"Credit/Debit Summary: {credit_count} credit transactions (₹{total_credits:,.2f}), {debit_count} debit transactions (₹{total_debits:,.2f}) from {len(unique_txns)} total transactions")
        print(f"CREDIT/DEBIT CALCULATION: {credit_count} credits=₹{total_credits:,.2f}, {debit_count} debits=₹{total_debits:,.2f} (from {len(unique_txns)} transactions)", flush=True)
        
        # Debug: Show first few transactions to verify data
        if unique_txns:
            print(f"SAMPLE TRANSACTIONS (first 3):", flush=True)
            for i, txn in enumerate(unique_txns[:3]):
                date = txn.get("transaction_date", "N/A")
                credit = txn.get("credit_amount")
                debit = txn.get("debit_amount")
                balance = txn.get("balance_after_transaction")
                print(f"  [{i+1}] Date={date}, Credit={credit}, Debit={debit}, Balance={balance}", flush=True)
        
        # Formula: Opening + Credits - Debits = Closing
        expected_closing = opening_balance + total_credits - total_debits
        
        logger.info(f"Transaction Sequence Validation: Opening=₹{opening_balance:,.2f}, Credits=₹{total_credits:,.2f}, Debits=₹{total_debits:,.2f}, Expected Closing=₹{expected_closing:,.2f}, Actual Closing=₹{closing_balance:,.2f}")
        print(f"\n📐 TRANSACTION SEQUENCE CALCULATION:", flush=True)
        print(f"   Opening Balance:     ₹{opening_balance:,.2f}", flush=True)
        print(f"   + Total Credits:     ₹{total_credits:,.2f} ({credit_count} transactions)", flush=True)
        print(f"   - Total Debits:      ₹{total_debits:,.2f} ({debit_count} transactions)", flush=True)
        print(f"   = Expected Closing: ₹{expected_closing:,.2f}", flush=True)
        print(f"   Actual Closing:      ₹{closing_balance:,.2f}", flush=True)
        print(f"   ────────────────────────────────────────", flush=True)
        difference = abs(expected_closing - closing_balance)
        print(f"   Difference:          ₹{difference:,.2f}", flush=True)
        
        # Allow small rounding differences (1 rupee)
        difference = abs(expected_closing - closing_balance)
        if difference > 1:
            error_count = 1  # Single error for the overall mismatch
            errors.append({
                "transaction_date": "STATEMENT_PERIOD",
                "transaction_id": "BALANCE_MISMATCH",
                "expected_balance": expected_closing,
                "actual_balance": closing_balance,
                "difference": difference,
                "opening_balance": opening_balance,
                "total_credits": total_credits,
                "total_debits": total_debits,
                "formula": f"Opening ({opening_balance:,.2f}) + Credits ({total_credits:,.2f}) - Debits ({total_debits:,.2f}) = Expected Closing ({expected_closing:,.2f})"
            })
            logger.warning(f"Transaction sequence error: Expected closing balance ₹{expected_closing:,.2f}, Actual closing balance ₹{closing_balance:,.2f}, Difference ₹{difference:,.2f}")
            print(f"\n❌ BALANCE MISMATCH DETECTED!", flush=True)
            print(f"   Expected Closing: ₹{expected_closing:,.2f}", flush=True)
            print(f"   Actual Closing:   ₹{closing_balance:,.2f}", flush=True)
            print(f"   Difference:      ₹{difference:,.2f} (> ₹1 threshold)", flush=True)
            print(f"   ⚠️  Possible tampering: transactions deleted/added manually", flush=True)
        else:
            print(f"\n✅ BALANCE MATCH: Opening + Credits - Debits = Closing", flush=True)
            print(f"   Difference: ₹{difference:,.2f} (within ₹1 tolerance)", flush=True)
        
        return errors


# Singleton instance
bank_statement_analytics_service = BankStatementAnalyticsService()
