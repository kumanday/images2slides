"""Authentication services."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests
from google.oauth2 import id_token
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db.models import User
from ..db.session import get_db

security = HTTPBearer()


class GoogleTokenPayload:
    """Verified Google token payload."""

    def __init__(self, sub: str, email: str, name: str | None, picture: str | None):
        self.sub = sub
        self.email = email
        self.name = name
        self.picture = picture


def verify_google_token(token: str) -> GoogleTokenPayload:
    """Verify a Google ID token and extract claims.
    
    Args:
        token: The Google ID token to verify.
        
    Returns:
        GoogleTokenPayload with user info.
        
    Raises:
        HTTPException: If token is invalid.
    """
    try:
        idinfo = id_token.verify_oauth2_token(
            token,
            requests.Request(),
            settings.google_client_id,
        )
        return GoogleTokenPayload(
            sub=idinfo["sub"],
            email=idinfo["email"],
            name=idinfo.get("name"),
            picture=idinfo.get("picture"),
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google token: {e}",
        )


async def get_or_create_user(
    db: AsyncSession,
    payload: GoogleTokenPayload,
) -> User:
    """Get existing user or create new one from Google token payload.
    
    Args:
        db: Database session.
        payload: Verified Google token payload.
        
    Returns:
        User instance.
    """
    result = await db.execute(
        select(User).where(User.google_sub == payload.sub)
    )
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            google_sub=payload.sub,
            email=payload.email,
            name=payload.name,
            picture_url=payload.picture,
        )
        db.add(user)
        await db.flush()
    else:
        # Update profile info if changed
        if user.email != payload.email:
            user.email = payload.email
        if user.name != payload.name:
            user.name = payload.name
        if user.picture_url != payload.picture:
            user.picture_url = payload.picture

    return user


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Dependency to get current authenticated user.
    
    Args:
        credentials: Bearer token from Authorization header.
        db: Database session.
        
    Returns:
        Authenticated User.
        
    Raises:
        HTTPException: If authentication fails.
    """
    token = credentials.credentials
    payload = verify_google_token(token)
    user = await get_or_create_user(db, payload)
    return user