from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import Settings
from ..db.models import OAuthToken
from .crypto import Crypto

TOKEN_URI = "https://oauth2.googleapis.com/token"


def get_google_credentials_for_user(
    db: Session,
    settings: Settings,
    crypto: Crypto,
    user_id: int,
    scopes: list[str],
) -> Credentials:
    token = db.scalar(select(OAuthToken).where(OAuthToken.user_id == user_id, OAuthToken.provider == "google"))
    if token is None:
        raise ValueError("No OAuth tokens stored for user")

    access_token = crypto.decrypt_str(token.access_token_encrypted)
    refresh_token = crypto.decrypt_str(token.refresh_token_encrypted) if token.refresh_token_encrypted else None

    expiry = token.expires_at
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri=TOKEN_URI,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=scopes,
    )
    if expiry is not None:
        creds.expiry = expiry

    return creds


def build_slides_service(creds: Credentials) -> Any:
    return build("slides", "v1", credentials=creds, cache_discovery=False)
