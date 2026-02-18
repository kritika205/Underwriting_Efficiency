"""
Script to cross-validate all extracted documents against customer datasheet
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.services.cross_validation_service import cross_validation_service
from app.core.database import init_db, close_db

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    """Run cross-validation on all documents"""
    try:
        await init_db()
        logger.info("Starting cross-validation of all documents...")
        result = await cross_validation_service.cross_validate_all_documents()
        
        logger.info(f"\n=== Cross-Validation Summary ===")
        logger.info(f"Total documents validated: {result['summary']['total']}")
        logger.info(f"Passed (score >= 80): {result['summary']['passed']}")
        logger.info(f"Warnings (50-79): {result['summary']['warnings']}")
        logger.info(f"Errors (score < 50): {result['summary']['errors']}")
        logger.info(f"Average validation score: {result['summary']['average_score']:.2f}")
        
        # Show documents with issues
        issues = [v for v in result['validations'] if v.get('validation_score', 0) < 80]
        if issues:
            logger.info(f"\n=== Documents with Issues ({len(issues)}) ===")
            for issue in issues[:10]:  # Show top 10
                logger.info(f"Document: {issue['document_id']}")
                logger.info(f"  Score: {issue['validation_score']:.2f}")
                logger.info(f"  Customer: {issue.get('customer_name', 'N/A')}")
                if issue.get('mismatches'):
                    logger.info(f"  Mismatches: {len(issue['mismatches'])}")
                    for mismatch in issue['mismatches'][:3]:
                        logger.info(f"    - {mismatch['field']}: '{mismatch['extracted_value']}' vs '{mismatch['profile_value']}'")
        
    except Exception as e:
        logger.error(f"Cross-validation failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())


