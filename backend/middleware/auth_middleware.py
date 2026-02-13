from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import jwt
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / '.env')

JWT_SECRET = os.environ.get('JWT_SECRET')
security = HTTPBearer(auto_error=False)

ROLE_HIERARCHY = {
    "GLOBAL_SUPER_ADMIN": 100,
    "DDYS_COMPLIANCE_MANAGER": 90,
    "DDYS_QA_SECOND_LINE": 80,
    "DDYS_QA_FIRST_LINE": 70,
    "DDYS_RCM_CHECKER": 60,
    "DDYS_RCM_MAKER": 50,
    "TENANT_MLRO": 45,
    "TENANT_COMPLIANCE_USER": 40,
    "TENANT_ADMIN": 35,
    "TENANT_BUSINESS_USER": 30,
    "VIDEO_IDENT_AGENT": 20,
    "END_CUSTOMER": 10,
}

PORTAL_ACCESS = {
    "admin": ["GLOBAL_SUPER_ADMIN", "DDYS_COMPLIANCE_MANAGER", "DDYS_QA_SECOND_LINE", "DDYS_QA_FIRST_LINE", "DDYS_RCM_CHECKER", "DDYS_RCM_MAKER"],
    "tenant": ["GLOBAL_SUPER_ADMIN", "DDYS_COMPLIANCE_MANAGER", "DDYS_QA_SECOND_LINE", "DDYS_QA_FIRST_LINE", "DDYS_RCM_CHECKER", "DDYS_RCM_MAKER", "TENANT_ADMIN", "TENANT_BUSINESS_USER", "TENANT_COMPLIANCE_USER", "TENANT_MLRO", "VIDEO_IDENT_AGENT"],
    "customer": ["END_CUSTOMER"],
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


def require_tenant_access(tenant_id: str, user: dict):
    if user.get("global_role") == "GLOBAL_SUPER_ADMIN":
        return True
    if user.get("global_role") in ["DDYS_COMPLIANCE_MANAGER", "DDYS_QA_SECOND_LINE", "DDYS_QA_FIRST_LINE", "DDYS_RCM_CHECKER", "DDYS_RCM_MAKER"]:
        tenant_roles = user.get("tenant_roles", [])
        for tr in tenant_roles:
            if tr.get("tenant_id") == tenant_id:
                return True
        return True  # DDYs staff has access to assigned tenants
    tenant_roles = user.get("tenant_roles", [])
    for tr in tenant_roles:
        if tr.get("tenant_id") == tenant_id:
            return True
    raise HTTPException(status_code=403, detail="No access to this tenant")
