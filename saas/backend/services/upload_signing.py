from __future__ import annotations

import base64
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256

from ..config import get_settings


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


@dataclass(frozen=True)
class UploadTokenPayload:
    storage_key: str
    user_id: int
    project_id: int
    exp: int


def sign_upload_token(payload: UploadTokenPayload) -> str:
    settings = get_settings()
    payload_json = json.dumps(payload.__dict__, separators=(",", ":")).encode("utf-8")
    payload_b64 = _b64url_encode(payload_json)

    sig = hmac.new(settings.tokens_encryption_key.encode("utf-8"), payload_b64.encode("ascii"), sha256)
    sig_b64 = _b64url_encode(sig.digest())
    return f"{payload_b64}.{sig_b64}"


def verify_upload_token(token: str) -> UploadTokenPayload:
    settings = get_settings()
    try:
        payload_b64, sig_b64 = token.split(".", 1)
    except ValueError as e:  # noqa: BLE001
        raise ValueError("Invalid token") from e

    expected_sig = hmac.new(
        settings.tokens_encryption_key.encode("utf-8"), payload_b64.encode("ascii"), sha256
    ).digest()

    if not hmac.compare_digest(_b64url_decode(sig_b64), expected_sig):
        raise ValueError("Invalid signature")

    payload_dict = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    payload = UploadTokenPayload(**payload_dict)

    now = int(datetime.now(tz=timezone.utc).timestamp())
    if payload.exp < now:
        raise ValueError("Token expired")

    return payload
