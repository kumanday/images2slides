import os
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from sqlalchemy import select
from models import User, OAuthToken

# OAuth configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
TOKENS_ENCRYPTION_KEY = os.getenv("TOKENS_ENCRYPTION_KEY", "default-32-byte-encryption-key-here!!")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours


def verify_google_id_token(id_token: str) -> dict:
    """Verify Google ID token and return claims."""
    try:
        # In production, verify with Google's public keys
        # For now, decode without verification in development
        payload = jwt.decode(id_token, options={"verify_signature": False})
        return payload
    except JWTError:
        return None


def get_or_create_user(
    db: Session,
    google_sub: str,
    email: str,
    name: Optional[str] = None,
    picture_url: Optional[str] = None
) -> User:
    """Get existing user or create new one."""
    result = db.execute(
        select(User).where(User.google_sub == google_sub)
    )
    user = result.scalar_one_or_none()
    
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
    
    return user


def save_oauth_tokens(
    db: Session,
    user_id: int,
    access_token: str,
    refresh_token: Optional[str] = None,
    expires_at: Optional[datetime] = None
) -> OAuthToken:
    """Save or update OAuth tokens for user."""
    result = db.execute(
        select(OAuthToken).where(OAuthToken.user_id == user_id)
    )
    token_record = result.scalar_one_or_none()
    
    if token_record:
        token_record.access_token = access_token
        token_record.refresh_token = refresh_token
        token_record.expires_at = expires_at
    else:
        token_record = OAuthToken(
            user_id=user_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at
        )
        db.add(token_record)
    
    db.commit()
    return token_record


def get_user_tokens(db: Session, user_id: int) -> Optional[OAuthToken]:
    """Get user's OAuth tokens."""
    result = db.execute(
        select(OAuthToken).where(OAuthToken.user_id == user_id)
    )
    return result.scalar_one_or_none()


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get user by ID."""
    result = db.execute(
        select(User).where(User.id == user_id)
    )
    return result.scalar_one_or_none()


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a simple access token for API authentication."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, TOKENS_ENCRYPTION_KEY, algorithm=ALGORITHM)


def verify_access_token(token: str) -> Optional[dict]:
    """Verify access token and return payload."""
    try:
        payload = jwt.decode(token, TOKENS_ENCRYPTION_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
