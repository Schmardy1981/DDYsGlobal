"""Screening orchestration.

The actual sanctions / PEP / adverse-media lookups are delegated to a pluggable
provider (see :mod:`services.providers`). This module is responsible for
turning a party record into a provider query, persisting hits, and keeping the
legacy callable name (``mock_screen_party``) so existing routes keep working
without a sweeping rename.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from .providers import get_screening_provider
from .providers.base import ScreeningQuery


def _party_display_name(party: dict) -> str:
    name = f"{party.get('first_name', '')} {party.get('last_name', '')}".strip()
    return name or party.get("legal_name") or "Unknown"


async def screen_party(db, screening_run: dict, party: dict, run_type: str) -> list[dict]:
    """Screen a single party and persist any hits. Returns the hit dicts."""
    provider = await get_screening_provider(db)
    query = ScreeningQuery(
        tenant_id=screening_run["tenant_id"],
        party_id=party["id"],
        name=_party_display_name(party),
        date_of_birth=party.get("date_of_birth"),
        nationality=party.get("nationality"),
        list_types=[run_type],
    )
    provider_hits = await provider.screen(query)

    persisted: list[dict] = []
    for hit in provider_hits:
        rec = {
            "id": str(uuid.uuid4()),
            "screening_run_id": screening_run["id"],
            "party_id": party["id"],
            "tenant_id": screening_run["tenant_id"],
            "hit_severity": hit.hit_severity,
            "match_score": hit.match_score,
            "matched_name": hit.matched_name,
            "list_source": hit.list_source,
            "details_json": hit.details,
            "list_type": hit.list_type,
            "provider": provider.name,
            "disposition": "open",
            "decided_by": None,
            "decided_at": None,
            "notes": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.screening_hits.insert_one({**rec})
        persisted.append(rec)

    return persisted


# Backwards-compatible alias for callers that still import the old name.
mock_screen_party = screen_party
