from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / '.env')

JWT_SECRET = os.environ.get('JWT_SECRET')
if not JWT_SECRET:
    # Fail fast on misconfiguration — JWT_SECRET MUST be set; otherwise
    # jwt.encode / decode silently degrades and tokens become unverifiable.
    raise RuntimeError(
        "JWT_SECRET environment variable is not set. "
        "Refusing to start without a signing secret."
    )
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
        "can_manage_intake": True,
        "can_manage_integrations": True,
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
        "can_manage_intake": True,
        "can_manage_integrations": False,
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
        "can_manage_intake": False,
        "can_manage_integrations": False,
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
        "can_manage_intake": False,
        "can_manage_integrations": False,
    },
    "END_CUSTOMER": {
        # END_CUSTOMER has no staff-side permissions. Customer-portal access
        # is mediated by ownership checks on case_id/user_id, not permission
        # flags.
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
        "can_video_ident": False,
        "can_view_mi": False,
        "can_view_audit": False,
        "can_export": False,
        "can_manage_jobs": False,
        "can_manage_prompts": False,
        "can_manage_intake": False,
        "can_manage_integrations": False,
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
        if not has_permission(user, permission):
            raise HTTPException(status_code=403, detail=f"Missing permission: {permission}")
        return user
    return checker


def has_permission(user: dict, permission: str) -> bool:
    role = user.get("global_role")
    role_perms = ROLE_PERMISSIONS.get(role, {})
    return bool(role_perms.get(permission, False))


def require_tenant_access(tenant_id: str, user: dict):
    """Raise 403 if `user` is not allowed to act on `tenant_id`.

    ADMIN can access every tenant. Everyone else must have an explicit
    role record for that tenant_id in their JWT's `tenant_roles` claim.
    """
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required")

    role = user.get("global_role")
    if role == "ADMIN":
        return True

    tenant_roles = user.get("tenant_roles", []) or []
    for tr in tenant_roles:
        if tr.get("tenant_id") == tenant_id:
            return True

    raise HTTPException(status_code=403, detail="No access to this tenant")


def get_user_tenant_ids(user: dict) -> list:
    if user.get("global_role") == "ADMIN":
        return []
    return [tr["tenant_id"] for tr in user.get("tenant_roles", []) if tr.get("tenant_id")]


def scope_tenant_query(user: dict, query: dict, tenant_id: str | None = None) -> dict:
    """Apply tenant scoping to a MongoDB query.

    Rules:
    - ADMIN: if `tenant_id` is given, scope to it; otherwise unscoped.
    - non-ADMIN: a supplied `tenant_id` must match one of the user's
      tenant_roles, otherwise 403. If none is supplied, the query is
      restricted to the union of the user's tenants.
    """
    if user.get("global_role") == "ADMIN":
        if tenant_id:
            query["tenant_id"] = tenant_id
        return query

    user_tenants = get_user_tenant_ids(user)
    if tenant_id:
        if tenant_id not in user_tenants:
            raise HTTPException(status_code=403, detail="No access to this tenant")
        query["tenant_id"] = tenant_id
    else:
        if not user_tenants:
            # User has no tenant roles at all — force empty result rather
            # than letting the query run unscoped.
            query["tenant_id"] = {"$in": []}
        else:
            query["tenant_id"] = {"$in": user_tenants}
    return query


def require_case_access(user: dict, case: dict):
    """Verify that `user` may operate on `case` (must share a tenant).

    Use this after loading a case-by-id, before mutating it.
    """
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    require_tenant_access(case.get("tenant_id", ""), user)
    return True


def require_customer_case_access(user: dict, case: dict):
    """Customer-side: END_CUSTOMER may only access cases bound in their JWT.

    The token issued by the customer portal embeds `case_id` (or the user
    has a tenant role for the case's tenant_id). Anything else is denied.
    """
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    role = user.get("global_role")
    if role == "ADMIN":
        return True

    if role == "END_CUSTOMER":
        token_case_id = user.get("case_id")
        if token_case_id and token_case_id == case.get("id"):
            return True
        # Allow if customer has a tenant-binding for that case's tenant
        # AND the case was created by/for this user (best-effort).
        tenant_id = case.get("tenant_id")
        for tr in user.get("tenant_roles", []) or []:
            if tr.get("tenant_id") == tenant_id:
                if case.get("created_by") == user.get("user_id"):
                    return True
        raise HTTPException(status_code=403, detail="Not your case")

    # Staff roles: fall back to tenant access
    require_tenant_access(case.get("tenant_id", ""), user)
    return True
