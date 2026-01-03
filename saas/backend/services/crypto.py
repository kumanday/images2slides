from __future__ import annotations

from cryptography.fernet import Fernet

from ..config import Settings


class Crypto:
    def __init__(self, settings: Settings) -> None:
        self._fernet = Fernet(settings.tokens_encryption_key)

    def encrypt_str(self, value: str) -> str:
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt_str(self, value: str) -> str:
        return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
