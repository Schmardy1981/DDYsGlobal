"""Email provider implementations."""

from __future__ import annotations

import json
import logging
import uuid
from typing import Optional

import httpx

from .base import EmailMessage, EmailProvider, EmailSendResult

logger = logging.getLogger(__name__)


class MockEmailProvider(EmailProvider):
    """No-op provider used in dev/test — records the message in the log."""

    name = "mock"

    async def send(self, message: EmailMessage) -> EmailSendResult:
        msg_id = f"mock-{uuid.uuid4().hex[:12]}"
        logger.info(
            "MOCK EMAIL to=%s subject=%s body_preview=%r id=%s",
            message.to,
            message.subject,
            message.body_text[:120],
            msg_id,
        )
        return EmailSendResult(success=True, provider=self.name, message_id=msg_id)


class SendGridEmailProvider(EmailProvider):
    """SendGrid v3 transactional email adapter.

    Uses the v3 ``/mail/send`` endpoint. We deliberately keep the request body
    minimal so the same adapter works for plain-text invitations and richer
    HTML reminders.
    """

    name = "sendgrid"
    _ENDPOINT = "https://api.sendgrid.com/v3/mail/send"

    def __init__(self, api_key: str, from_email: str, from_name: str = "DDYs Compliance"):
        self.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name

    async def send(self, message: EmailMessage) -> EmailSendResult:
        if not self.api_key:
            return EmailSendResult(
                success=False,
                provider=self.name,
                error="SENDGRID_API_KEY not configured",
            )

        body: dict = {
            "personalizations": [{"to": [{"email": message.to}]}],
            "from": {"email": self.from_email, "name": self.from_name},
            "subject": message.subject,
            "content": [{"type": "text/plain", "value": message.body_text}],
        }
        if message.body_html:
            body["content"].append({"type": "text/html", "value": message.body_html})
        if message.reply_to:
            body["reply_to"] = {"email": message.reply_to}
        if message.metadata:
            body["custom_args"] = {k: str(v) for k, v in message.metadata.items()}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._ENDPOINT, headers=headers, content=json.dumps(body))
            if 200 <= resp.status_code < 300:
                message_id = resp.headers.get("X-Message-Id") or resp.headers.get("X-Message-ID")
                return EmailSendResult(success=True, provider=self.name, message_id=message_id)
            logger.warning(
                "SendGrid send failed: status=%s body=%s", resp.status_code, resp.text[:500]
            )
            return EmailSendResult(
                success=False,
                provider=self.name,
                error=f"HTTP {resp.status_code}: {resp.text[:200]}",
            )
        except Exception as exc:  # noqa: BLE001 - log and surface
            logger.exception("SendGrid send raised an exception")
            return EmailSendResult(success=False, provider=self.name, error=str(exc))
