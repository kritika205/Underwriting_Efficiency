"""
Authentication Utilities
"""
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from app.core.config import settings
from typing import Optional
import logging
import bcrypt

logger = logging.getLogger(__name__)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash using bcrypt"""
    try:
        # Ensure both are bytes
        password_bytes = plain_password.encode('utf-8') if isinstance(plain_password, str) else plain_password
        hash_bytes = hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
        
        return bcrypt.checkpw(password_bytes, hash_bytes)
    except Exception as e:
        logger.error(f"Bcrypt verify failed: {e}")
        return False

def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt"""
    try:
        # Ensure password is bytes
        password_bytes = password.encode('utf-8') if isinstance(password, str) else password
        
        # Generate salt and hash password
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')
    except Exception as e:
        logger.error(f"Bcrypt hash failed: {e}")
        raise

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT token"""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
