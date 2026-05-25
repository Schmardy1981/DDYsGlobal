from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/api/policy", tags=["policy"])


def get_db(request: Request):
    return request.app.state.db


@router.get("/versions")
async def list_policy_versions(request: Request, tenant_id: Optional[str] = None):
    from middleware.auth_middleware import (
        get_current_user, has_permission, scope_tenant_query
    )
    user = await get_current_user(request)
    # Policy is regulator-facing — restrict reads to those who can manage
    # cases (CASE_MANAGER+) or higher.
    if not (has_permission(user, "can_manage_policies") or has_permission(user, "can_manage_cases")):
        raise HTTPException(status_code=403, detail="Insufficient permissions to read policy")
    db = get_db(request)

    query = {}
    query = scope_tenant_query(user, query, tenant_id)

    versions = await db.tenant_policy_versions.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return versions


@router.get("/rules")
async def list_rules(request: Request, tenant_id: Optional[str] = None, version_id: Optional[str] = None):
    from middleware.auth_middleware import (
        get_current_user, has_permission, scope_tenant_query
    )
    user = await get_current_user(request)
    if not (has_permission(user, "can_manage_policies") or has_permission(user, "can_manage_cases")):
        raise HTTPException(status_code=403, detail="Insufficient permissions to read policy")
    db = get_db(request)

    query = {"enabled": True}
    query = scope_tenant_query(user, query, tenant_id)
    if version_id:
        query["tenant_policy_version_id"] = version_id

    rules = await db.policy_rules.find(query, {"_id": 0}).to_list(500)
    return rules


@router.post("/rules")
async def create_rule(request: Request):
    from middleware.auth_middleware import get_current_user, has_permission
    user = await get_current_user(request)
    if not has_permission(user, "can_manage_policies"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    db = get_db(request)
    body = await request.json()

    rule = {
        "id": str(uuid.uuid4()),
        "tenant_policy_version_id": body.get("version_id"),
        "tenant_id": body.get("tenant_id"),
        "rule_key": body.get("rule_key"),
        "rule_value_json": body.get("rule_value", {}),
        "scope": body.get("scope", "tenant"),
        "priority": body.get("priority", 1),
        "enabled": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.policy_rules.insert_one({**rule})

    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": body.get("tenant_id", ""),
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "policy_rule.created",
        "entity_type": "policy_rule",
        "entity_id": rule["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": None,
        "after_json": rule,
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })

    return rule


@router.put("/rules/{rule_id}")
async def update_rule(rule_id: str, request: Request):
    from middleware.auth_middleware import get_current_user, has_permission
    user = await get_current_user(request)
    if not has_permission(user, "can_manage_policies"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    db = get_db(request)
    body = await request.json()

    before = await db.policy_rules.find_one({"id": rule_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Rule not found")

    updates = {}
    for key in ["rule_value_json", "scope", "priority", "enabled"]:
        if key in body:
            updates[key] = body[key]

    await db.policy_rules.update_one({"id": rule_id}, {"$set": updates})
    after = await db.policy_rules.find_one({"id": rule_id}, {"_id": 0})

    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": before.get("tenant_id", ""),
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "policy_rule.updated",
        "entity_type": "policy_rule",
        "entity_id": rule_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": before,
        "after_json": after,
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })

    return after


@router.post("/versions")
async def create_version(request: Request):
    from middleware.auth_middleware import get_current_user, has_permission
    user = await get_current_user(request)
    if not has_permission(user, "can_manage_policies"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    db = get_db(request)
    body = await request.json()

    version = {
        "id": str(uuid.uuid4()),
        "tenant_id": body.get("tenant_id"),
        "version_name": body.get("version_name"),
        "based_on_kos_version": body.get("based_on_kos_version", "1.11"),
        "effective_from": body.get("effective_from", datetime.now(timezone.utc).isoformat()),
        "effective_to": None,
        "status": "draft",
        "change_summary": body.get("change_summary", ""),
        "approved_by": None,
        "approved_at": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.tenant_policy_versions.insert_one({**version})
    return version
