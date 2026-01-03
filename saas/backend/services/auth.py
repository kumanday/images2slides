from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from google.auth.transport import requests
from google.oauth2 import id_token
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db.models import User
from ..db.session import get_db

security = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class GoogleIdentity:
    sub: str
    email: str
    name: str | None
    picture: str | None


def verify_google_id_token(token: str) -> GoogleIdentity:
    settings = get_settings()
    try:
        info = id_token.verify_oauth2_token(token, requests.Request(), settings.google_client_id)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid ID token") from e

    sub = info.get("sub")
    email = info.get("email")
    if not sub or not email:
        raise HTTPException(status_code=401, detail="Invalid ID token payload")

    return GoogleIdentity(
        sub=sub,
        email=email,
        name=info.get("name"),
        picture=info.get("picture"),
    )


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    ident = verify_google_id_token(creds.credentials)

    user = db.scalar(select(User).where(User.google_sub == ident.sub))
    if user is None:
        user = User(
            google_sub=ident.sub,
            email=ident.email,
            name=ident.name,
            picture_url=ident.picture,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        updated = False
        if user.email != ident.email:
            user.email = ident.email
            updated = True
        if ident.name and user.name != ident.name:
            user.name = ident.name
            updated = True
        if ident.picture and user.picture_url != ident.picture:
            user.picture_url = ident.picture
            updated = True
        if updated:
            db.commit()
            db.refresh(user)

    return user
