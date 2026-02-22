from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/api/tenants", tags=["tenants"])


class TenantCreate(BaseModel):
    name: str
    legal_name: str
    default_jurisdiction: str = "EU"
    branding_json: Optional[dict] = None

class TenantUpdate(BaseModel):
    name: Optional[str] = None
    legal_name: Optional[str] = None
    default_jurisdiction: Optional[str] = None
    branding_json: Optional[dict] = None
    status: Optional[str] = None


def get_db(request: Request):
    return request.app.state.db


@router.get("")
async def list_tenants(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    if user.get("global_role") in ["GLOBAL_SUPER_ADMIN", "DDYS_COMPLIANCE_MANAGER"]:
        tenants = await db.tenants.find({"deleted": {"$ne": True}}, {"_id": 0}).to_list(500)
    else:
        tenant_ids = [tr["tenant_id"] for tr in user.get("tenant_roles", [])]
        tenants = await db.tenants.find({"id": {"$in": tenant_ids}, "deleted": {"$ne": True}}, {"_id": 0}).to_list(500)
    return tenants


@router.post("")
async def create_tenant(body: TenantCreate, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    if user.get("global_role") not in ["GLOBAL_SUPER_ADMIN"]:
        raise HTTPException(status_code=403, detail="Only super admin can create tenants")
    
    db = get_db(request)
    tenant = {
        "id": str(uuid.uuid4()),
        "name": body.name,
        "legal_name": body.legal_name,
        "default_jurisdiction": body.default_jurisdiction,
        "branding_json": body.branding_json or {"primary_color": "#0F172A", "logo_url": ""},
        "status": "active",
        "created_by": user["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "deleted": False
    }
    await db.tenants.insert_one({**tenant})
    
    # Create default policy version for tenant
    policy_version = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant["id"],
        "version_name": "KOS v1.11 Baseline",
        "based_on_kos_version": "1.11",
        "effective_from": datetime.now(timezone.utc).isoformat(),
        "effective_to": None,
        "status": "active",
        "change_summary": "Initial KOS v1.11 baseline policy",
        "approved_by": user["user_id"],
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.tenant_policy_versions.insert_one({**policy_version})
    
    # Create default policy rules
    default_rules = [
        {"rule_key": "rr_cycle_high", "rule_value_json": {"months": 12}, "scope": "global"},
        {"rule_key": "rr_cycle_medium", "rule_value_json": {"months": 24}, "scope": "global"},
        {"rule_key": "rr_cycle_low", "rule_value_json": {"months": 60}, "scope": "global"},
        {"rule_key": "edr_alert_review_days", "rule_value_json": {"days": 28}, "scope": "global"},
        {"rule_key": "edr_completion_days", "rule_value_json": {"days": 90}, "scope": "global"},
        {"rule_key": "temp_waiver_max_days", "rule_value_json": {"days": 90}, "scope": "global"},
        {"rule_key": "liveness_threshold", "rule_value_json": {"min_score": 0.70}, "scope": "global"},
        {"rule_key": "deepfake_threshold", "rule_value_json": {"max_score": 0.30}, "scope": "global"},
        {"rule_key": "poa_recency_natural_months", "rule_value_json": {"months": 3}, "scope": "global"},
        {"rule_key": "poa_recency_legal_months", "rule_value_json": {"months": 12}, "scope": "global"},
        {"rule_key": "attestation_max_months_before_signoff", "rule_value_json": {"months": 6}, "scope": "global"},
    ]
    for rule in default_rules:
        rule_doc = {
            "id": str(uuid.uuid4()),
            "tenant_policy_version_id": policy_version["id"],
            "tenant_id": tenant["id"],
            **rule,
            "priority": 1,
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.policy_rules.insert_one({**rule_doc})
    
    # Log audit
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": tenant["id"],
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "tenant.created",
        "entity_type": "tenant",
        "entity_id": tenant["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": None,
        "after_json": tenant,
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })
    
    return tenant


@router.get("/{tenant_id}")
async def get_tenant(tenant_id: str, request: Request):
    from middleware.auth_middleware import get_current_user, require_tenant_access
    user = await get_current_user(request)
    require_tenant_access(tenant_id, user)
    db = get_db(request)
    
    tenant = await db.tenants.find_one({"id": tenant_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.put("/{tenant_id}")
async def update_tenant(tenant_id: str, body: TenantUpdate, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    if user.get("global_role") not in ["GLOBAL_SUPER_ADMIN", "TENANT_ADMIN"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    db = get_db(request)
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    before = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    await db.tenants.update_one({"id": tenant_id}, {"$set": updates})
    after = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "tenant.updated",
        "entity_type": "tenant",
        "entity_id": tenant_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": before,
        "after_json": after,
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })
    
    return after


@router.get("/{tenant_id}/users")
async def list_tenant_users(tenant_id: str, request: Request):
    from middleware.auth_middleware import get_current_user, require_tenant_access
    user = await get_current_user(request)
    require_tenant_access(tenant_id, user)
    db = get_db(request)
    
    roles = await db.user_tenant_roles.find({"tenant_id": tenant_id, "active": True}, {"_id": 0}).to_list(500)
    user_ids = [r["user_id"] for r in roles]
    users = await db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "password_hash": 0, "mfa_secret": 0}).to_list(500)
    
    # Attach roles
    role_map = {}
    for r in roles:
        role_map.setdefault(r["user_id"], []).append(r["role"])
    for u in users:
        u["roles"] = role_map.get(u["id"], [])
    
    return users


@router.get("/public/list")
async def public_tenant_list(request: Request):
    db = get_db(request)
    tenants = await db.tenants.find(
        {"status": "active", "deleted": {"$ne": True}},
        {"_id": 0, "id": 1, "name": 1, "branding_json": 1}
    ).to_list(500)
    return tenants


@router.get("/{tenant_id}/regulations")
async def get_tenant_regulations(tenant_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    regs = await db.tenant_regulations.find({"tenant_id": tenant_id}, {"_id": 0}).to_list(100)
    return regs


@router.post("/{tenant_id}/regulations")
async def add_tenant_regulation(tenant_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()

    reg = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "framework": body.get("framework", ""),  # e.g. MiCAR, SEC, FMA, FINMA
        "jurisdiction": body.get("jurisdiction", ""),  # e.g. EU, US, LI, CH
        "description": body.get("description", ""),
        "required_documents": body.get("required_documents", []),
        "rules_json": body.get("rules_json", {}),
        "active": True,
        "created_by": user["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.tenant_regulations.insert_one({**reg})
    return reg


@router.put("/{tenant_id}/regulations/{reg_id}")
async def update_tenant_regulation(tenant_id: str, reg_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()

    updates = {}
    for key in ["framework", "jurisdiction", "description", "required_documents", "rules_json", "active"]:
        if key in body:
            updates[key] = body[key]
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.tenant_regulations.update_one({"id": reg_id}, {"$set": updates})
    return await db.tenant_regulations.find_one({"id": reg_id}, {"_id": 0})


@router.delete("/{tenant_id}/regulations/{reg_id}")
async def delete_tenant_regulation(tenant_id: str, reg_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    await db.tenant_regulations.delete_one({"id": reg_id})
    return {"message": "Deleted"}

