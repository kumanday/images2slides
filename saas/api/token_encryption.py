"""Token encryption utilities"""
import os
from cryptography.fernet import Fernet
from typing import Optional

# Get encryption key from environment
ENCRYPTION_KEY = os.getenv("TOKENS_ENCRYPTION_KEY")

if not ENCRYPTION_KEY:
    raise ValueError("TOKENS_ENCRYPTION_KEY environment variable is not set")

# Ensure key is 32 bytes and URL-safe base64 encoded
if len(ENCRYPTION_KEY) != 44:  # Fernet keys are 44 characters when base64 encoded
    # If it's not a Fernet key, try to convert it
    if len(ENCRYPTION_KEY) == 32:
        # It's a raw 32-byte key, encode it
        ENCRYPTION_KEY_BYTES = ENCRYPTION_KEY.encode()
        ENCRYPTION_KEY = Fernet(ENCRYPTION_KEY_BYTES).generate_key().decode()
    else:
        raise ValueError("TOKENS_ENCRYPTION_KEY must be 32 bytes (raw) or 44 characters (Fernet base64)")

cipher_suite = Fernet(ENCRYPTION_KEY.encode())


def encrypt_token(token: str) -> str:
    """Encrypt a token"""
    encrypted = cipher_suite.encrypt(token.encode())
    return encrypted.decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a token"""
    decrypted = cipher_suite.decrypt(encrypted_token.encode())
    return decrypted.decode()


def encrypt_optional_token(token: Optional[str]) -> Optional[str]:
    """Encrypt a token if it exists"""
    if token is None:
        return None
    return encrypt_token(token)


def decrypt_optional_token(encrypted_token: Optional[str]) -> Optional[str]:
    """Decrypt a token if it exists"""
    if encrypted_token is None:
        return None
    return decrypt_token(encrypted_token)
