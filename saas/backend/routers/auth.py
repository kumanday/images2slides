"""Authentication endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..db.models import User
from ..services.auth import get_current_user, verify_google_token

router = APIRouter()


class UserResponse(BaseModel):
    """User response schema."""

    id: int
    email: str
    name: str | None
    picture_url: str | None

    class Config:
        from_attributes = True


@router.get("/me")
async def get_me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> UserResponse:
    """Get current authenticated user.
    
    Returns:
        Current user info.
        
    Raises:
        HTTPException: If not authenticated.
    """
    return UserResponse.model_validate(current_user)