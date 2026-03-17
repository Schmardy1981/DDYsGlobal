from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / '.env')

JWT_SECRET = os.environ.get('JWT_SECRET')
security = HTTPBearer(auto_error=False)

# =============================================================================
# ROLE SYSTEM (4 Zugänge)
# =============================================================================
#
# 1. ADMIN          — DDYs Plattform-Administratoren (voller Zugriff)
# 2. CASE_MANAGER   — DDYs-Mitarbeiter die Bankkunden betreuen
#                      (Case-Bearbeitung, QA, Screening, Maker/Checker)
# 3. VIDEO_AGENT    — Mitarbeiter für Video-Identifikation
# 4. BANK_USER      — Bankkunden (Tenant-scoped, nur eigene Kundendaten)
#
# END_CUSTOMER wird intern für Endkunden-Portal behalten (kein Staff-Zugang)
# =============================================================================

ROLE_HIERARCHY = {
    "ADMIN": 100,
    "CASE_MANAGER": 80,
    "VIDEO_AGENT": 50,
    "BANK_USER": 30,
    "END_CUSTOMER": 10,
}

PORTAL_ACCESS = {
    "admin": ["ADMIN"],
    "workspace": ["ADMIN", "CASE_MANAGER", "VIDEO_AGENT", "BANK_USER"],
    "customer": ["END_CUSTOMER"],
}

ROLE_PERMISSIONS = {
    "ADMIN": {
        "can_manage_tenants": True,
        "can_manage_users": True,
        "can_manage_settings": True,
        "can_manage_policies": True,
        "can_view_all_tenants": True,
        "can_manage_cases": True,
        "can_approve_cases": True,
        "can_run_screening": True,
        "can_manage_waivers": True,
        "can_manage_edr": True,
        "can_manage_qa": True,
        "can_video_ident": True,
        "can_view_mi": True,
        "can_view_audit": True,
        "can_export": True,
        "can_manage_jobs": True,
        "can_manage_prompts": True,
    },
    "CASE_MANAGER": {
        "can_manage_tenants": False,
        "can_manage_users": False,
        "can_manage_settings": False,
        "can_manage_policies": False,
        "can_view_all_tenants": False,
        "can_manage_cases": True,
        "can_approve_cases": True,
        "can_run_screening": True,
        "can_manage_waivers": True,
        "can_manage_edr": True,
        "can_manage_qa": True,
        "can_video_ident": False,
        "can_view_mi": True,
        "can_view_audit": True,
        "can_export": True,
        "can_manage_jobs": False,
        "can_manage_prompts": False,
    },
    "VIDEO_AGENT": {
        "can_manage_tenants": False,
        "can_manage_users": False,
        "can_manage_settings": False,
        "can_manage_policies": False,
        "can_view_all_tenants": False,
        "can_manage_cases": False,
        "can_approve_cases": False,
        "can_run_screening": False,
        "can_manage_waivers": False,
        "can_manage_edr": False,
        "can_manage_qa": False,
        "can_video_ident": True,
        "can_view_mi": False,
        "can_view_audit": False,
        "can_export": False,
        "can_manage_jobs": False,
        "can_manage_prompts": False,
    },
    "BANK_USER": {
        "can_manage_tenants": False,
        "can_manage_users": False,
        "can_manage_settings": False,
        "can_manage_policies": False,
        "can_view_all_tenants": False,
        "can_manage_cases": True,
        "can_approve_cases": False,
        "can_run_screening": False,
        "can_manage_waivers": False,
        "can_manage_edr": False,
        "can_manage_qa": False,
        "can_video_ident": False,
        "can_view_mi": True,
        "can_view_audit": True,
        "can_export": True,
        "can_manage_jobs": False,
        "can_manage_prompts": False,
    },
}


async def get_current_user(request: Request):
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth.split(" ")[1]
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_roles(*allowed_roles):
    async def checker(request: Request):
        user = await get_current_user(request)
        user_global_role = user.get("global_role")
        user_tenant_roles = user.get("tenant_roles", [])
        all_roles = set()
        if user_global_role:
            all_roles.add(user_global_role)
        for tr in user_tenant_roles:
            all_roles.add(tr.get("role"))
        if not all_roles.intersection(set(allowed_roles)):
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user
    return checker


def require_permission(permission: str):
    async def checker(request: Request):
        user = await get_current_user(request)
        role = user.get("global_role")
        role_perms = ROLE_PERMISSIONS.get(role, {})
        if not role_perms.get(permission, False):
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")
        return user
    return checker


def require_tenant_access(tenant_id: str, user: dict):
    role = user.get("global_role")

    # ADMIN: Zugriff auf alle Tenants
    if role == "ADMIN":
        return True

    # CASE_MANAGER: Zugriff auf zugewiesene Tenants
    if role == "CASE_MANAGER":
        tenant_roles = user.get("tenant_roles", [])
        for tr in tenant_roles:
            if tr.get("tenant_id") == tenant_id:
                return True
        raise HTTPException(status_code=403, detail="No access to this tenant")

    # VIDEO_AGENT + BANK_USER: Nur zugewiesene Tenants
    tenant_roles = user.get("tenant_roles", [])
    for tr in tenant_roles:
        if tr.get("tenant_id") == tenant_id:
            return True
    raise HTTPException(status_code=403, detail="No access to this tenant")


def get_user_tenant_ids(user: dict) -> list:
    if user.get("global_role") == "ADMIN":
        return []
    return [tr["tenant_id"] for tr in user.get("tenant_roles", []) if tr.get("tenant_id")]
