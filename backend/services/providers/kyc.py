"""KYC / Identity Verification provider implementations."""

from __future__ import annotations

import hashlib
import hmac
import logging
import random
import uuid

import httpx

from .base import KYCProvider, KYCSessionRequest, KYCSessionResult, KYCWebhookEvent

logger = logging.getLogger(__name__)


class MockKYCProvider(KYCProvider):
    """In-process mock used in dev/test.

    Generates predictable session IDs and accepts any webhook. Scores are
    sampled from a sensible range so downstream policy thresholds can be
    exercised.
    """

    name = "mock"

    async def create_session(self, req: KYCSessionRequest) -> KYCSessionResult:
        session_id = f"mock-{uuid.uuid4().hex[:16]}"
        logger.info(
            "MOCK KYC create_session tenant=%s case=%s party=%s -> %s",
            req.tenant_id,
            req.case_id,
            req.party_id,
            session_id,
        )
        return KYCSessionResult(
            provider=self.name,
            session_id=session_id,
            verification_url=f"https://mock-kyc.local/sessions/{session_id}",
            status="created",
            raw={"mock": True, "case_id": req.case_id, "party_id": req.party_id},
        )

    async def get_session(self, session_id: str) -> KYCSessionResult:
        return KYCSessionResult(
            provider=self.name,
            session_id=session_id,
            status="approved",
            raw={"mock": True},
        )

    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        return True

    def parse_webhook(self, payload: dict) -> KYCWebhookEvent:
        return KYCWebhookEvent(
            session_id=payload.get("session_id", ""),
            status=payload.get("status", "approved"),
            liveness_score=payload.get("liveness_score", round(random.uniform(0.75, 0.99), 2)),
            deepfake_score=payload.get("deepfake_score", round(random.uniform(0.01, 0.15), 2)),
            document_match=payload.get("document_match", True),
            raw=payload,
        )


class DIDITKYCProvider(KYCProvider):
    """DIDIT (didit.me) adapter.

    Implements the parts of the DIDIT REST API used by the platform: session
    creation, status polling, and HMAC webhook verification. The exact request
    shapes are taken from the DIDIT v1 documentation; if their schema changes,
    only this adapter needs updating — callers go through the ``KYCProvider``
    interface.
    """

    name = "didit"

    def __init__(self, api_key: str, api_secret: str, base_url: str, webhook_secret: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url.rstrip("/")
        self.webhook_secret = webhook_secret

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "X-Api-Secret": self.api_secret,
            "Content-Type": "application/json",
        }

    async def create_session(self, req: KYCSessionRequest) -> KYCSessionResult:
        if not self.api_key:
            raise RuntimeError("DIDIT_API_KEY not configured")
        body = {
            "external_id": f"{req.tenant_id}:{req.case_id}:{req.party_id}",
            "callback_url": req.callback_url,
            "metadata": {
                "tenant_id": req.tenant_id,
                "case_id": req.case_id,
                "party_id": req.party_id,
                **req.metadata,
            },
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{self.base_url}/sessions",
                headers=self._headers(),
                json=body,
            )
        resp.raise_for_status()
        data = resp.json()
        return KYCSessionResult(
            provider=self.name,
            session_id=data.get("id") or data.get("session_id", ""),
            verification_url=data.get("verification_url") or data.get("url"),
            status=data.get("status", "created"),
            raw=data,
        )

    async def get_session(self, session_id: str) -> KYCSessionResult:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{self.base_url}/sessions/{session_id}",
                headers=self._headers(),
            )
        resp.raise_for_status()
        data = resp.json()
        return KYCSessionResult(
            provider=self.name,
            session_id=session_id,
            verification_url=data.get("verification_url"),
            status=data.get("status", "unknown"),
            raw=data,
        )

    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        if not self.webhook_secret:
            logger.warning("DIDIT webhook secret not configured — rejecting webhook")
            return False
        expected = hmac.new(self.webhook_secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature or "")

    def parse_webhook(self, payload: dict) -> KYCWebhookEvent:
        scores = payload.get("scores", {}) or {}
        return KYCWebhookEvent(
            session_id=payload.get("session_id") or payload.get("id", ""),
            status=payload.get("status", "unknown"),
            liveness_score=scores.get("liveness"),
            deepfake_score=scores.get("deepfake"),
            document_match=payload.get("document_match"),
            decision_reason=payload.get("decision_reason"),
            raw=payload,
        )
