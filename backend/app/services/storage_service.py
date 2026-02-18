"""
File Storage Service
"""
import os
import aiofiles
import shutil
from pathlib import Path
from typing import BinaryIO
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

class StorageService:
    """Handles file storage operations"""
    
    def __init__(self):
        self.use_azure = settings.USE_AZURE_STORAGE
        self.local_path = Path(settings.LOCAL_STORAGE_PATH)
        self.local_path.mkdir(parents=True, exist_ok=True)
    
    async def save_file(
        self, 
        file_content: bytes, 
        user_id: str, 
        document_id: str, 
        filename: str,
        subfolder: str = "original"
    ) -> str:
        """
        Save file to storage
        
        Args:
            file_content: File bytes
            user_id: User identifier
            document_id: Document identifier
            filename: Original filename
            subfolder: Subfolder (original/processed)
        
        Returns:
            File path
        """
        if self.use_azure:
            return await self._save_to_azure(file_content, user_id, document_id, filename, subfolder)
        else:
            return await self._save_to_local(file_content, user_id, document_id, filename, subfolder)
    
    async def _save_to_local(
        self,
        file_content: bytes,
        user_id: str,
        document_id: str,
        filename: str,
        subfolder: str
    ) -> str:
        """Save file to local filesystem"""
        file_dir = self.local_path / user_id / document_id / subfolder
        file_dir.mkdir(parents=True, exist_ok=True)
        
        file_path = file_dir / filename
        
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(file_content)
        
        return str(file_path.relative_to(self.local_path))
    
    async def _save_to_azure(
        self,
        file_content: bytes,
        user_id: str,
        document_id: str,
        filename: str,
        subfolder: str
    ) -> str:
        """Save file to Azure Blob Storage"""
        try:
            from azure.storage.blob import BlobServiceClient
            
            blob_service_client = BlobServiceClient.from_connection_string(
                settings.AZURE_STORAGE_CONNECTION_STRING
            )
            
            blob_path = f"{user_id}/{document_id}/{subfolder}/{filename}"
            blob_client = blob_service_client.get_blob_client(
                container=settings.AZURE_STORAGE_CONTAINER,
                blob=blob_path
            )
            
            blob_client.upload_blob(file_content, overwrite=True)
            
            return blob_path
        except Exception as e:
            logger.error(f"Failed to save to Azure: {e}")
            # Fallback to local storage
            return await self._save_to_local(file_content, user_id, document_id, filename, subfolder)
    
    async def read_file(self, file_path: str) -> bytes:
        """Read file from storage"""
        if self.use_azure:
            return await self._read_from_azure(file_path)
        else:
            return await self._read_from_local(file_path)
    
    async def _read_from_local(self, file_path: str) -> bytes:
        """Read file from local filesystem"""
        full_path = self.local_path / file_path
        async with aiofiles.open(full_path, 'rb') as f:
            return await f.read()
    
    async def _read_from_azure(self, file_path: str) -> bytes:
        """Read file from Azure Blob Storage"""
        try:
            from azure.storage.blob import BlobServiceClient
            
            blob_service_client = BlobServiceClient.from_connection_string(
                settings.AZURE_STORAGE_CONNECTION_STRING
            )
            
            blob_client = blob_service_client.get_blob_client(
                container=settings.AZURE_STORAGE_CONTAINER,
                blob=file_path
            )
            
            return await blob_client.download_blob().readall()
        except Exception as e:
            logger.error(f"Failed to read from Azure: {e}")
            raise
    
    async def delete_file(self, file_path: str) -> bool:
        """Delete file from storage"""
        if self.use_azure:
            return await self._delete_from_azure(file_path)
        else:
            return await self._delete_from_local(file_path)
    
    async def delete_file_and_directory(self, file_path: str) -> bool:
        """Delete file and its parent directory structure (entire document folder)"""
        if self.use_azure:
            return await self._delete_from_azure(file_path)
        else:
            return await self._delete_from_local_directory(file_path)
    
    async def _delete_from_local(self, file_path: str) -> bool:
        """Delete file from local filesystem"""
        try:
            full_path = self.local_path / file_path
            if full_path.exists():
                full_path.unlink()
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete local file: {e}")
            return False
    
    async def _delete_from_azure(self, file_path: str) -> bool:
        """Delete file from Azure Blob Storage"""
        try:
            from azure.storage.blob import BlobServiceClient
            
            blob_service_client = BlobServiceClient.from_connection_string(
                settings.AZURE_STORAGE_CONNECTION_STRING
            )
            
            blob_client = blob_service_client.get_blob_client(
                container=settings.AZURE_STORAGE_CONTAINER,
                blob=file_path
            )
            
            blob_client.delete_blob()
            return True
        except Exception as e:
            logger.error(f"Failed to delete Azure file: {e}")
            return False
    
    async def _delete_from_local_directory(self, file_path: str) -> bool:
        """Delete file and entire document directory from local filesystem"""
        try:
            full_path = self.local_path / file_path
            
            if full_path.exists():
                # Delete the file if it's a file
                if full_path.is_file():
                    full_path.unlink()
                
                # Delete the document directory (e.g., user_id/document_id/)
                # Go up to the document_id directory level
                # Path structure: user_id/document_id/original/filename
                # We want to delete: user_id/document_id/
                document_dir = full_path.parent.parent  # Goes from original/filename to document_id
                if document_dir.exists() and document_dir.is_dir():
                    shutil.rmtree(document_dir)
                    return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete local file/directory: {e}")
            return False

storage_service = StorageService()






