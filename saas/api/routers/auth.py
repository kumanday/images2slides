from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
from jose import jwt, JWTError
from saas.api.database import get_db
from saas.api.models import User
from saas.api.oauth_manager import store_oauth_token
import os

router = APIRouter()


class UserResponse(BaseModel):
    id: int
    email: str
    name: Optional[str] = None
    picture_url: Optional[str] = None

    class Config:
        from_attributes = True


class GoogleAuthRequest(BaseModel):
    id_token: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None


def get_current_user_from_token(token: str, db: Session) -> User:
    """Get current user from JWT token"""
    try:
        # Decode JWT token (simplified - in production, verify signature)
        payload = jwt.decode(token, os.getenv("NEXTAUTH_SECRET", ""), algorithms=["HS256"])
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def get_current_user(
    authorization: str = Header(None),
    db: Session = Depends(get_db)
) -> User:
    """Get current user from authorization header"""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    # Extract token from "Bearer <token>"
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    
    token = parts[1]
    return get_current_user_from_token(token, db)


@router.post("/auth/google", response_model=UserResponse)
async def google_auth(
    request: GoogleAuthRequest,
    db: Session = Depends(get_db)
):
    """Authenticate with Google OAuth"""
    try:
        # Verify Google ID token
        id_info = id_token.verify_oauth2_token(
            request.id_token,
            google_requests.Request(),
            os.getenv("GOOGLE_CLIENT_ID")
        )
        
        # Extract user info
        google_sub = id_info["sub"]
        email = id_info["email"]
        name = id_info.get("name")
        picture_url = id_info.get("picture")
        
        # Create or update user
        user = db.query(User).filter(User.google_sub == google_sub).first()
        
        if not user:
            user = User(
                google_sub=google_sub,
                email=email,
                name=name,
                picture_url=picture_url
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        else:
            # Update user info if changed
            if user.email != email:
                user.email = email
            if user.name != name:
                user.name = name
            if user.picture_url != picture_url:
                user.picture_url = picture_url
            db.commit()
            db.refresh(user)
        
        # Store OAuth tokens if provided
        if request.access_token:
            store_oauth_token(
                db=db,
                user=user,
                provider="google",
                access_token=request.access_token,
                refresh_token=request.refresh_token,
                token_type="Bearer",
                scope="openid email profile https://www.googleapis.com/auth/presentations https://www.googleapis.com/auth/drive.file",
                expires_in=request.expires_in
            )
        
        return user
        
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user info"""
    return current_user
