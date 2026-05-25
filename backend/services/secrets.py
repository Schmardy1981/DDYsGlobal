"""Symmetric encryption helper for secrets stored at rest.

API keys for third-party integrations (Anthropic, Refinitiv, SendGrid, etc.)
are persisted to Mongo. Storing them in plaintext means a database dump is a
full credential compromise. This module wraps Fernet with a key derived from
the ``SECRETS_ENCRYPTION_KEY`` (or, as a fallback, ``JWT_SECRET``) environment
variable so callers get encrypted-at-rest without having to manage keys.

If neither variable is set we fall back to a deterministic key derived from a
local-only sentinel so the system still starts in dev — but a warning is
logged because that gives ZERO confidentiality vs. an attacker with DB
access. Production deployments must set ``SECRETS_ENCRYPTION_KEY``.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

_ENCRYPTED_PREFIX = "enc::"


def _derive_key() -> bytes:
    secret = os.environ.get("SECRETS_ENCRYPTION_KEY") or os.environ.get("JWT_SECRET")
    if not secret:
        logger.warning(
            "SECRETS_ENCRYPTION_KEY / JWT_SECRET not set. "
            "Secrets at rest will use a non-secret derivation key — "
            "this is acceptable for local dev only."
        )
        secret = "ddys-dev-only-secret-do-not-use-in-prod"
    digest = hashlib.sha256(secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


_FERNET: Fernet | None = None


def _fernet() -> Fernet:
    global _FERNET
    if _FERNET is None:
        _FERNET = Fernet(_derive_key())
    return _FERNET


def encrypt_secret(value: str) -> str:
    """Encrypt a plaintext secret and return a tagged ciphertext string.

    Already-encrypted values (with ``enc::`` prefix) are returned unchanged
    so callers can re-encrypt idempotently.
    """
    if not value:
        return value
    if isinstance(value, str) and value.startswith(_ENCRYPTED_PREFIX):
        return value
    token = _fernet().encrypt(value.encode("utf-8")).decode("utf-8")
    return f"{_ENCRYPTED_PREFIX}{token}"


def decrypt_secret(value: str) -> str:
    """Reverse of :func:`encrypt_secret`. Returns plaintext.

    Untagged values are returned as-is to support gradual migration from
    plaintext to encrypted storage.
    """
    if not value or not isinstance(value, str):
        return value
    if not value.startswith(_ENCRYPTED_PREFIX):
        return value
    payload = value[len(_ENCRYPTED_PREFIX):]
    try:
        return _fernet().decrypt(payload.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        logger.error("Failed to decrypt secret — wrong key or corrupted data")
        return ""


def is_encrypted(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(_ENCRYPTED_PREFIX)
