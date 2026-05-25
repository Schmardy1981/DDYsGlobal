"""Baseline migration: create indexes for all core collections.

Before this migration the platform relied on full-collection scans for every
query. This migration registers the indexes that match the access patterns
already used by ``routes/`` and ``services/``.
"""

from __future__ import annotations

import logging
from pymongo import ASCENDING, DESCENDING

logger = logging.getLogger(__name__)


# (collection, keys, options)
INDEX_SPECS: list[tuple[str, list[tuple[str, int]], dict]] = [
    # auth / users
    ("users", [("email", ASCENDING)], {"unique": True, "name": "users_email_unique"}),
    ("users", [("id", ASCENDING)], {"unique": True, "name": "users_id_unique"}),
    ("user_tenant_roles", [("user_id", ASCENDING), ("tenant_id", ASCENDING)], {"name": "user_tenant_roles_lookup"}),
    ("user_tenant_roles", [("tenant_id", ASCENDING), ("active", ASCENDING)], {"name": "user_tenant_roles_active"}),
    ("otp_codes", [("email", ASCENDING), ("code", ASCENDING)], {"name": "otp_codes_lookup"}),
    ("otp_codes", [("expires_at", ASCENDING)], {"name": "otp_codes_expiry", "expireAfterSeconds": 0}),

    # tenants
    ("tenants", [("id", ASCENDING)], {"unique": True, "name": "tenants_id_unique"}),
    ("tenants", [("name", ASCENDING)], {"name": "tenants_name"}),

    # cases & related
    ("cases", [("id", ASCENDING)], {"unique": True, "name": "cases_id_unique"}),
    ("cases", [("tenant_id", ASCENDING), ("status", ASCENDING)], {"name": "cases_tenant_status"}),
    ("cases", [("tenant_id", ASCENDING), ("created_at", DESCENDING)], {"name": "cases_tenant_created"}),
    ("parties", [("case_id", ASCENDING)], {"name": "parties_case"}),
    ("parties", [("tenant_id", ASCENDING)], {"name": "parties_tenant"}),
    ("requirement_items", [("case_id", ASCENDING)], {"name": "req_items_case"}),
    ("requirement_items", [("tenant_id", ASCENDING), ("status", ASCENDING)], {"name": "req_items_tenant_status"}),

    # documents
    ("documents", [("id", ASCENDING)], {"unique": True, "name": "documents_id_unique"}),
    ("documents", [("tenant_id", ASCENDING), ("case_id", ASCENDING)], {"name": "documents_tenant_case"}),
    ("documents", [("file_hash", ASCENDING)], {"name": "documents_hash"}),
    ("documents", [("requirement_item_id", ASCENDING)], {"name": "documents_req_item", "sparse": True}),
    ("document_ai_results", [("document_id", ASCENDING)], {"name": "ai_results_doc"}),

    # screening
    ("screening_results", [("tenant_id", ASCENDING), ("party_id", ASCENDING)], {"name": "screening_tenant_party"}),
    ("screening_results", [("case_id", ASCENDING)], {"name": "screening_case"}),

    # risk & waivers & approvals
    ("risk_scores", [("case_id", ASCENDING)], {"name": "risk_case"}),
    ("waivers", [("tenant_id", ASCENDING), ("status", ASCENDING)], {"name": "waivers_tenant_status"}),
    ("waivers", [("case_id", ASCENDING)], {"name": "waivers_case"}),
    ("waivers", [("expires_at", ASCENDING)], {"name": "waivers_expiry", "sparse": True}),
    ("approvals", [("tenant_id", ASCENDING), ("status", ASCENDING)], {"name": "approvals_tenant_status"}),

    # audit
    ("audit_logs", [("tenant_id", ASCENDING), ("timestamp", DESCENDING)], {"name": "audit_tenant_time"}),
    ("audit_logs", [("entity_type", ASCENDING), ("entity_id", ASCENDING)], {"name": "audit_entity"}),
    ("audit_logs", [("actor_user_id", ASCENDING), ("timestamp", DESCENDING)], {"name": "audit_actor"}),

    # notifications
    ("notifications", [("user_id", ASCENDING), ("read", ASCENDING), ("created_at", DESCENDING)], {"name": "notifications_user_read"}),

    # integrations & settings
    ("integrations", [("key", ASCENDING)], {"unique": True, "name": "integrations_key_unique"}),
    ("system_settings", [("key", ASCENDING)], {"unique": True, "name": "system_settings_key_unique"}),

    # reminders / EDR / video ident
    ("reminders", [("tenant_id", ASCENDING), ("due_date", ASCENDING)], {"name": "reminders_due"}),
    ("edr_cases", [("tenant_id", ASCENDING), ("status", ASCENDING)], {"name": "edr_tenant_status"}),
    ("video_ident_sessions", [("case_id", ASCENDING)], {"name": "video_ident_case"}),

    # exports
    ("kyc_exports", [("case_id", ASCENDING), ("created_at", DESCENDING)], {"name": "kyc_exports_case"}),
]


async def up(db) -> None:
    for collection, keys, options in INDEX_SPECS:
        try:
            await db[collection].create_index(keys, **options)
            logger.info("Created index %s on %s", options.get("name"), collection)
        except Exception as exc:  # noqa: BLE001 - log and continue; index may already exist with diff opts
            logger.warning(
                "Skipping index %s on %s: %s",
                options.get("name"),
                collection,
                exc,
            )


async def down(db) -> None:
    for collection, _keys, options in INDEX_SPECS:
        name = options.get("name")
        if not name:
            continue
        try:
            await db[collection].drop_index(name)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not drop index %s on %s: %s", name, collection, exc)
