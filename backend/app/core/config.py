"""
Application Configuration
"""
import json
from typing import List

from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    # Azure OpenAI
    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_API_KEY: str
    AZURE_OPENAI_API_VERSION: str = "2024-02-15-preview"
    AZURE_OPENAI_DEPLOYMENT_NAME: str = "gpt-4-vision"
    
    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "underwriting_ocr"
    
    # Storage
    AZURE_STORAGE_CONNECTION_STRING: str = ""
    AZURE_STORAGE_CONTAINER: str = "documents"
    USE_AZURE_STORAGE: bool = False
    LOCAL_STORAGE_PATH: str = "./storage/documents"
    
    # Security
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # Application
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    MAX_FILE_SIZE_MB: int = 50
    ALLOWED_FILE_TYPES: str = "pdf,jpg,jpeg,png,tiff"
    
    # CORS - Accept as string, will be parsed to list
    # Include both common frontend ports: Vite (5173, 5174) and Create React App (3000)
    # Can be overridden by environment variable CORS_ORIGINS

    # IMPORTANT: Keep this as `str` so pydantic-settings doesn't try to JSON-parse it
    # when loaded from environment variables. We'll parse it below into a `list[str]`.
    # Supported env formats:
    # - Comma-separated:  http://localhost:5173,http://localhost:3000
    # - JSON list:        ["http://localhost:5173", "http://localhost:3000"]
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174"

    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

# Parse CORS origins from string to list
def _parse_cors_origins(value) -> List[str]:
    if value is None:
        return []

    # Already a list (e.g., if code assigns it later)
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]

    # String: allow JSON list or comma-separated
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []

        if s.startswith("["):
            try:
                data = json.loads(s)
                if isinstance(data, list):
                    return [str(v).strip() for v in data if str(v).strip()]
            except json.JSONDecodeError:
                # Fall back to comma-splitting
                pass

        return [origin.strip().strip('"').strip("'") for origin in s.split(",") if origin.strip()]

    return []

settings.CORS_ORIGINS = _parse_cors_origins(settings.CORS_ORIGINS)

# Always ensure common development ports are included
# Convert to set to avoid duplicates, then back to list
cors_set = set(settings.CORS_ORIGINS)

# Add essential localhost ports
essential_ports = [
    "http://localhost:5173",
    "http://localhost:5174",
    "http://localhost:3000",
]
for origin in essential_ports:
    cors_set.add(origin)

# In DEBUG mode, add more common development ports
if settings.DEBUG:
    additional_ports = ["5175", "3001", "8080", "8081"]
    for port in additional_ports:
        cors_set.add(f"http://localhost:{port}")

# Convert back to list
settings.CORS_ORIGINS = list(cors_set)




