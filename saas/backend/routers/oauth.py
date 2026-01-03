from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import OAuthToken, User
from ..db.session import get_db
from ..schemas import OAuthExchangeIn
from ..services.auth import get_current_user
from ..services.crypto import Crypto
from ..config import get_settings

router = APIRouter()


@router.post("/oauth/google/exchange")
def oauth_exchange(
    body: OAuthExchangeIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    settings = get_settings()
    crypto = Crypto(settings)

    token = db.scalar(
        select(OAuthToken).where(OAuthToken.user_id == user.id, OAuthToken.provider == body.provider)
    )

    if token is None:
        token = OAuthToken(
            user_id=user.id,
            provider=body.provider,
            scopes=body.scopes,
            access_token_encrypted=crypto.encrypt_str(body.access_token),
            refresh_token_encrypted=crypto.encrypt_str(body.refresh_token) if body.refresh_token else None,
            expires_at=body.expires_at,
        )
        db.add(token)
    else:
        token.scopes = body.scopes or token.scopes
        token.access_token_encrypted = crypto.encrypt_str(body.access_token)
        if body.refresh_token:
            token.refresh_token_encrypted = crypto.encrypt_str(body.refresh_token)
        token.expires_at = body.expires_at

    db.commit()
    return {"status": "ok"}
