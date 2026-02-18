"""
MongoDB Database Connection
"""
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None

database = Database()

async def get_database():
    """Get database instance"""
    return database.client[settings.MONGODB_DB_NAME]

async def init_db():
    """Initialize database connection"""
    try:
        database.client = AsyncIOMotorClient(settings.MONGODB_URL)
        # Test connection
        await database.client.admin.command('ping')
        logger.info("Connected to MongoDB")
        
        # Create indexes
        db = database.client[settings.MONGODB_DB_NAME]
        
        # Documents collection indexes
        await db.documents.create_index("document_id", unique=True)
        await db.documents.create_index("user_id")
        await db.documents.create_index("status")
        await db.documents.create_index("document_type")
        await db.documents.create_index("uploaded_at")
        
        # Users collection indexes
        await db.users.create_index("user_id", unique=True)
        await db.users.create_index("email", unique=True)
        
        # Extraction results indexes
        await db.extraction_results.create_index("document_id")
        await db.extraction_results.create_index("user_id")
        await db.extraction_results.create_index("document_type")
        
        # User document aggregations indexes
        await db.user_document_aggregations.create_index("user_id", unique=True)
        await db.user_document_aggregations.create_index("last_updated")
        
        # Customer profiles indexes
        await db.customer_profiles.create_index("customer_id", unique=True)
        await db.customer_profiles.create_index("pan_number")
        await db.customer_profiles.create_index("aadhar_number")
        
        # Risk analyses indexes
        await db.risk_analyses.create_index("document_id")
        await db.risk_analyses.create_index("user_id")
        await db.risk_analyses.create_index("risk_level")
        await db.risk_analyses.create_index("analysis_timestamp")
        
        # Bank transaction record indexes
        await db.bank_transaction_record.create_index("transaction_id", unique=True)
        await db.bank_transaction_record.create_index("document_id")
        await db.bank_transaction_record.create_index("user_id")
        await db.bank_transaction_record.create_index("account_number")
        await db.bank_transaction_record.create_index("transaction_date")
        
        # Admins collection indexes
        await db.admins.create_index("admin_id", unique=True)
        await db.admins.create_index("email", unique=True)
        
        logger.info("Database indexes created")
        
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise

async def close_db():
    """Close database connection"""
    if database.client:
        database.client.close()
        logger.info("Disconnected from MongoDB")





