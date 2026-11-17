import base64
import hashlib
import os
import socket
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

_ENC_PREFIX = "enc:v1:"


@lru_cache(maxsize=1)
def _get_fernet() -> Fernet:
    """Return a Fernet instance backed by API_KEY_ENCRYPTION_SECRET or a machine-local fallback."""
    secret = os.environ.get("API_KEY_ENCRYPTION_SECRET")
    if not secret:
        secret = f"ai-hedge-fund-local:{socket.gethostname()}"
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    key = base64.urlsafe_b64encode(digest)
    return Fernet(key)


def encrypt_secret(value: str) -> str:
    """Encrypt a secret value for storage at rest."""
    if not value or value.startswith(_ENC_PREFIX):
        return value
    token = _get_fernet().encrypt(value.encode("utf-8")).decode("ascii")
    return f"{_ENC_PREFIX}{token}"


def decrypt_secret(value: str) -> str:
    """Decrypt a stored secret value, passing through legacy plaintext values."""
    if not value or not value.startswith(_ENC_PREFIX):
        return value
    token = value[len(_ENC_PREFIX):].encode("ascii")
    try:
        return _get_fernet().decrypt(token).decode("utf-8")
    except InvalidToken:
        return ""


def mask_secret(value: str) -> str:
    """Return a masked representation of a secret suitable for API responses."""
    if not value:
        return ""
    if len(value) > 8:
        return f"{value[:4]}...{value[-4:]}"
    return "****"
