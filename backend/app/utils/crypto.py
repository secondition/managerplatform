"""Symmetric encryption for at-rest secrets (AI provider API keys).

The Fernet key is derived from the app's ``jwt_secret`` (already required in
.env) so we don't add a second secret to manage. Only ciphertext is stored; the
API layer never returns raw keys — it masks them (see ``mask_secret``).
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


def _fernet() -> Fernet:
    # Derive a stable 32-byte urlsafe key from jwt_secret.
    digest = hashlib.sha256(settings.jwt_secret.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: str | None) -> str | None:
    if not ciphertext:
        return None
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError):
        return None


def mask_secret(plaintext: str | None) -> str:
    """Return a masked hint like ``sk-****abcd`` for display, never the raw key."""
    if not plaintext:
        return ""
    if len(plaintext) <= 8:
        return "****"
    return f"{plaintext[:3]}****{plaintext[-4:]}"
