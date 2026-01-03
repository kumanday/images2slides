"""OAuth token management"""
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from saas.api.models import User, OAuthToken
from saas.api.token_encryption import encrypt_optional_token, decrypt_optional_token
import os


def store_oauth_token(
    db: Session,
    user: User,
    provider: str,
    access_token: str,
    refresh_token: str = None,
    token_type: str = "Bearer",
    scope: str = None,
    expires_in: int = None
) -> OAuthToken:
    """Store or update OAuth token for a user"""
    # Calculate expiration time
    expires_at = None
    if expires_in:
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
    
    # Check if token already exists
    token = db.query(OAuthToken).filter(
        OAuthToken.user_id == user.id,
        OAuthToken.provider == provider
    ).first()
    
    if token:
        # Update existing token
        token.access_token = encrypt_optional_token(access_token)
        token.refresh_token = encrypt_optional_token(refresh_token)
        token.token_type = token_type
        token.scope = scope
        token.expires_at = expires_at
        token.updated_at = datetime.utcnow()
    else:
        # Create new token
        token = OAuthToken(
            user_id=user.id,
            provider=provider,
            access_token=encrypt_optional_token(access_token),
            refresh_token=encrypt_optional_token(refresh_token),
            token_type=token_type,
            scope=scope,
            expires_at=expires_at
        )
        db.add(token)
    
    db.commit()
    db.refresh(token)
    return token


def get_oauth_token(
    db: Session,
    user: User,
    provider: str
) -> OAuthToken | None:
    """Get OAuth token for a user"""
    token = db.query(OAuthToken).filter(
        OAuthToken.user_id == user.id,
        OAuthToken.provider == provider
    ).first()
    
    return token


def get_decrypted_access_token(
    db: Session,
    user: User,
    provider: str
) -> str | None:
    """Get decrypted access token for a user"""
    token = get_oauth_token(db, user, provider)
    if not token:
        return None
    
    return decrypt_optional_token(token.access_token)


def get_decrypted_refresh_token(
    db: Session,
    user: User,
    provider: str
) -> str | None:
    """Get decrypted refresh token for a user"""
    token = get_oauth_token(db, user, provider)
    if not token:
        return None
    
    return decrypt_optional_token(token.refresh_token)


def is_token_expired(token: OAuthToken) -> bool:
    """Check if a token is expired"""
    if not token.expires_at:
        return False
    
    return datetime.utcnow() >= token.expires_at
