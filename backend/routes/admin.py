from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import uuid
import bcrypt
from datetime import datetime, timezone

router = APIRouter(prefix="/api/admin", tags=["admin"])


def get_db(request: Request):
    return request.app.state.db


@router.get("/users")
async def list_all_users(request: Request, global_role: Optional[str] = None):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    if user.get("global_role") not in ["ADMIN"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    db = get_db(request)
    
    query = {}
    if global_role:
        query["global_role"] = global_role
    
    users = await db.users.find(query, {"_id": 0, "password_hash": 0, "mfa_secret": 0}).to_list(1000)
    
    # Attach tenant roles
    for u in users:
        roles = await db.user_tenant_roles.find({"user_id": u["id"]}, {"_id": 0}).to_list(100)
        u["tenant_roles"] = roles
    
    return users


@router.post("/users")
async def create_user(request: Request):
    from middleware.auth_middleware import get_current_user
    admin = await get_current_user(request)
    if admin.get("global_role") not in ["ADMIN"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    db = get_db(request)
    body = await request.json()
    
    # Check if email exists
    existing = await db.users.find_one({"email": body["email"]}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already exists")
    
    # Minimum complexity for an admin-provisioned password. Users created
    # without a supplied password are still flagged with
    # `must_change_password: True` so the next login forces a rotation —
    # the admin can no longer leave the default `Welcome123!` in place.
    password = body.get("password") or "Welcome123!"
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    user = {
        "id": str(uuid.uuid4()),
        "email": body["email"],
        "name": body.get("name", ""),
        "global_role": body.get("global_role"),
        "password_hash": password_hash,
        "mfa_enabled": False,
        "mfa_secret": None,
        "must_change_password": True,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.users.insert_one({**user})
    
    # Assign tenant roles if provided
    tenant_roles = body.get("tenant_roles", [])
    for tr in tenant_roles:
        role_doc = {
            "id": str(uuid.uuid4()),
            "user_id": user["id"],
            "tenant_id": tr["tenant_id"],
            "role": tr["role"],
            "active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.user_tenant_roles.insert_one({**role_doc})
    
    safe_user = {k: v for k, v in user.items() if k not in ["password_hash", "mfa_secret"]}
    safe_user["tenant_roles"] = tenant_roles
    
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": "",
        "actor_user_id": admin["user_id"],
        "actor_role": admin.get("global_role", ""),
        "action_key": "user.created",
        "entity_type": "user",
        "entity_id": user["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": None,
        "after_json": safe_user,
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })
    
    return safe_user


@router.put("/users/{user_id}")
async def update_user(user_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    admin = await get_current_user(request)
    if admin.get("global_role") not in ["ADMIN"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    db = get_db(request)
    body = await request.json()
    
    before = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0, "mfa_secret": 0})
    if not before:
        raise HTTPException(status_code=404, detail="User not found")
    
    updates = {}
    for key in ["name", "global_role", "status", "mfa_enabled"]:
        if key in body:
            updates[key] = body[key]
    
    if "password" in body and body["password"]:
        updates["password_hash"] = bcrypt.hashpw(body["password"].encode(), bcrypt.gensalt()).decode()
    
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.users.update_one({"id": user_id}, {"$set": updates})
    
    # Update tenant roles if provided
    if "tenant_roles" in body:
        await db.user_tenant_roles.delete_many({"user_id": user_id})
        for tr in body["tenant_roles"]:
            role_doc = {
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "tenant_id": tr["tenant_id"],
                "role": tr["role"],
                "active": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            await db.user_tenant_roles.insert_one({**role_doc})
    
    after = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0, "mfa_secret": 0})
    return after


@router.get("/settings")
async def get_settings(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    if user.get("global_role") not in ["ADMIN"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    db = get_db(request)
    
    settings = await db.system_settings.find_one({"key": "global"}, {"_id": 0})
    if not settings:
        settings = {
            "key": "global",
            "llm_provider": "anthropic",
            "llm_model": "claude-sonnet-4-5-20250929",
            "llm_api_key_set": bool(os.environ.get("EMERGENT_LLM_KEY")),
            "custom_llm_key": "",
            "email_provider": "mock",
            "email_api_key": "",
            "screening_provider": "mock",
            "screening_api_key": "",
            "video_ident_provider": "mock"
        }
    
    # Never return actual API keys
    if settings.get("custom_llm_key"):
        settings["custom_llm_key"] = "***configured***"
    if settings.get("email_api_key"):
        settings["email_api_key"] = "***configured***"
    if settings.get("screening_api_key"):
        settings["screening_api_key"] = "***configured***"
    
    return settings


import os

# Field names in system_settings:global that contain secret material and
# must be encrypted at rest.
_SECRET_SETTINGS_FIELDS = {"custom_llm_key", "email_api_key", "screening_api_key"}

@router.put("/settings")
async def update_settings(request: Request):
    from middleware.auth_middleware import get_current_user
    from services.secrets import encrypt_secret
    user = await get_current_user(request)
    if user.get("global_role") not in ["ADMIN"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    db = get_db(request)
    body = await request.json()

    updates = {}
    for key in ["llm_provider", "llm_model", "custom_llm_key", "email_provider", "email_api_key", "screening_provider", "screening_api_key", "video_ident_provider"]:
        if key in body:
            value = body[key]
            if key in _SECRET_SETTINGS_FIELDS and value and value != "***configured***":
                value = encrypt_secret(value)
            elif value == "***configured***":
                # Don't overwrite an existing encrypted secret with the mask.
                continue
            updates[key] = value

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.system_settings.update_one(
        {"key": "global"},
        {"$set": updates},
        upsert=True
    )
    
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": "",
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "settings.updated",
        "entity_type": "system_settings",
        "entity_id": "global",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": None,
        "after_json": {k: v for k, v in updates.items() if "key" not in k.lower() or k == "key"},
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })
    
    return {"message": "Settings updated"}


@router.post("/seed")
async def seed_demo_data(request: Request):
    """Seed demo data for testing. ADMIN-only."""
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    if user.get("global_role") != "ADMIN":
        raise HTTPException(status_code=403, detail="Only ADMIN can seed")
    db = get_db(request)

    existing = await db.tenants.find_one({"name": "Demo Bank"}, {"_id": 0})
    if existing:
        return {"message": "Demo data already exists", "tenant_id": existing["id"]}

    from routes.seed import seed_all
    result = await seed_all(db)
    return result
