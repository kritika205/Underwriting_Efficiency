"""
Script to verify extraction results data integrity

This script checks:
1. All extraction results have user_id
2. All extraction results have valid document_id references
3. Statistics about extraction results
"""
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from app.core.config import settings
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_extraction_data():
    """Verify extraction results data integrity"""
    try:
        # Connect to MongoDB
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        db = client[settings.MONGODB_DB_NAME]
        
        logger.info("Verifying extraction results data integrity...")
        
        # Count total extraction results
        total_count = await db.extraction_results.count_documents({})
        logger.info(f"Total extraction results: {total_count}")
        
        # Count extraction results with user_id
        with_user_id = await db.extraction_results.count_documents({"user_id": {"$exists": True, "$ne": None}})
        logger.info(f"Extraction results with user_id: {with_user_id}")
        
        # Count extraction results without user_id
        without_user_id = await db.extraction_results.count_documents({"user_id": {"$exists": False}})
        without_user_id += await db.extraction_results.count_documents({"user_id": None})
        logger.info(f"Extraction results without user_id: {without_user_id}")
        
        # Group by user_id
        pipeline = [
            {"$match": {"user_id": {"$exists": True, "$ne": None}}},
            {"$group": {
                "_id": "$user_id",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        
        user_stats = await db.extraction_results.aggregate(pipeline).to_list(length=None)
        logger.info(f"\nExtraction results by user:")
        for stat in user_stats[:10]:  # Show top 10
            logger.info(f"  {stat['_id']}: {stat['count']} extractions")
        
        # Group by document type
        pipeline = [
            {"$group": {
                "_id": "$document_type",
                "count": {"$sum": 1}
            }},
            {"$sort": {"count": -1}}
        ]
        
        type_stats = await db.extraction_results.aggregate(pipeline).to_list(length=None)
        logger.info(f"\nExtraction results by document type:")
        for stat in type_stats:
            logger.info(f"  {stat['_id']}: {stat['count']} extractions")
        
        # Check for orphaned extraction results (document doesn't exist)
        orphaned = []
        extraction_results = await db.extraction_results.find({}).to_list(length=None)
        for extraction in extraction_results:
            document_id = extraction.get("document_id")
            if document_id:
                doc = await db.documents.find_one({"document_id": document_id})
                if not doc:
                    orphaned.append(extraction.get("_id"))
        
        if orphaned:
            logger.warning(f"\nFound {len(orphaned)} orphaned extraction results (document not found)")
        else:
            logger.info(f"\nAll extraction results have valid document references")
        
        # Summary
        logger.info(f"\n=== Summary ===")
        logger.info(f"Total: {total_count}")
        logger.info(f"With user_id: {with_user_id} ({with_user_id/total_count*100:.1f}%)" if total_count > 0 else "With user_id: 0")
        logger.info(f"Without user_id: {without_user_id}")
        logger.info(f"Orphaned: {len(orphaned)}")
        
        # Close connection
        client.close()
        
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(verify_extraction_data())

