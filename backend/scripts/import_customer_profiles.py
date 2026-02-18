"""
Script to import customer profiles from CSV to MongoDB
"""
import sys
import os

# Add parent directory to path BEFORE other imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import csv
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from app.models.customer import CustomerProfile
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def safe_float(value, default=None):
    """Safely convert value to float, handling NULL and empty strings"""
    if not value:
        return default
    value_str = str(value).strip().upper()
    if value_str == '' or value_str == 'NULL':
        return default
    try:
        return float(value_str)
    except (ValueError, TypeError):
        return default

async def import_customer_profiles(csv_file_path: str):
    """Import customer profiles from CSV file"""
    try:
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        db = client[settings.MONGODB_DB_NAME]
        
        # Read CSV file
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            
            imported = 0
            for row in reader:
                try:
                    # Helper function to safely get and clean values
                    def get_value(key, default=None):
                        val = row.get(key, "").strip()
                        if not val or val.upper() == "NULL":
                            return default
                        return val if val else default
                    
                    # Clean up the row data
                    customer_data = {
                        "customer_id": row.get("Customer ID", "").strip(),
                        "full_name": row.get("Full Name", "").strip(),
                        "father_name": get_value("Father's Name"),
                        "gender": get_value("Gender"),
                        "date_of_birth": get_value("Date of Birth"),
                        "mobile_number": get_value("Mobile number"),
                        "pan_number": get_value("Pan Number"),
                        "aadhar_number": get_value("Aadhar Number"),
                        "address": get_value("Address"),
                        "city": get_value("City"),
                        "state": get_value("State"),
                        "pincode": get_value("Pincode"),
                        "dl_number": get_value("DL Number"),
                        "passport_number": get_value("Passport Number"),
                        "cibil_score": safe_float(row.get("Cibil Score")),
                        "existing_loan": get_value("Exisiting Loan"),
                        "employment_type": get_value("Employment Type"),
                        "employer_name": get_value("Employer Name"),
                        "monthly_salary": safe_float(row.get("Monthly Salary")),
                        "gst_number": get_value("GST Number"),
                        "annual_turnover": safe_float(row.get("Annual Turnover")),
                        "kyc_status": get_value("KYC Status"),
                        "created_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    }
                    
                    # Skip empty rows
                    if not customer_data["customer_id"]:
                        continue
                    
                    # Create customer profile
                    customer = CustomerProfile(**customer_data)
                    
                    # Upsert (update if exists, insert if not)
                    await db.customer_profiles.update_one(
                        {"customer_id": customer.customer_id},
                        {"$set": customer.model_dump()},
                        upsert=True
                    )
                    
                    imported += 1
                    logger.info(f"Imported customer: {customer.customer_id} - {customer.full_name}")
                    
                except Exception as e:
                    logger.error(f"Error importing row: {e}")
                    continue
        
        logger.info(f"Successfully imported {imported} customer profiles")
        
        # Create indexes
        await db.customer_profiles.create_index("customer_id", unique=True)
        await db.customer_profiles.create_index("pan_number")
        await db.customer_profiles.create_index("aadhar_number")
        logger.info("Created indexes on customer_profiles collection")
        
        client.close()
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
        raise

if __name__ == "__main__":
    csv_path = os.path.join(os.path.dirname(__file__), "..", "Sample_db(Sheet1).csv")
    csv_path = os.path.abspath(csv_path)
    asyncio.run(import_customer_profiles(csv_path))

