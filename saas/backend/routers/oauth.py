"""OAuth token management endpoints."""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.session import get_db
from ..db.models import User, OAuthToken
from ..services.auth import get_current_user
from ..services.encryption import encrypt_token

router = APIRouter()


class OAuthExchangeRequest(BaseModel):
    """Request to store OAuth tokens."""

    access_token: str
    refresh_token: str | None = None
    expires_at: datetime | None = None
    scopes: list[str] = []


class OAuthExchangeResponse(BaseModel):
    """Response after storing OAuth tokens."""

    status: str
    has_refresh_token: bool
    scopes: list[str]


@router.post("/google/exchange")
async def exchange_google_tokens(
    request: OAuthExchangeRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OAuthExchangeResponse:
    """Store Google OAuth tokens for the current user.
    
    The frontend obtains tokens through NextAuth and sends them here
    for secure encrypted storage. These tokens are used by the worker
    to access Google Slides API on behalf of the user.
    
    Args:
        request: OAuth tokens from the frontend.
        current_user: Authenticated user.
        db: Database session.
        
    Returns:
        Status of token storage.
    """
    # Check for existing token
    result = await db.execute(
        select(OAuthToken).where(
            OAuthToken.user_id == current_user.id,
            OAuthToken.provider == "google",
        )
    )
    existing = result.scalar_one_or_none()

    encrypted_access = encrypt_token(request.access_token)
    encrypted_refresh = (
        encrypt_token(request.refresh_token) if request.refresh_token else None
    )

    if existing:
        existing.access_token_encrypted = encrypted_access
        if encrypted_refresh:
            existing.refresh_token_encrypted = encrypted_refresh
        if request.expires_at:
            existing.token_expires_at = request.expires_at
        if request.scopes:
            existing.scopes = request.scopes
    else:
        oauth_token = OAuthToken(
            user_id=current_user.id,
            provider="google",
            access_token_encrypted=encrypted_access,
            refresh_token_encrypted=encrypted_refresh,
            token_expires_at=request.expires_at,
            scopes=request.scopes,
        )
        db.add(oauth_token)

    await db.flush()

    return OAuthExchangeResponse(
        status="stored",
        has_refresh_token=request.refresh_token is not None,
        scopes=request.scopes,
    )


@router.get("/google/status")
async def get_google_oauth_status(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """Check if user has stored Google OAuth tokens.
    
    Args:
        current_user: Authenticated user.
        db: Database session.
        
    Returns:
        Token status including scopes and expiry.
    """
    result = await db.execute(
        select(OAuthToken).where(
            OAuthToken.user_id == current_user.id,
            OAuthToken.provider == "google",
        )
    )
    token = result.scalar_one_or_none()

    if not token:
        return {
            "has_tokens": False,
            "has_refresh_token": False,
            "scopes": [],
            "expires_at": None,
        }

    return {
        "has_tokens": True,
        "has_refresh_token": token.refresh_token_encrypted is not None,
        "scopes": token.scopes or [],
        "expires_at": token.token_expires_at.isoformat() if token.token_expires_at else None,
    }