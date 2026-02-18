"""
User Management API Endpoints
"""
from fastapi import APIRouter, HTTPException, Body
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
from app.models.user import User, UserCreate
from app.core.database import get_database
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", response_model=User)
async def create_user(user_data: UserCreate):
    """
    Create a new user
    
    - **email**: User email (must be unique)
    - **name**: User name
    - **organization**: Optional organization name
    """
    try:
        db = await get_database()
        
        # Validate and normalize fields first
        email = user_data.email.strip() if user_data.email else ""
        name = user_data.name.strip() if user_data.name else ""
        
        if not email:
            raise HTTPException(status_code=422, detail="Email is required and cannot be empty")
        if not name:
            raise HTTPException(status_code=422, detail="Name is required and cannot be empty")
        
        # Generate user_id
        user_id = f"user_{uuid.uuid4().hex[:12]}"
        
        # Check if email already exists (using normalized email)
        existing = await db.users.find_one({"email": email})
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"User with email {email} already exists"
            )
        
        # Normalize organization field - convert empty strings to None
        organization = user_data.organization
        if organization is not None and (not isinstance(organization, str) or organization.strip() == ""):
            organization = None
        
        # Create user
        user = User(
            user_id=user_id,
            email=email,
            name=name,
            organization=organization,
            created_at=datetime.now(timezone.utc),
            subscription_tier="basic"
        )
        
        # Save to database
        await db.users.insert_one(user.model_dump())
        
        logger.info(f"User created: {user_id}")
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/", response_model=List[User])
async def list_users():
    """Get all users"""
    try:
        db = await get_database()
        cursor = db.users.find().sort("created_at", -1)
        users = await cursor.to_list(length=None)
        
        # Remove _id from each user and validate with User model
        result = []
        for user in users:
            user.pop("_id", None)
            # Use model_validate for better handling of optional fields including case_status
            result.append(User.model_validate(user))
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to list users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{user_id}", response_model=User)
async def get_user(user_id: str):
    """Get user by ID"""
    try:
        db = await get_database()
        user = await db.users.find_one({"user_id": user_id})
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user.pop("_id", None)
        # Use model_validate for better handling of optional fields
        return User.model_validate(user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/bulk", response_model=List[User])
async def create_bulk_users(users_data: List[UserCreate]):
    """
    Create multiple users at once
    
    Useful for creating your 4 users quickly
    """
    try:
        db = await get_database()
        created_users = []
        
        for user_data in users_data:
            # Generate user_id
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            
            # Check if email already exists
            existing = await db.users.find_one({"email": user_data.email})
            if existing:
                logger.warning(f"User with email {user_data.email} already exists, skipping...")
                continue
            
            # Create user
            user = User(
                user_id=user_id,
                email=user_data.email,
                name=user_data.name,
                organization=user_data.organization,
                created_at=datetime.now(timezone.utc),
                subscription_tier="basic"
            )
            
            # Save to database
            await db.users.insert_one(user.model_dump())
            created_users.append(user)
            logger.info(f"User created: {user_id}")
        
        return created_users
        
    except Exception as e:
        logger.error(f"Failed to create users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create-default", response_model=List[User])
async def create_default_users():
    """
    Create 4 default users (user_001, user_002, user_003, user_004)
    
    This endpoint creates the 4 users you need for your system
    """
    try:
        db = await get_database()
        created_users = []
        
        default_users = [
            {
                "user_id": "user_001",
                "email": "user1@example.com",
                "name": "User One",
                "organization": "Company A"
            },
            {
                "user_id": "user_002",
                "email": "user2@example.com",
                "name": "User Two",
                "organization": "Company B"
            },
            {
                "user_id": "user_003",
                "email": "user3@example.com",
                "name": "User Three",
                "organization": "Company C"
            },
            {
                "user_id": "user_004",
                "email": "user4@example.com",
                "name": "User Four",
                "organization": "Company D"
            }
        ]
        
        for user_data in default_users:
            # Check if user already exists
            existing = await db.users.find_one({"user_id": user_data["user_id"]})
            if existing:
                logger.info(f"User {user_data['user_id']} already exists, skipping...")
                existing.pop("_id", None)
                created_users.append(User(**existing))
                continue
            
            # Check if email already exists
            email_existing = await db.users.find_one({"email": user_data["email"]})
            if email_existing:
                logger.warning(f"Email {user_data['email']} already exists, skipping...")
                continue
            
            # Create user
            user = User(
                user_id=user_data["user_id"],
                email=user_data["email"],
                name=user_data["name"],
                organization=user_data["organization"],
                created_at=datetime.now(timezone.utc),
                subscription_tier="basic"
            )
            
            # Save to database
            await db.users.insert_one(user.model_dump())
            created_users.append(user)
            logger.info(f"User created: {user_data['user_id']}")
        
        return created_users
        
    except Exception as e:
        logger.error(f"Failed to create default users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/{user_id}")
async def delete_user(user_id: str):
    """Delete a user by ID"""
    try:
        db = await get_database()
        user = await db.users.find_one({"user_id": user_id})
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Delete user
        await db.users.delete_one({"user_id": user_id})
        
        logger.info(f"User deleted: {user_id}")
        
        return {"message": f"User {user_id} deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/{user_id}/case-status")
async def update_case_status(user_id: str, request_data: Dict[str, Any] = Body(...)):
    """Update case status and decision for a user"""
    try:
        db = await get_database()
        user = await db.users.find_one({"user_id": user_id})
        
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Update user with case status and decision
        update_data = {
            "case_status": request_data.get("case_status", "In Review"),
            "case_updated_at": datetime.now(timezone.utc)
        }
        
        if request_data.get("decision"):
            update_data["case_decision"] = request_data["decision"]
        if request_data.get("notes"):
            update_data["case_notes"] = request_data["notes"]
        if request_data.get("conditions"):
            update_data["case_conditions"] = request_data["conditions"]
        
        await db.users.update_one(
            {"user_id": user_id},
            {"$set": update_data}
        )
        
        logger.info(f"Case status updated for user {user_id}: {update_data['case_status']}")
        
        # Return updated user with proper validation
        updated_user = await db.users.find_one({"user_id": user_id})
        if not updated_user:
            raise HTTPException(status_code=404, detail="User not found after update")
        
        updated_user.pop("_id", None)
        # Use model_validate for proper datetime serialization
        return User.model_validate(updated_user)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update case status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


