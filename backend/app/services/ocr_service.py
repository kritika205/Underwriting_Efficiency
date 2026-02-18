"""
Azure OpenAI Vision OCR Service
"""
import base64
import io
from typing import Optional, Dict, Any
from openai import AzureOpenAI
from app.core.config import settings
from app.services.storage_service import storage_service
import logging

logger = logging.getLogger(__name__)

class OCRService:
    """Azure OpenAI Vision OCR Service"""
    
    def __init__(self):
        self.client = AzureOpenAI(
            api_key=settings.AZURE_OPENAI_API_KEY,
            api_version=settings.AZURE_OPENAI_API_VERSION,
            azure_endpoint=settings.AZURE_OPENAI_ENDPOINT
        )
        self.deployment_name = settings.AZURE_OPENAI_DEPLOYMENT_NAME
    
    async def extract_text(
        self, 
        file_path: str, 
        prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extract text from document using Azure OpenAI Vision
        
        Args:
            file_path: Path to document file
            prompt: Optional custom prompt
        
        Returns:
            Dictionary with extracted text and metadata
        """
        try:
            logger.info(f"Starting OCR extraction for file: {file_path}")
            
            # Read file
            file_content = await storage_service.read_file(file_path)
            logger.info(f"File read successfully, size: {len(file_content)} bytes")
            
            # Determine MIME type
            mime_type = self._get_mime_type(file_path)
            logger.info(f"Detected MIME type: {mime_type}")
            
            # Handle PDF files - convert to image
            if mime_type == 'application/pdf':
                logger.info("Converting PDF to image for Azure OpenAI Vision")
                # Convert PDF first page to image
                image_data = await self._pdf_to_image(file_content)
                base64_image = base64.b64encode(image_data).decode('utf-8')
                mime_type = 'image/png'  # PDF converted to PNG
                logger.info(f"PDF converted to PNG, base64 size: {len(base64_image)} chars")
            else:
                # For image files, use as-is
                base64_image = base64.b64encode(file_content).decode('utf-8')
                logger.info(f"Image encoded to base64, size: {len(base64_image)} chars")
            
            # Default prompt if not provided
            if not prompt:
                prompt = """Extract all text from this document. 
                Preserve the structure and formatting as much as possible.
                Include all numbers, dates, names, addresses, and other relevant information.
                Return the extracted text in a clear, structured format."""
            
            # Prepare messages with proper data URL format
            image_url = f"data:{mime_type};base64,{base64_image}"
            logger.info(f"Prepared image URL, total length: {len(image_url)} chars")
            
            messages = [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_url
                            }
                        }
                    ]
                }
            ]
            
            logger.info(f"Calling Azure OpenAI with model: {self.deployment_name}")
            
            # OPTIMIZATION: Optimize token usage for better performance
            # Call Azure OpenAI with optimized parameters
            response = self.client.chat.completions.create(
                model=self.deployment_name,
                messages=messages,
                max_tokens=2000,  # Reduced from 4000 - most documents don't need 4000 tokens
                temperature=0.0,  # Changed from 0.1 to 0.0 for more deterministic results
                top_p=0.95  # Add top_p for better performance
            )
            
            extracted_text = response.choices[0].message.content
            logger.info(f"OCR extraction successful, extracted text length: {len(extracted_text)} chars")
            
            return {
                "text": extracted_text,
                "model": self.deployment_name,
                "tokens_used": response.usage.total_tokens,
                "confidence": 0.95  # Azure OpenAI doesn't provide confidence, using default
            }
            
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}", exc_info=True)
            raise Exception(f"OCR extraction failed: {str(e)}")
    
    async def _pdf_to_image(self, pdf_content: bytes) -> bytes:
        """Convert PDF first page to PNG image using PyMuPDF"""
        try:
            import fitz  # PyMuPDF
            
            # Open PDF from bytes
            pdf_document = fitz.open(stream=pdf_content, filetype="pdf")
            
            if len(pdf_document) == 0:
                raise Exception("PDF has no pages")
            
            # Get first page
            page = pdf_document[0]
            
            # Render page to image with 2x zoom for better quality
            matrix = fitz.Matrix(2, 2)  # 2x zoom
            pix = page.get_pixmap(matrix=matrix)
            
            # Convert to PNG bytes
            img_bytes = pix.tobytes("png")
            
            # Clean up
            pdf_document.close()
            
            return img_bytes
            
        except ImportError:
            raise Exception("PyMuPDF (fitz) is required for PDF processing. Install with: pip install PyMuPDF")
        except Exception as e:
            logger.error(f"PDF to image conversion failed: {e}")
            raise Exception(f"Failed to convert PDF to image: {str(e)}")
    
    def _get_mime_type(self, file_path: str) -> str:
        """Get MIME type from file extension"""
        ext = file_path.lower().split('.')[-1]
        mime_types = {
            'pdf': 'application/pdf',
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'tiff': 'image/tiff',
            'tif': 'image/tiff'
        }
        return mime_types.get(ext, 'application/octet-stream')

ocr_service = OCRService()

