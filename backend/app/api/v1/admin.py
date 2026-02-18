"""
Admin Authentication API Endpoints
"""
from fastapi import APIRouter, HTTPException, Depends, status, Body
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import uuid
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from app.models.admin import Admin, AdminCreate, AdminLogin, AdminResponse, TokenResponse
from app.core.database import get_database
from app.core.auth import verify_password, get_password_hash, create_access_token, verify_token
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()

async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Admin:
    """Get current admin from JWT token"""
    token = credentials.credentials
    payload = verify_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    admin_id: str = payload.get("sub")
    if admin_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    db = await get_database()
    admin_doc = await db.admins.find_one({"admin_id": admin_id})
    
    if admin_doc is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return Admin(**admin_doc)

@router.post("/login", response_model=TokenResponse)
async def admin_login(login_data: AdminLogin):
    """
    Admin login endpoint
    
    - **email**: Admin email
    - **password**: Admin password
    """
    try:
        db = await get_database()
        
        # Find admin by email
        admin_doc = await db.admins.find_one({"email": login_data.email})
        
        # If admin doesn't exist and it's the default admin email, create it
        if admin_doc is None and login_data.email == "admin@admin.com":
            try:
                # Create default admin
                admin_id = "admin_001"
                hashed_password = get_password_hash("admin123")
                
                admin = Admin(
                    admin_id=admin_id,
                    email="admin@admin.com",
                    name="Default Admin",
                    hashed_password=hashed_password,
                    created_at=datetime.now(timezone.utc),
                    is_active=True
                )
                
                await db.admins.insert_one(admin.model_dump())
                logger.info("Default admin created: admin@admin.com")
                
                # Use the newly created admin
                admin_doc = admin.model_dump()
            except Exception as e:
                logger.error(f"Failed to create default admin: {e}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect email or password"
                )
        
        if admin_doc is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        admin = Admin(**admin_doc)
        
        # Verify password
        if not verify_password(login_data.password, admin.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Check if admin is active
        if not admin.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin account is inactive"
            )
        
        # Update last login
        await db.admins.update_one(
            {"admin_id": admin.admin_id},
            {"$set": {"last_login": datetime.now(timezone.utc)}}
        )
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": admin.admin_id, "email": admin.email},
            expires_delta=access_token_expires
        )
        
        # Return token and admin info
        admin_response = AdminResponse(
            admin_id=admin.admin_id,
            email=admin.email,
            name=admin.name,
            created_at=admin.created_at,
            last_login=datetime.now(timezone.utc),
            is_active=admin.is_active
        )
        
        logger.info(f"Admin logged in: {admin.email}")
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            admin=admin_response
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to login admin: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create", response_model=AdminResponse)
async def create_admin(admin_data: AdminCreate, current_admin: Admin = Depends(get_current_admin)):
    """
    Create a new admin (requires authentication)
    
    - **email**: Admin email (must be unique)
    - **name**: Admin name
    - **password**: Admin password
    """
    try:
        db = await get_database()
        
        # Validate and normalize fields
        email = admin_data.email.strip() if admin_data.email else ""
        name = admin_data.name.strip() if admin_data.name else ""
        
        if not email:
            raise HTTPException(status_code=422, detail="Email is required and cannot be empty")
        if not name:
            raise HTTPException(status_code=422, detail="Name is required and cannot be empty")
        if not admin_data.password:
            raise HTTPException(status_code=422, detail="Password is required and cannot be empty")
        
        # Generate admin_id
        admin_id = f"admin_{uuid.uuid4().hex[:12]}"
        
        # Check if email already exists
        existing = await db.admins.find_one({"email": email})
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Admin with email {email} already exists"
            )
        
        # Hash password
        hashed_password = get_password_hash(admin_data.password)
        
        # Create admin
        admin = Admin(
            admin_id=admin_id,
            email=email,
            name=name,
            hashed_password=hashed_password,
            created_at=datetime.now(timezone.utc),
            is_active=True
        )
        
        # Save to database
        await db.admins.insert_one(admin.model_dump())
        
        logger.info(f"Admin created: {admin_id} by {current_admin.email}")
        
        # Return admin without password
        return AdminResponse(
            admin_id=admin.admin_id,
            email=admin.email,
            name=admin.name,
            created_at=admin.created_at,
            last_login=admin.last_login,
            is_active=admin.is_active
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create admin: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/me", response_model=AdminResponse)
async def get_current_admin_info(current_admin: Admin = Depends(get_current_admin)):
    """Get current admin information"""
    return AdminResponse(
        admin_id=current_admin.admin_id,
        email=current_admin.email,
        name=current_admin.name,
        created_at=current_admin.created_at,
        last_login=current_admin.last_login,
        is_active=current_admin.is_active
    )

class AdminUpdate(BaseModel):
    """Admin profile update request"""
    name: Optional[str] = None
    current_password: Optional[str] = None
    new_password: Optional[str] = None

@router.put("/me", response_model=AdminResponse)
async def update_admin_profile(
    update_data: AdminUpdate = Body(...),
    current_admin: Admin = Depends(get_current_admin)
):
    """
    Update admin profile
    
    - **name**: New admin name (optional)
    - **current_password**: Current password (required if changing password)
    - **new_password**: New password (optional)
    """
    try:
        db = await get_database()
        update_data_dict = {}
        
        # Update name if provided
        if update_data.name and update_data.name.strip():
            update_data_dict["name"] = update_data.name.strip()
        
        # Update password if provided
        if update_data.new_password:
            if not update_data.current_password:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Current password is required to change password"
                )
            
            # Verify current password
            if not verify_password(update_data.current_password, current_admin.hashed_password):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Current password is incorrect"
                )
            
            # Validate new password
            if len(update_data.new_password) < 6:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="New password must be at least 6 characters"
                )
            
            # Hash new password
            update_data_dict["hashed_password"] = get_password_hash(update_data.new_password)
        
        # If no updates, return current admin
        if not update_data_dict:
            return AdminResponse(
                admin_id=current_admin.admin_id,
                email=current_admin.email,
                name=current_admin.name,
                created_at=current_admin.created_at,
                last_login=current_admin.last_login,
                is_active=current_admin.is_active
            )
        
        # Update in database
        await db.admins.update_one(
            {"admin_id": current_admin.admin_id},
            {"$set": update_data_dict}
        )
        
        # Fetch updated admin
        updated_doc = await db.admins.find_one({"admin_id": current_admin.admin_id})
        updated_admin = Admin(**updated_doc)
        
        logger.info(f"Admin profile updated: {current_admin.email}")
        
        return AdminResponse(
            admin_id=updated_admin.admin_id,
            email=updated_admin.email,
            name=updated_admin.name,
            created_at=updated_admin.created_at,
            last_login=updated_admin.last_login,
            is_active=updated_admin.is_active
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update admin profile: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create-default")
async def create_default_admin():
    """
    Create a default admin account (for initial setup)
    Default credentials:
    - Email: admin@admin.com
    - Password: admin123
    """
    try:
        db = await get_database()
        
        # Check if default admin already exists
        existing = await db.admins.find_one({"email": "admin@admin.com"})
        if existing:
            return {"message": "Default admin already exists", "email": "admin@admin.com"}
        
        # Create default admin
        admin_id = "admin_001"
        hashed_password = get_password_hash("admin123")
        
        admin = Admin(
            admin_id=admin_id,
            email="admin@admin.com",
            name="Default Admin",
            hashed_password=hashed_password,
            created_at=datetime.now(timezone.utc),
            is_active=True
        )
        
        await db.admins.insert_one(admin.model_dump())
        
        logger.info("Default admin created: admin@admin.com")
        
        return {
            "message": "Default admin created successfully",
            "email": "admin@admin.com",
            "password": "admin123",
            "note": "Please change the password after first login"
        }
        
    except Exception as e:
        logger.error(f"Failed to create default admin: {e}")
        raise HTTPException(status_code=500, detail=str(e))
