"""Token encryption services."""

import base64
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from ..config import settings


def _get_fernet() -> Fernet:
    """Get Fernet instance for encryption/decryption."""
    # Derive a key from the encryption key using PBKDF2
    key = settings.tokens_encryption_key.encode()
    # Use a fixed salt for deterministic key derivation
    salt = b"images2slides_v1"
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    derived_key = base64.urlsafe_b64encode(kdf.derive(key))
    return Fernet(derived_key)


def encrypt_token(plaintext: str) -> str:
    """Encrypt a token for storage.
    
    Args:
        plaintext: The token to encrypt.
        
    Returns:
        Base64-encoded encrypted token.
    """
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    """Decrypt a stored token.
    
    Args:
        ciphertext: The encrypted token.
        
    Returns:
        Decrypted plaintext token.
        
    Raises:
        Exception: If decryption fails.
    """
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()