"""
Script to import bank statement data from CSV or Excel file for two customers
Stores transactions in 'bank_transaction_record' collection
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import pandas as pd
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from datetime import datetime, timezone
import uuid
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def parse_date(date_value):
    """Parse date from various formats"""
    if pd.isna(date_value):
        return None
    if isinstance(date_value, str):
        try:
            # Handle DD-MM-YYYY format
            if '-' in date_value and len(date_value.split('-')) == 3:
                parts = date_value.split('-')
                if len(parts[0]) == 2:  # DD-MM-YYYY
                    return pd.to_datetime(date_value, format='%d-%m-%Y').strftime('%Y-%m-%d')
            return pd.to_datetime(date_value).strftime('%Y-%m-%d')
        except:
            return None
    if hasattr(date_value, 'strftime'):
        return date_value.strftime('%Y-%m-%d')
    return None

def safe_float(value, default=None):
    """Safely convert to float"""
    if pd.isna(value) or value == '' or str(value).strip() == '':
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

def parse_transactions(df):
    """Parse transactions from DataFrame"""
    transactions = []
    
    # Find columns (case-insensitive)
    date_col = None
    desc_col = None
    debit_col = None
    credit_col = None
    balance_col = None
    
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if 'date' in col_lower:
            date_col = col
        elif 'description' in col_lower or 'narration' in col_lower or 'particulars' in col_lower:
            desc_col = col
        elif 'debit' in col_lower:
            debit_col = col
        elif 'credit' in col_lower:
            credit_col = col
        elif 'balance' in col_lower or 'running' in col_lower:
            balance_col = col
    
    logger.info(f"Found columns - Date: {date_col}, Description: {desc_col}, Debit: {debit_col}, Credit: {credit_col}, Balance: {balance_col}")
    
    if not date_col:
        logger.warning(f"Date column not found. Available columns: {list(df.columns)}")
        return transactions
    
    for idx, row in df.iterrows():
        date = parse_date(row.get(date_col))
        if not date:
            continue
        
        debit = safe_float(row.get(debit_col), 0)
        credit = safe_float(row.get(credit_col), 0)
        balance = safe_float(row.get(balance_col))
        
        # Determine transaction type
        if debit and debit > 0:
            trans_type = "DEBIT"
            amount = debit
        elif credit and credit > 0:
            trans_type = "CREDIT"
            amount = credit
        else:
            continue  # Skip rows with no transaction
        
        transaction = {
            "date": date,
            "description": str(row.get(desc_col, "")).strip() if desc_col else "",
            "type": trans_type,
            "balance": balance
        }
        
        if trans_type == "DEBIT":
            transaction["debit"] = amount
            transaction["credit"] = None
        else:
            transaction["debit"] = None
            transaction["credit"] = amount
        
        transactions.append(transaction)
    
    return transactions

async def find_or_create_user_id(customer_name: str, db):
    """Find user_id from customer profile by name, or create one"""
    # Try to find existing customer profile
    customer = await db.customer_profiles.find_one({
        "full_name": {"$regex": customer_name, "$options": "i"}
    })
    
    if customer:
        user_id = customer.get("customer_id")
        logger.info(f"Found existing customer: {customer_name} -> {user_id}")
        return user_id
    
    # If not found, create a new customer_id
    user_id = f"user_{uuid.uuid4().hex[:12]}"
    logger.info(f"Created new user_id for {customer_name}: {user_id}")
    return user_id

def extract_account_info_from_csv(file_path):
    """Extract account information from CSV header rows"""
    account_info = {
        "account_number": None,
        "account_holder_name": None,
        "bank_name": None,
        "ifsc_code": None,
        "account_type": None,
        "opening_balance": None,
        "closing_balance": None,
        "statement_period_from": None,
        "statement_period_to": None
    }
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()[:15]  # Read first 15 lines
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Split by comma
                parts = [p.strip() for p in line.split(',')]
                if len(parts) < 2:
                    continue
                
                key = parts[0].lower()
                value = parts[1] if len(parts) > 1 else ""
                
                if 'account holder name' in key or 'account holder' in key:
                    account_info["account_holder_name"] = value
                elif 'account number' in key:
                    account_info["account_number"] = value
                elif 'bank name' in key:
                    account_info["bank_name"] = value
                elif 'account type' in key:
                    account_info["account_type"] = value
                elif 'opening balance' in key:
                    account_info["opening_balance"] = safe_float(value)
                elif 'closing balance' in key:
                    account_info["closing_balance"] = safe_float(value)
                elif 'statement period' in key:
                    # Parse period like "01-01-2025 to 30-06-2025"
                    period_str = value
                    if ' to ' in period_str:
                        dates = period_str.split(' to ')
                        if len(dates) == 2:
                            account_info["statement_period_from"] = parse_date(dates[0].strip())
                            account_info["statement_period_to"] = parse_date(dates[1].strip())
    
    except Exception as e:
        logger.warning(f"Error extracting account info from CSV: {e}")
    
    return account_info

async def process_csv_file(file_path: str, db):
    """Process CSV file and import transactions"""
    logger.info("Processing CSV file")
    
    # Extract account info from header
    account_info = extract_account_info_from_csv(file_path)
    
    # Read CSV, skip header rows (first 9 rows based on structure)
    df = pd.read_csv(file_path, skiprows=9, header=0)
    
    # Clean column names
    df.columns = [col.strip() for col in df.columns]
    
    customer_name = account_info.get("account_holder_name")
    if not customer_name:
        logger.error("Could not find account holder name in CSV")
        return
    
    # Get or create user_id
    user_id = await find_or_create_user_id(customer_name, db)
    
    # Use extracted account info
    account_number = account_info.get("account_number")
    account_holder_name = account_info.get("account_holder_name")
    bank_name = account_info.get("bank_name") or "Axis Bank"
    opening_balance = account_info.get("opening_balance")
    closing_balance = account_info.get("closing_balance")
    statement_period_from = account_info.get("statement_period_from")
    statement_period_to = account_info.get("statement_period_to")
    
    # Parse transactions
    transactions = parse_transactions(df)
    
    if not transactions:
        logger.warning(f"No transactions found for {customer_name}")
        return
    
    # Use transaction dates if period not found in header
    if not statement_period_from or not statement_period_to:
        dates = [t['date'] for t in transactions if t.get('date')]
        if dates:
            statement_period_from = min(dates)
            statement_period_to = max(dates)
    
    # Calculate minimum balance
    minimum_balance = None
    if transactions:
        balances = [t['balance'] for t in transactions if t.get('balance') is not None]
        if balances:
            minimum_balance = min(balances)
    
    # Create document record
    document_id = f"doc_{uuid.uuid4().hex[:12]}"
    
    document = {
        "document_id": document_id,
        "user_id": user_id,
        "application_id": None,
        "file_name": os.path.basename(file_path),
        "file_path": file_path,
        "file_type": "csv",
        "file_size": os.path.getsize(file_path),
        "mime_type": "text/csv",
        "document_type": "BANK_STATEMENT",
        "status": "COMPLETED",
        "expected_document_type": "BANK_STATEMENT",
        "uploaded_at": datetime.now(timezone.utc),
        "processed_at": datetime.now(timezone.utc),
        "extracted_data": {},
        "quality_score": None,
        "validation_warnings": [],
        "validation_errors": [],
        "has_type_mismatch": False,
        "metadata": {
            "customer_name": customer_name
        }
    }
    
    # Create extraction record
    extracted_fields = {
        "account_number": account_number,
        "account_holder_name": account_holder_name,
        "bank_name": bank_name,
        "statement_period_from": statement_period_from,
        "statement_period_to": statement_period_to,
        "opening_balance": opening_balance,
        "closing_balance": closing_balance,
        "minimum_balance": minimum_balance,
        "transactions": transactions,
        "ifsc_code": None,
        "branch_name": None
    }
    
    extraction_record = {
        "document_id": document_id,
        "user_id": user_id,
        "document_type": "BANK_STATEMENT",
        "extracted_fields": extracted_fields,
        "extraction_timestamp": datetime.now(timezone.utc),
        "version": "1.0"
    }
    
    # Update document with extracted data
    document["extracted_data"] = extracted_fields
    
    # Insert document and extraction records
    await db.documents.insert_one(document)
    await db.extraction_results.insert_one(extraction_record)
    
    # Store each transaction in bank_transaction_record collection
    transaction_records = []
    for idx, transaction in enumerate(transactions):
        transaction_id = f"txn_{uuid.uuid4().hex[:12]}"
        
        transaction_record = {
            "transaction_id": transaction_id,
            "document_id": document_id,
            "user_id": user_id,
            "account_number": account_number,
            "account_holder_name": account_holder_name,
            "bank_name": bank_name,
            "transaction_date": transaction.get("date"),
            "description": transaction.get("description"),
            "transaction_type": transaction.get("type"),
            "debit_amount": transaction.get("debit"),
            "credit_amount": transaction.get("credit"),
            "balance_after_transaction": transaction.get("balance"),
            "ifsc_code": None,
            "branch_name": None,
            "statement_period_from": statement_period_from,
            "statement_period_to": statement_period_to,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "metadata": {
                "transaction_index": idx,
                "customer_name": customer_name
            }
        }
        transaction_records.append(transaction_record)
    
    # Bulk insert all transactions
    if transaction_records:
        await db.bank_transaction_record.insert_many(transaction_records)
        logger.info(f"Inserted {len(transaction_records)} transactions into bank_transaction_record collection")
    
    logger.info(f"Imported bank statement for {customer_name}: {document_id}")
    logger.info(f"  - Transactions: {len(transactions)}")
    logger.info(f"  - Period: {statement_period_from} to {statement_period_to}")
    logger.info(f"  - Balance: {opening_balance} to {closing_balance}")

def find_header_row(df):
    """Find the row index that contains column headers (Date, Description, etc.)"""
    header_keywords = ['date', 'description', 'debit', 'credit', 'balance']
    
    for idx in range(min(20, len(df))):  # Check first 20 rows
        row_values = [str(val).lower().strip() for val in df.iloc[idx].values if pd.notna(val)]
        # Check if this row contains multiple header keywords
        matches = sum(1 for keyword in header_keywords if any(keyword in val for val in row_values))
        if matches >= 3:  # At least 3 header keywords found
            return idx
    return None

def extract_account_info_from_excel(df, header_row_idx):
    """Extract account information from rows before the header row"""
    account_info = {
        "account_number": None,
        "account_holder_name": None,
        "bank_name": "Axis Bank",
        "ifsc_code": None,
        "account_type": None,
        "opening_balance": None,
        "closing_balance": None,
        "statement_period_from": None,
        "statement_period_to": None
    }
    
    if header_row_idx is None:
        header_row_idx = len(df)
    
    # Search in rows before the header
    # When reading with header=None, columns are numeric (0, 1, 2, etc.)
    for idx in range(min(header_row_idx, len(df))):
        # Check all columns in this row
        for col_idx in range(len(df.columns)):
            cell_value = str(df.iloc[idx, col_idx]).strip() if pd.notna(df.iloc[idx, col_idx]) else ""
            cell_lower = cell_value.lower()
            
            # Get the value in the next column (usually the actual value)
            # In Excel format, label is in col 0, value is in col 1
            if col_idx == 0 and len(df.columns) > 1:
                next_value = str(df.iloc[idx, 1]).strip() if pd.notna(df.iloc[idx, 1]) else ""
            else:
                next_value = ""
            
            if 'account holder name' in cell_lower or 'account holder' in cell_lower:
                account_info["account_holder_name"] = next_value if next_value else cell_value
            elif 'account number' in cell_lower:
                account_info["account_number"] = next_value if next_value else cell_value
            elif 'bank name' in cell_lower:
                account_info["bank_name"] = next_value if next_value else cell_value
            elif 'ifsc' in cell_lower:
                account_info["ifsc_code"] = next_value if next_value else cell_value
            elif 'account type' in cell_lower:
                account_info["account_type"] = next_value if next_value else cell_value
            elif 'opening balance' in cell_lower:
                account_info["opening_balance"] = safe_float(next_value if next_value else cell_value)
            elif 'closing balance' in cell_lower:
                account_info["closing_balance"] = safe_float(next_value if next_value else cell_value)
            elif 'statement period' in cell_lower:
                period_str = next_value if next_value else cell_value
                if ' to ' in period_str:
                    dates = period_str.split(' to ')
                    if len(dates) == 2:
                        account_info["statement_period_from"] = parse_date(dates[0].strip())
                        account_info["statement_period_to"] = parse_date(dates[1].strip())
    
    return account_info

async def process_excel_file(file_path: str, db):
    """Process Excel file and import transactions"""
    logger.info("Processing Excel file")
    excel_file = pd.ExcelFile(file_path)
    
    customer_mapping = {
        "Rajesh Kumar": None,
        "Omnik Nema": None
    }
    
    # Process each sheet
    for sheet_name in excel_file.sheet_names:
        logger.info(f"Processing sheet: {sheet_name}")
        
        # First, read without header to find the header row
        df_raw = pd.read_excel(file_path, sheet_name=sheet_name, header=None)
        
        # Find the header row
        header_row_idx = find_header_row(df_raw)
        
        if header_row_idx is None:
            logger.warning(f"Could not find header row in sheet: {sheet_name}")
            logger.warning(f"Available columns: {list(df_raw.columns)}")
            continue
        
        logger.info(f"Found header row at index: {header_row_idx}")
        
        # Extract account information from rows before header
        account_info = extract_account_info_from_excel(df_raw, header_row_idx)
        
        # Now read the file with the correct header row
        df = pd.read_excel(file_path, sheet_name=sheet_name, header=header_row_idx, skiprows=0)
        
        # Clean column names
        df.columns = [str(col).strip() for col in df.columns]
        
        # Get customer name from account info or sheet name
        customer_name = account_info.get("account_holder_name")
        if not customer_name:
            # Try to identify customer from sheet name
            for name in customer_mapping.keys():
                if name.lower() in sheet_name.lower():
                    customer_name = name
                    break
            
            if not customer_name:
                customer_name = sheet_name.strip()
        
        # Get or create user_id
        user_id = await find_or_create_user_id(customer_name, db)
        
        # Use extracted account information
        account_number = account_info.get("account_number")
        account_holder_name = account_info.get("account_holder_name") or customer_name
        bank_name = account_info.get("bank_name") or "Axis Bank"
        ifsc_code = account_info.get("ifsc_code")
        opening_balance = account_info.get("opening_balance")
        closing_balance = account_info.get("closing_balance")
        statement_period_from = account_info.get("statement_period_from")
        statement_period_to = account_info.get("statement_period_to")
        
        # Parse transactions
        transactions = parse_transactions(df)
        
        if not transactions:
            logger.warning(f"No transactions found for {customer_name}")
            continue
        
        # Use transaction dates if period not found in header
        if not statement_period_from or not statement_period_to:
            dates = [t['date'] for t in transactions if t.get('date')]
            if dates:
                statement_period_from = min(dates)
                statement_period_to = max(dates)
        
        # Calculate balances if not found in header
        minimum_balance = None
        if transactions:
            balances = [t['balance'] for t in transactions if t.get('balance') is not None]
            if balances:
                if not opening_balance:
                    opening_balance = balances[0] if len(balances) > 0 else None
                if not closing_balance:
                    closing_balance = balances[-1] if len(balances) > 0 else None
                minimum_balance = min(balances) if balances else None
        
        # Create document record
        document_id = f"doc_{uuid.uuid4().hex[:12]}"
        
        document = {
            "document_id": document_id,
            "user_id": user_id,
            "application_id": None,
            "file_name": f"Axis_Bank_Statement_{customer_name.replace(' ', '_')}.xlsx",
            "file_path": file_path,
            "file_type": "xlsx",
            "file_size": os.path.getsize(file_path),
            "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "document_type": "BANK_STATEMENT",
            "status": "COMPLETED",
            "expected_document_type": "BANK_STATEMENT",
            "uploaded_at": datetime.now(timezone.utc),
            "processed_at": datetime.now(timezone.utc),
            "extracted_data": {},
            "quality_score": None,
            "validation_warnings": [],
            "validation_errors": [],
            "has_type_mismatch": False,
            "metadata": {
                "sheet_name": sheet_name,
                "customer_name": customer_name
            }
        }
        
        # Create extraction record
        extracted_fields = {
            "account_number": account_number,
            "account_holder_name": account_holder_name,
            "bank_name": bank_name,
            "statement_period_from": statement_period_from,
            "statement_period_to": statement_period_to,
            "opening_balance": opening_balance,
            "closing_balance": closing_balance,
            "minimum_balance": minimum_balance,
            "transactions": transactions,
            "ifsc_code": ifsc_code,
            "branch_name": None
        }
        
        extraction_record = {
            "document_id": document_id,
            "user_id": user_id,
            "document_type": "BANK_STATEMENT",
            "extracted_fields": extracted_fields,
            "extraction_timestamp": datetime.now(timezone.utc),
            "version": "1.0"
        }
        
        # Update document with extracted data
        document["extracted_data"] = extracted_fields
        
        # Insert document and extraction records
        await db.documents.insert_one(document)
        await db.extraction_results.insert_one(extraction_record)
        
        # Store each transaction in bank_transaction_record collection
        transaction_records = []
        for idx, transaction in enumerate(transactions):
            transaction_id = f"txn_{uuid.uuid4().hex[:12]}"
            
            transaction_record = {
                "transaction_id": transaction_id,
                "document_id": document_id,
                "user_id": user_id,
                "account_number": account_number,
                "account_holder_name": account_holder_name,
                "bank_name": bank_name,
                "transaction_date": transaction.get("date"),
                "description": transaction.get("description"),
                "transaction_type": transaction.get("type"),
                "debit_amount": transaction.get("debit"),
                "credit_amount": transaction.get("credit"),
                "balance_after_transaction": transaction.get("balance"),
                "ifsc_code": ifsc_code,
                "branch_name": None,
                "statement_period_from": statement_period_from,
                "statement_period_to": statement_period_to,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
                "metadata": {
                    "transaction_index": idx,
                    "sheet_name": sheet_name,
                    "customer_name": customer_name
                }
            }
            transaction_records.append(transaction_record)
        
        # Bulk insert all transactions
        if transaction_records:
            await db.bank_transaction_record.insert_many(transaction_records)
            logger.info(f"Inserted {len(transaction_records)} transactions into bank_transaction_record collection")
        
        logger.info(f"Imported bank statement for {customer_name}: {document_id}")
        logger.info(f"  - Transactions: {len(transactions)}")
        logger.info(f"  - Period: {statement_period_from} to {statement_period_to}")
        logger.info(f"  - Balance: {opening_balance} to {closing_balance}")

async def import_bank_statements(file_path: str, db):
    """Import bank statements from CSV or Excel file and store transactions in bank_transaction_record collection"""
    try:
        file_ext = os.path.splitext(file_path)[1].lower()
        
        if file_ext == '.csv':
            await process_csv_file(file_path, db)
        elif file_ext in ['.xlsx', '.xls']:
            await process_excel_file(file_path, db)
        else:
            logger.error(f"Unsupported file format: {file_ext}")
            return
        
        logger.info("Successfully imported bank statements from file")
        
    except Exception as e:
        logger.error(f"Import failed: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Look for specific files
    omnik_csv = os.path.join(backend_dir, "Omnik_Bank_Statement_Jan_Jun_2025.csv")
    rajesh_excel = os.path.join(backend_dir, "Rajesh_Bank_Statement.xlsx")
    
    # Fallback to old file names
    old_csv = os.path.join(backend_dir, "Axis_Bank_Statement_Jan_Jun_2025.csv")
    old_excel = os.path.join(backend_dir, "Axis_Bank_Statement_Jan_Jun_2025.xlsx")
    
    files_to_process = []
    
    # Check for Omnik CSV
    if os.path.exists(omnik_csv):
        logger.info(f"Found Omnik CSV file: {os.path.basename(omnik_csv)}")
        files_to_process.append(omnik_csv)
    elif os.path.exists(old_csv):
        logger.info(f"Found CSV file: {os.path.basename(old_csv)}")
        files_to_process.append(old_csv)
    
    # Check for Rajesh Excel
    if os.path.exists(rajesh_excel):
        logger.info(f"Found Rajesh Excel file: {os.path.basename(rajesh_excel)}")
        files_to_process.append(rajesh_excel)
    elif os.path.exists(old_excel):
        logger.info(f"Found Excel file: {os.path.basename(old_excel)}")
        files_to_process.append(old_excel)
    
    if not files_to_process:
        logger.error("No bank statement files found. Checked:")
        logger.error(f"  - {omnik_csv}")
        logger.error(f"  - {rajesh_excel}")
        logger.error(f"  - {old_csv}")
        logger.error(f"  - {old_excel}")
        sys.exit(1)
    
    async def process_all_files():
        # Initialize database connection once for all files
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        db = client[settings.MONGODB_DB_NAME]
        
        try:
            # Create indexes once
            await db.bank_transaction_record.create_index("transaction_id", unique=True)
            await db.bank_transaction_record.create_index("document_id")
            await db.bank_transaction_record.create_index("user_id")
            await db.bank_transaction_record.create_index("account_number")
            await db.bank_transaction_record.create_index("transaction_date")
            logger.info("Created indexes for bank_transaction_record collection")
            
            # Process all files
            success_count = 0
            for file_path in files_to_process:
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing: {os.path.basename(file_path)}")
                logger.info(f"{'='*60}")
                try:
                    await import_bank_statements(file_path, db)
                    success_count += 1
                except Exception as e:
                    logger.error(f"Failed to process {os.path.basename(file_path)}: {e}", exc_info=True)
                    continue
            
            logger.info("\n" + "="*60)
            logger.info(f"Batch import completed! Successfully processed {success_count}/{len(files_to_process)} file(s)")
            logger.info("="*60)
        finally:
            client.close()
    
    asyncio.run(process_all_files())
