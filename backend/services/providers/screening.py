"""Screening provider implementations (sanctions / PEP / adverse media)."""

from __future__ import annotations

import logging
import random
from typing import Optional

import httpx

from .base import ScreeningHit, ScreeningProvider, ScreeningQuery

logger = logging.getLogger(__name__)


class MockScreeningProvider(ScreeningProvider):
    """Deterministically-random mock used in dev/test.

    Returns at most one hit per ``list_type`` requested, with a ~20% chance per
    type. Matches the behaviour of the legacy ``mock_screen_party`` helper so
    UI flows keep working without external credentials.
    """

    name = "mock"

    _TEMPLATES: dict[str, list[dict]] = {
        "sanctions": [
            {"list_source": "UN Security Council", "hit_severity": "high", "match_score": 0.85},
            {"list_source": "EU Sanctions", "hit_severity": "high", "match_score": 0.72},
            {"list_source": "OFAC SDN", "hit_severity": "high", "match_score": 0.68},
        ],
        "pep": [
            {"list_source": "World-Check PEP", "hit_severity": "medium", "match_score": 0.78},
            {"list_source": "PEP Database", "hit_severity": "medium", "match_score": 0.65},
        ],
        "adverse_media": [
            {"list_source": "Adverse Media DB", "hit_severity": "low", "match_score": 0.55},
            {"list_source": "News Analytics", "hit_severity": "medium", "match_score": 0.62},
        ],
    }

    async def screen(self, query: ScreeningQuery) -> list[ScreeningHit]:
        hits: list[ScreeningHit] = []
        for list_type in query.list_types:
            templates = self._TEMPLATES.get(list_type) or self._TEMPLATES["sanctions"]
            if random.random() < 0.2:
                template = random.choice(templates)
                hits.append(
                    ScreeningHit(
                        list_source=template["list_source"],
                        hit_severity=template["hit_severity"],
                        match_score=template["match_score"],
                        matched_name=f"{query.name} (partial match)",
                        list_type=list_type,
                        details={
                            "matched_entity": query.name,
                            "match_type": "name_fuzzy",
                            "additional_info": f"Mock {list_type} hit for testing",
                            "source_url": f"https://example.com/{list_type}/reference",
                        },
                    )
                )
        return hits


class WorldCheckProvider(ScreeningProvider):
    """Refinitiv World-Check One v2 adapter — stub.

    The full API requires HMAC-signed requests with a per-request canonical
    string. This stub validates configuration and shapes the response; wiring
    the actual signature flow is the only step left before going live.
    """

    name = "worldcheck"

    def __init__(self, api_key: str, api_secret: str, group_id: str, base_url: str):
        self.api_key = api_key
        self.api_secret = api_secret
        self.group_id = group_id
        self.base_url = base_url.rstrip("/")

    async def screen(self, query: ScreeningQuery) -> list[ScreeningHit]:
        if not self.api_key or not self.api_secret or not self.group_id:
            logger.warning(
                "WorldCheck not fully configured (api_key/api_secret/group_id); returning empty hits"
            )
            return []
        # TODO: sign request per Refinitiv HMAC spec and parse the cases/results
        # response into ScreeningHit instances. Configuration is wired so the
        # platform can be flipped over without touching call sites.
        logger.info("WorldCheck screen request not yet implemented; returning empty hits")
        return []


class ComplyAdvantageProvider(ScreeningProvider):
    """ComplyAdvantage adapter — stub."""

    name = "complyadvantage"

    def __init__(self, api_key: str, base_url: str):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def screen(self, query: ScreeningQuery) -> list[ScreeningHit]:
        if not self.api_key:
            logger.warning("ComplyAdvantage API key not configured; returning empty hits")
            return []
        body = {
            "search_term": query.name,
            "client_ref": query.party_id,
            "fuzziness": 0.6,
            "filters": {"types": query.list_types},
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/searches",
                    params={"api_key": self.api_key},
                    json=body,
                )
            if resp.status_code >= 300:
                logger.warning(
                    "ComplyAdvantage HTTP %s: %s", resp.status_code, resp.text[:300]
                )
                return []
            data = resp.json()
        except Exception:  # noqa: BLE001
            logger.exception("ComplyAdvantage request failed")
            return []

        hits: list[ScreeningHit] = []
        for entity in (data.get("content", {}).get("data", {}).get("hits") or []):
            details = entity.get("doc", {}) or {}
            hits.append(
                ScreeningHit(
                    list_source=details.get("source_notes", "ComplyAdvantage"),
                    hit_severity=_severity_from_types(details.get("types", [])),
                    match_score=float(entity.get("score", 0)) / 100.0,
                    matched_name=details.get("name", query.name),
                    list_type=_primary_list_type(details.get("types", [])),
                    details=details,
                )
            )
        return hits


def _severity_from_types(types: list[str]) -> str:
    if any(t.startswith("sanction") for t in types):
        return "high"
    if any(t.startswith("pep") for t in types):
        return "medium"
    return "low"


def _primary_list_type(types: list[str]) -> str:
    for t in types:
        if t.startswith("sanction"):
            return "sanctions"
        if t.startswith("pep"):
            return "pep"
        if t.startswith("adverse"):
            return "adverse_media"
    return "adverse_media"
