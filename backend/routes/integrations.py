from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import uuid
from datetime import datetime, timezone

from services.secrets import encrypt_secret, decrypt_secret, is_encrypted

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


def get_db(request: Request):
    return request.app.state.db


# Default integrations registry
DEFAULT_INTEGRATIONS = [
    {
        "key": "llm_anthropic",
        "name": "Anthropic Claude",
        "category": "AI / LLM",
        "description": "Document Intelligence, OSINT Risk Analysis, Field Extraction",
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "placeholder": "sk-ant-..."},
            {"key": "model", "label": "Model", "type": "text", "placeholder": "claude-sonnet-4-5-20250929"},
        ],
        "icon": "brain",
    },
    {
        "key": "llm_openai",
        "name": "OpenAI",
        "category": "AI / LLM",
        "description": "Alternative LLM provider for document analysis",
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "placeholder": "sk-..."},
            {"key": "model", "label": "Model", "type": "text", "placeholder": "gpt-5.2"},
        ],
        "icon": "sparkles",
    },
    {
        "key": "didit",
        "name": "DIDIT",
        "category": "Identity Verification",
        "description": "Identity verification, document authenticity, liveness detection",
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "placeholder": "didit_..."},
            {"key": "api_secret", "label": "API Secret", "type": "password", "placeholder": ""},
            {"key": "base_url", "label": "Base URL", "type": "text", "placeholder": "https://api.didit.me/v1"},
            {"key": "webhook_secret", "label": "Webhook Secret", "type": "password", "placeholder": ""},
        ],
        "icon": "fingerprint",
    },
    {
        "key": "screening_worldcheck",
        "name": "Refinitiv World-Check",
        "category": "Screening",
        "description": "Sanctions, PEP, and adverse media screening",
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "placeholder": ""},
            {"key": "api_secret", "label": "API Secret", "type": "password", "placeholder": ""},
            {"key": "group_id", "label": "Group ID", "type": "text", "placeholder": ""},
            {"key": "base_url", "label": "Base URL", "type": "text", "placeholder": "https://rms-world-check-one-api-pilot.thomsonreuters.com/v2"},
        ],
        "icon": "shield-check",
    },
    {
        "key": "screening_complyadvantage",
        "name": "ComplyAdvantage",
        "category": "Screening",
        "description": "AML screening, transaction monitoring, adverse media",
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "placeholder": ""},
            {"key": "base_url", "label": "Base URL", "type": "text", "placeholder": "https://api.complyadvantage.com"},
        ],
        "icon": "search",
    },
    {
        "key": "email_sendgrid",
        "name": "SendGrid",
        "category": "Email",
        "description": "Transactional emails for invitations, reminders, notifications",
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "placeholder": "SG.xxx"},
            {"key": "from_email", "label": "From Email", "type": "text", "placeholder": "noreply@ddys.com"},
            {"key": "from_name", "label": "From Name", "type": "text", "placeholder": "DDYs Compliance"},
        ],
        "icon": "mail",
    },
    {
        "key": "email_resend",
        "name": "Resend",
        "category": "Email",
        "description": "Modern email API for transactional emails",
        "fields": [
            {"key": "api_key", "label": "API Key", "type": "password", "placeholder": "re_xxx"},
            {"key": "from_email", "label": "From Email", "type": "text", "placeholder": "noreply@ddys.com"},
        ],
        "icon": "mail",
    },
    {
        "key": "storage_supabase",
        "name": "Supabase Storage",
        "category": "Storage",
        "description": "Document storage, video recordings, KYC file exports",
        "fields": [
            {"key": "url", "label": "Supabase URL", "type": "text", "placeholder": "https://xxx.supabase.co"},
            {"key": "anon_key", "label": "Anon Key", "type": "password", "placeholder": ""},
            {"key": "service_key", "label": "Service Key", "type": "password", "placeholder": ""},
        ],
        "icon": "database",
    },
    {
        "key": "emergent_llm",
        "name": "Emergent Universal Key",
        "category": "AI / LLM",
        "description": "Universal key for Claude, GPT, Gemini via Emergent platform",
        "fields": [
            {"key": "api_key", "label": "Universal Key", "type": "password", "placeholder": "sk-emergent-..."},
        ],
        "icon": "key",
    },
]


def _password_field_keys(integ_def: dict) -> set:
    return {f["key"] for f in integ_def.get("fields", []) if f["type"] == "password"}


@router.get("")
async def list_integrations(request: Request):
    from middleware.auth_middleware import get_current_user, has_permission
    user = await get_current_user(request)
    # Knowing which integrations are configured is sensitive (it tells an
    # attacker which third-party services to attempt to compromise). Limit
    # reads to those who can manage integrations.
    if not has_permission(user, "can_manage_integrations"):
        raise HTTPException(status_code=403, detail="Missing permission: can_manage_integrations")
    db = get_db(request)

    saved = await db.integrations.find({}, {"_id": 0}).to_list(100)
    saved_map = {s["key"]: s for s in saved}

    result = []
    for integ in DEFAULT_INTEGRATIONS:
        entry = {**integ}
        saved_config = saved_map.get(integ["key"], {})
        entry["enabled"] = saved_config.get("enabled", False)
        entry["connected"] = saved_config.get("connected", False)
        entry["last_tested"] = saved_config.get("last_tested")
        # Mask API keys — never echo raw or encrypted values
        entry["configured_fields"] = {}
        pwd_keys = _password_field_keys(integ)
        for field in integ["fields"]:
            val = saved_config.get("values", {}).get(field["key"], "")
            if field["key"] in pwd_keys:
                entry["configured_fields"][field["key"]] = "***configured***" if val else ""
            else:
                entry["configured_fields"][field["key"]] = val
        result.append(entry)

    return result


@router.put("/{key}")
async def update_integration(key: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    if user.get("global_role") not in ["ADMIN"]:
        raise HTTPException(status_code=403, detail="Only super admin can manage integrations")
    db = get_db(request)
    body = await request.json()

    integ_def = next((i for i in DEFAULT_INTEGRATIONS if i["key"] == key), None)
    if not integ_def:
        raise HTTPException(status_code=404, detail="Integration not found")

    existing = await db.integrations.find_one({"key": key}, {"_id": 0})
    existing_values = existing.get("values", {}) if existing else {}

    update = {
        "key": key,
        "name": integ_def["name"],
        "category": integ_def["category"],
        "enabled": body.get("enabled", existing.get("enabled", False) if existing else False),
        "values": {},
        "updated_by": user["user_id"],
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    new_values = body.get("values", {})
    pwd_keys = _password_field_keys(integ_def)
    for field in integ_def["fields"]:
        fkey = field["key"]
        new_val = new_values.get(fkey, "")
        if new_val and new_val != "***configured***":
            # New value supplied. Encrypt at rest if it's a secret field.
            update["values"][fkey] = encrypt_secret(new_val) if fkey in pwd_keys else new_val
        elif fkey in existing_values:
            update["values"][fkey] = existing_values[fkey]

    has_key = any(update["values"].get(k) for k in pwd_keys)
    update["connected"] = has_key and update["enabled"]

    await db.integrations.update_one(
        {"key": key},
        {"$set": update},
        upsert=True
    )

    try:
        from services.providers import reset_provider_singletons
        reset_provider_singletons()
    except Exception:
        pass

    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": "",
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": f"integration.{key}.updated",
        "entity_type": "integration",
        "entity_id": key,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": {"enabled": existing.get("enabled") if existing else None},
        "after_json": {"enabled": update["enabled"], "connected": update["connected"]},
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })

    return {"message": f"Integration '{integ_def['name']}' updated", "connected": update["connected"], "enabled": update["enabled"]}


@router.post("/{key}/test")
async def test_integration(key: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    if user.get("global_role") not in ["ADMIN"]:
        raise HTTPException(status_code=403, detail="Only super admin can test integrations")
    db = get_db(request)

    config = await db.integrations.find_one({"key": key}, {"_id": 0})
    if not config or not config.get("enabled"):
        return {"success": False, "message": "Integration not enabled"}

    await db.integrations.update_one(
        {"key": key},
        {"$set": {"last_tested": datetime.now(timezone.utc).isoformat(), "test_result": "success"}}
    )

    return {"success": True, "message": f"Connection to {config.get('name', key)} successful (mock test)"}


# --- Helpers exposed for providers to fetch decrypted secrets ---

async def get_integration_values(db, key: str) -> dict:
    """Return a *decrypted* copy of an integration's saved values.

    Provider code should never read the raw ``integrations.values`` dict
    directly — it'll see ciphertext after the encryption migration. Going
    through this helper guarantees plaintext at the point of use without
    storing plaintext at rest.
    """
    config = await db.integrations.find_one({"key": key}, {"_id": 0})
    if not config:
        return {}
    integ_def = next((i for i in DEFAULT_INTEGRATIONS if i["key"] == key), None)
    pwd_keys = _password_field_keys(integ_def) if integ_def else set()
    out = {}
    for k, v in (config.get("values") or {}).items():
        if k in pwd_keys:
            out[k] = decrypt_secret(v) if is_encrypted(v) else v
        else:
            out[k] = v
    return out
