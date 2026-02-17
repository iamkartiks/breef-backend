"""User Service - Authentication and user management."""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from supabase import Client
from typing import Optional

from shared.database import get_db
from shared.models import UserProfile, UserProfileUpdate, ErrorResponse

router = APIRouter()
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Client = Depends(get_db)
) -> dict:
    """Get current user from JWT token."""
    try:
        # Verify token with Supabase
        token = credentials.credentials
        response = db.auth.get_user(token)
        
        if not response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        
        return response.user.model_dump()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )


@router.get("/me", response_model=UserProfile)
async def get_user_profile(
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db)
):
    """Get current user's profile."""
    try:
        # Get user profile from database
        response = db.table("user_profiles").select("*").eq("id", current_user["id"]).execute()
        
        if not response.data:
            # Create profile if it doesn't exist
            profile_data = {
                "id": current_user["id"],
                "email": current_user.get("email", ""),
                "full_name": current_user.get("user_metadata", {}).get("full_name"),
            }
            db.table("user_profiles").insert(profile_data).execute()
            return UserProfile(**profile_data)
        
        return UserProfile(**response.data[0])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching user profile: {str(e)}"
        )


@router.put("/me", response_model=UserProfile)
async def update_user_profile(
    profile_update: UserProfileUpdate,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db)
):
    """Update current user's profile."""
    try:
        update_data = profile_update.model_dump(exclude_unset=True)
        
        response = db.table("user_profiles").update(update_data).eq("id", current_user["id"]).execute()
        
        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User profile not found"
            )
        
        return UserProfile(**response.data[0])
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating user profile: {str(e)}"
        )

