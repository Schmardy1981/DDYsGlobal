"""Pluggable provider integrations (email, KYC/IDV, screening).

Every external integration the platform talks to is encapsulated behind a
small abstract interface in :mod:`backend.services.providers.base`. Concrete
adapters (mock + real) live in sibling modules. The active implementation is
selected by environment variables; configuration values can also be sourced
from the ``integrations`` collection so admins can configure providers from
the UI without redeploying.

This module exposes the public factory helpers consumed by the routes:

    from services.providers import (
        get_email_provider,
        get_kyc_provider,
        get_screening_provider,
    )

Each ``get_*`` helper returns a singleton per process. Pass ``db`` if you want
the factory to honour DB-stored credentials in the ``integrations``
collection.
"""

from .base import EmailMessage, EmailProvider, KYCProvider, ScreeningHit, ScreeningProvider
from .email import MockEmailProvider, SendGridEmailProvider
from .kyc import DIDITKYCProvider, MockKYCProvider
from .screening import ComplyAdvantageProvider, MockScreeningProvider, WorldCheckProvider

import os
from typing import Optional

__all__ = [
    "EmailMessage",
    "EmailProvider",
    "KYCProvider",
    "ScreeningHit",
    "ScreeningProvider",
    "get_email_provider",
    "get_kyc_provider",
    "get_screening_provider",
]

_email_singleton: Optional[EmailProvider] = None
_kyc_singleton: Optional[KYCProvider] = None
_screening_singleton: Optional[ScreeningProvider] = None


async def _load_integration(db, key: str) -> dict:
    if db is None:
        return {}
    try:
        rec = await db.integrations.find_one({"key": key, "enabled": True}, {"_id": 0})
        return (rec or {}).get("values", {}) or {}
    except Exception:  # noqa: BLE001 - DB optional
        return {}


async def get_email_provider(db=None) -> EmailProvider:
    """Return the configured email provider (singleton)."""
    global _email_singleton
    if _email_singleton is not None:
        return _email_singleton

    provider = os.environ.get("EMAIL_PROVIDER", "mock").lower()
    if provider == "sendgrid":
        values = await _load_integration(db, "email_sendgrid")
        _email_singleton = SendGridEmailProvider(
            api_key=os.environ.get("SENDGRID_API_KEY") or values.get("api_key", ""),
            from_email=os.environ.get("EMAIL_FROM") or values.get("from_email", "noreply@ddys.com"),
            from_name=os.environ.get("EMAIL_FROM_NAME") or values.get("from_name", "DDYs Compliance"),
        )
    else:
        _email_singleton = MockEmailProvider()
    return _email_singleton


async def get_kyc_provider(db=None) -> KYCProvider:
    """Return the configured identity-verification provider (singleton)."""
    global _kyc_singleton
    if _kyc_singleton is not None:
        return _kyc_singleton

    provider = os.environ.get("KYC_PROVIDER", "mock").lower()
    if provider == "didit":
        values = await _load_integration(db, "didit")
        _kyc_singleton = DIDITKYCProvider(
            api_key=os.environ.get("DIDIT_API_KEY") or values.get("api_key", ""),
            api_secret=os.environ.get("DIDIT_API_SECRET") or values.get("api_secret", ""),
            base_url=os.environ.get("DIDIT_BASE_URL")
            or values.get("base_url", "https://api.didit.me/v1"),
            webhook_secret=os.environ.get("DIDIT_WEBHOOK_SECRET")
            or values.get("webhook_secret", ""),
        )
    else:
        _kyc_singleton = MockKYCProvider()
    return _kyc_singleton


async def get_screening_provider(db=None) -> ScreeningProvider:
    """Return the configured sanctions/PEP/adverse-media provider (singleton)."""
    global _screening_singleton
    if _screening_singleton is not None:
        return _screening_singleton

    provider = os.environ.get("SCREENING_PROVIDER", "mock").lower()
    if provider == "worldcheck":
        values = await _load_integration(db, "screening_worldcheck")
        _screening_singleton = WorldCheckProvider(
            api_key=os.environ.get("WORLDCHECK_API_KEY") or values.get("api_key", ""),
            api_secret=os.environ.get("WORLDCHECK_API_SECRET") or values.get("api_secret", ""),
            group_id=os.environ.get("WORLDCHECK_GROUP_ID") or values.get("group_id", ""),
            base_url=os.environ.get("WORLDCHECK_BASE_URL")
            or values.get("base_url", "https://rms-world-check-one-api-pilot.thomsonreuters.com/v2"),
        )
    elif provider == "complyadvantage":
        values = await _load_integration(db, "screening_complyadvantage")
        _screening_singleton = ComplyAdvantageProvider(
            api_key=os.environ.get("COMPLYADVANTAGE_API_KEY") or values.get("api_key", ""),
            base_url=os.environ.get("COMPLYADVANTAGE_BASE_URL")
            or values.get("base_url", "https://api.complyadvantage.com"),
        )
    else:
        _screening_singleton = MockScreeningProvider()
    return _screening_singleton


def reset_provider_singletons() -> None:
    """Clear cached providers — used by tests and after admin config changes."""
    global _email_singleton, _kyc_singleton, _screening_singleton
    _email_singleton = None
    _kyc_singleton = None
    _screening_singleton = None
