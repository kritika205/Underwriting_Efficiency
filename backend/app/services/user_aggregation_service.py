"""
Service for managing user document aggregations
"""
from app.core.database import get_database
from app.models.extraction import UserDocumentAggregation, DocumentExtractionDetail
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class UserAggregationService:
    """Service for managing user document aggregations"""
    
    async def update_user_aggregation(
        self,
        user_id: str,
        document_id: str,
        document_type: str,
        extracted_fields: Dict[str, Any]
    ):
        """
        Update or create user document aggregation with new extraction data
        Only stores extracted_fields and document_type
        """
        try:
            db = await get_database()
            
            # Get existing aggregation or create new one
            existing = await db.user_document_aggregations.find_one({"user_id": user_id})
            
            # Create document extraction detail - only extracted_fields and document_type
            doc_detail = DocumentExtractionDetail(
                document_id=document_id,
                document_type=document_type,
                extracted_fields=extracted_fields
            )
            
            if existing:
                # Update existing aggregation
                documents = existing.get("documents", {})
                documents_by_type = existing.get("documents_by_type", {})
                
                # Update or add document
                documents[document_id] = doc_detail.model_dump()
                
                # Update documents_by_type
                if document_type not in documents_by_type:
                    documents_by_type[document_type] = []
                
                if document_id not in documents_by_type[document_type]:
                    documents_by_type[document_type].append(document_id)
                
                # Update aggregation
                await db.user_document_aggregations.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "documents": documents,
                            "documents_by_type": documents_by_type,
                            "total_documents": len(documents),
                            "last_updated": datetime.now(timezone.utc)
                        }
                    }
                )
                logger.info(f"Updated user aggregation for user_id: {user_id}, document_id: {document_id}")
            else:
                # Create new aggregation
                aggregation = UserDocumentAggregation(
                    user_id=user_id,
                    documents={document_id: doc_detail.model_dump()},
                    documents_by_type={document_type: [document_id]},
                    total_documents=1
                )
                await db.user_document_aggregations.insert_one(aggregation.model_dump())
                logger.info(f"Created new user aggregation for user_id: {user_id}, document_id: {document_id}")
            
        except Exception as e:
            logger.error(f"Failed to update user aggregation: {e}")
            raise
    
    async def get_user_aggregation(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get user document aggregation
        """
        try:
            db = await get_database()
            aggregation = await db.user_document_aggregations.find_one({"user_id": user_id})
            
            if aggregation:
                aggregation.pop("_id", None)
                return aggregation
            
            return None
        except Exception as e:
            logger.error(f"Failed to get user aggregation: {e}")
            raise
    
    async def remove_document_from_aggregation(self, user_id: str, document_id: str):
        """
        Remove a document from user aggregation
        """
        try:
            db = await get_database()
            existing = await db.user_document_aggregations.find_one({"user_id": user_id})
            
            if existing:
                documents = existing.get("documents", {})
                documents_by_type = existing.get("documents_by_type", {})
                
                # Get document type before removing
                doc_type = None
                if document_id in documents:
                    doc_type = documents[document_id].get("document_type")
                    del documents[document_id]
                
                # Remove from documents_by_type
                if doc_type and doc_type in documents_by_type:
                    if document_id in documents_by_type[doc_type]:
                        documents_by_type[doc_type].remove(document_id)
                    # Remove document type if empty
                    if not documents_by_type[doc_type]:
                        del documents_by_type[doc_type]
                
                # Update aggregation
                await db.user_document_aggregations.update_one(
                    {"user_id": user_id},
                    {
                        "$set": {
                            "documents": documents,
                            "documents_by_type": documents_by_type,
                            "total_documents": len(documents),
                            "last_updated": datetime.now(timezone.utc)
                        }
                    }
                )
                logger.info(f"Removed document {document_id} from user aggregation for user_id: {user_id}")
        except Exception as e:
            logger.error(f"Failed to remove document from aggregation: {e}")
            raise


# Create singleton instance
user_aggregation_service = UserAggregationService()

