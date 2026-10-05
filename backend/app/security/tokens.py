"""Fernet-based token encryption at rest."""

from __future__ import annotations

import base64
import hashlib
import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import get_settings

logger = logging.getLogger(__name__)


def _derive_fernet_key(raw: str) -> bytes:
    """Accept a Fernet key or any passphrase; derive a stable url-safe 32-byte key."""
    raw = raw.strip()
    try:
        decoded = base64.urlsafe_b64decode(raw.encode("utf-8"))
        if len(decoded) == 32:
            return raw.encode("utf-8")
    except Exception:
        pass
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


def get_fernet() -> Fernet:
    settings = get_settings()
    return Fernet(_derive_fernet_key(settings.token_encryption_key))


def encrypt_token(plaintext: str) -> str:
    if not plaintext:
        raise ValueError("Cannot encrypt empty token")
    return get_fernet().encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_token(ciphertext: str) -> str:
    try:
        return get_fernet().decrypt(ciphertext.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        logger.error("Token decrypt failed (key mismatch or corrupt ciphertext)")
        raise ValueError("Invalid encrypted token") from exc


def redact_secrets(text: str, secrets: list[str] | None = None) -> str:
    """Redact known secret substrings from log text."""
    if not text:
        return text
    redacted = text
    for secret in secrets or []:
        if secret and len(secret) > 3:
            redacted = redacted.replace(secret, "[REDACTED]")
    return redacted
