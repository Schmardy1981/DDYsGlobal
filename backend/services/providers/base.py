"""Abstract base classes for external provider integrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


# --- Email ----------------------------------------------------------------


@dataclass
class EmailMessage:
    to: str
    subject: str
    body_text: str
    body_html: Optional[str] = None
    reply_to: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class EmailSendResult:
    success: bool
    provider: str
    message_id: Optional[str] = None
    error: Optional[str] = None


class EmailProvider(ABC):
    """Adapter for transactional email delivery."""

    name: str = "base"

    @abstractmethod
    async def send(self, message: EmailMessage) -> EmailSendResult: ...


# --- KYC / Identity Verification -----------------------------------------


@dataclass
class KYCSessionRequest:
    case_id: str
    tenant_id: str
    party_id: str
    callback_url: Optional[str] = None
    metadata: dict = field(default_factory=dict)


@dataclass
class KYCSessionResult:
    provider: str
    session_id: str
    verification_url: Optional[str] = None
    status: str = "created"
    raw: dict = field(default_factory=dict)


@dataclass
class KYCWebhookEvent:
    session_id: str
    status: str  # created | in_progress | approved | declined | expired
    liveness_score: Optional[float] = None
    deepfake_score: Optional[float] = None
    document_match: Optional[bool] = None
    decision_reason: Optional[str] = None
    raw: dict = field(default_factory=dict)


class KYCProvider(ABC):
    """Adapter for identity verification (DIDIT, IDnow, etc.)."""

    name: str = "base"

    @abstractmethod
    async def create_session(self, req: KYCSessionRequest) -> KYCSessionResult: ...

    @abstractmethod
    async def get_session(self, session_id: str) -> KYCSessionResult: ...

    @abstractmethod
    async def verify_webhook(self, payload: bytes, signature: str) -> bool: ...

    @abstractmethod
    def parse_webhook(self, payload: dict) -> KYCWebhookEvent: ...


# --- Screening ------------------------------------------------------------


@dataclass
class ScreeningQuery:
    tenant_id: str
    party_id: str
    name: str
    date_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    list_types: list[str] = field(default_factory=lambda: ["sanctions", "pep", "adverse_media"])


@dataclass
class ScreeningHit:
    list_source: str
    hit_severity: str  # low | medium | high
    match_score: float
    matched_name: str
    list_type: str  # sanctions | pep | adverse_media
    details: dict = field(default_factory=dict)


class ScreeningProvider(ABC):
    """Adapter for sanctions / PEP / adverse-media screening."""

    name: str = "base"

    @abstractmethod
    async def screen(self, query: ScreeningQuery) -> list[ScreeningHit]: ...
