from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional, List
import uuid
import jwt
import bcrypt
import pyotp
import os
import secrets
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / '.env')

JWT_SECRET = os.environ.get('JWT_SECRET')
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET is required")
MFA_ISSUER = os.environ.get('MFA_ISSUER', 'DDYs-Compliance')

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str

class LoginResponse(BaseModel):
    requires_mfa: bool = False
    mfa_token: Optional[str] = None
    token: Optional[str] = None
    user: Optional[dict] = None

class MFAVerifyRequest(BaseModel):
    mfa_token: str
    code: str

class MFASetupResponse(BaseModel):
    secret: str
    otpauth_url: str

class RegisterRequest(BaseModel):
    email: str
    password: str
    name: str


def get_db(request: Request):
    return request.app.state.db


def create_token(user_data: dict, tenant_roles: list) -> str:
    payload = {
        "user_id": user_data["id"],
        "email": user_data["email"],
        "name": user_data["name"],
        "global_role": user_data.get("global_role"),
        "tenant_roles": tenant_roles,
        "mfa_verified": True,
        "exp": datetime.now(timezone.utc) + timedelta(hours=12)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def create_mfa_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "mfa_pending": True,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=10)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


@router.post("/login")
async def login(req: LoginRequest, request: Request):
    db = get_db(request)
    user = await db.users.find_one({"email": req.email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if user.get("status") != "active":
        raise HTTPException(status_code=401, detail="Account is inactive")
    stored_pw = user.get("password_hash", "")
    if not stored_pw or not bcrypt.checkpw(req.password.encode(), stored_pw.encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check if MFA is enabled
    if user.get("mfa_enabled") and user.get("mfa_secret"):
        mfa_token = create_mfa_token(user["id"])
        return {"requires_mfa": True, "mfa_token": mfa_token, "token": None, "user": None}

    # No MFA - return token directly
    tenant_roles = await db.user_tenant_roles.find({"user_id": user["id"], "active": True}, {"_id": 0}).to_list(100)
    token = create_token(user, tenant_roles)
    safe_user = {k: v for k, v in user.items() if k != "password_hash" and k != "mfa_secret"}
    safe_user["tenant_roles"] = tenant_roles
    return {"requires_mfa": False, "mfa_token": None, "token": token, "user": safe_user}


@router.post("/mfa/verify")
async def verify_mfa(req: MFAVerifyRequest, request: Request):
    db = get_db(request)
    try:
        payload = jwt.decode(req.mfa_token, JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid MFA token")

    if not payload.get("mfa_pending"):
        raise HTTPException(status_code=400, detail="Not an MFA token")

    user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    totp = pyotp.TOTP(user["mfa_secret"])
    if not totp.verify(req.code, valid_window=1):
        raise HTTPException(status_code=401, detail="Invalid MFA code")

    tenant_roles = await db.user_tenant_roles.find({"user_id": user["id"], "active": True}, {"_id": 0}).to_list(100)
    token = create_token(user, tenant_roles)
    safe_user = {k: v for k, v in user.items() if k != "password_hash" and k != "mfa_secret"}
    safe_user["tenant_roles"] = tenant_roles
    return {"token": token, "user": safe_user}


@router.post("/mfa/setup")
async def setup_mfa(request: Request):
    """Initialize TOTP MFA for the *currently authenticated* user.

    Re-issuing the secret resets MFA for the caller's own account only.
    A stolen session can no longer overwrite a different user's MFA secret —
    the target user_id is taken from the verified JWT, never from the body.
    Additionally, re-enabling MFA when it's already active requires the
    caller to verify their current TOTP code first.
    """
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)

    user_doc = await db.users.find_one({"id": user["user_id"]}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    # If MFA is already enabled, require the caller to prove control of
    # the existing secret before we let them replace it. Body must include
    # `current_code`.
    if user_doc.get("mfa_enabled") and user_doc.get("mfa_secret"):
        try:
            body = await request.json()
        except Exception:
            body = {}
        current_code = body.get("current_code") if isinstance(body, dict) else None
        if not current_code:
            raise HTTPException(
                status_code=400,
                detail="MFA already enabled; provide current_code to reset"
            )
        totp = pyotp.TOTP(user_doc["mfa_secret"])
        if not totp.verify(current_code, valid_window=1):
            raise HTTPException(status_code=401, detail="Invalid current MFA code")

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    otpauth_url = totp.provisioning_uri(name=user["email"], issuer_name=MFA_ISSUER)

    await db.users.update_one(
        {"id": user["user_id"]},
        {"$set": {"mfa_secret": secret, "mfa_enabled": True, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    return {"secret": secret, "otpauth_url": otpauth_url}


@router.get("/me")
async def get_me(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)

    user_doc = await db.users.find_one({"id": user["user_id"]}, {"_id": 0, "password_hash": 0, "mfa_secret": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    tenant_roles = await db.user_tenant_roles.find({"user_id": user["user_id"], "active": True}, {"_id": 0}).to_list(100)
    user_doc["tenant_roles"] = tenant_roles
    return user_doc


@router.post("/customer/otp-request")
async def customer_otp_request(request: Request):
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    tenant_id = body.get("tenant_id")
    case_ref = body.get("case_ref")
    db = get_db(request)

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Valid email required")
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id required")

    # Verify the tenant_id is a real, active tenant — never trust the body
    # blindly. Without this, anyone can stamp arbitrary tenants into a JWT.
    tenant = await db.tenants.find_one(
        {"id": tenant_id, "status": "active", "deleted": {"$ne": True}},
        {"_id": 0, "id": 1}
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # If a case_ref is provided, require that it exists in the given
    # tenant. This is what scopes the OTP to a real relationship.
    if case_ref:
        case_exists = await db.cases.find_one(
            {"case_ref": case_ref, "tenant_id": tenant_id, "deleted": {"$ne": True}},
            {"_id": 0, "id": 1}
        )
        if not case_exists:
            raise HTTPException(status_code=404, detail="Case not found")

    # Find the END_CUSTOMER user. We no longer auto-provision arbitrary
    # users from an unauthenticated request — the user must already exist
    # (created via the invite flow or admin import).
    user = await db.users.find_one(
        {"email": email, "global_role": "END_CUSTOMER", "status": "active"},
        {"_id": 0}
    )
    if not user:
        # Return a generic message to avoid email-enumeration, but do NOT
        # create the account. The customer must use the invite path.
        return {"message": "If an account exists, an OTP has been sent.", "provider": "n/a", "delivered": False}

    # Generate OTP. Mock provider returns the fixed code so existing demo
    # flows keep working; real providers (e.g. SendGrid) get a cryptographic
    # 6-digit value and never expose it in the response.
    from services.providers import get_email_provider
    from services.providers.base import EmailMessage

    email_provider = await get_email_provider(db)
    if email_provider.name == "mock":
        otp_code = "123456"
    else:
        otp_code = f"{secrets.randbelow(1_000_000):06d}"

    await db.otp_codes.insert_one({
        "user_id": user["id"],
        "email": email,
        "code": otp_code,
        "tenant_id": tenant_id,
        "case_ref": case_ref,
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        "used": False,
        "attempts": 0
    })

    send_result = await email_provider.send(EmailMessage(
        to=email,
        subject="Your DDYs verification code",
        body_text=(
            f"Your DDYs verification code is: {otp_code}\n\n"
            f"It expires in 10 minutes."
        ),
        metadata={"tenant_id": tenant_id or "", "case_ref": case_ref or "", "kind": "otp"},
    ))

    payload = {
        "message": "OTP sent to email",
        "provider": email_provider.name,
        "delivered": send_result.success,
    }
    if email_provider.name == "mock":
        payload["demo_otp"] = otp_code
    return payload


@router.post("/customer/otp-verify")
async def customer_otp_verify(request: Request):
    body = await request.json()
    email = (body.get("email") or "").strip().lower()
    code = body.get("code")
    tenant_id = body.get("tenant_id")
    db = get_db(request)

    if not email or not code or not tenant_id:
        raise HTTPException(status_code=400, detail="email, code and tenant_id are required")

    otp = await db.otp_codes.find_one(
        {"email": email, "code": code, "used": False, "tenant_id": tenant_id},
        {"_id": 0}
    )
    if not otp:
        raise HTTPException(status_code=401, detail="Invalid OTP")

    # Enforce expiry. The 10-minute window was being written but never
    # checked — verify it here so an old code can't be used forever.
    expires_at_raw = otp.get("expires_at")
    if expires_at_raw:
        try:
            expires_at = datetime.fromisoformat(expires_at_raw)
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > expires_at:
                raise HTTPException(status_code=401, detail="OTP has expired")
        except ValueError:
            raise HTTPException(status_code=401, detail="OTP has invalid expiry")

    await db.otp_codes.update_one({"email": email, "code": code}, {"$set": {"used": True}})

    user = await db.users.find_one({"email": email, "global_role": "END_CUSTOMER"}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Verify the user has a relationship with that tenant. We bind the
    # JWT's tenant_roles to that relationship rather than trusting the body.
    # Acceptable proofs of relationship:
    #   1. The user has a case in that tenant they own (created_by==user.id), or
    #   2. The user has an accepted invite for that tenant, or
    #   3. The user already has an active user_tenant_role for it.
    has_relationship = False
    existing_role = await db.user_tenant_roles.find_one(
        {"user_id": user["id"], "tenant_id": tenant_id, "active": True},
        {"_id": 0, "id": 1}
    )
    if existing_role:
        has_relationship = True
    if not has_relationship:
        owned = await db.cases.find_one(
            {"tenant_id": tenant_id, "created_by": user["id"], "deleted": {"$ne": True}},
            {"_id": 0, "id": 1}
        )
        if owned:
            has_relationship = True
    if not has_relationship:
        invite = await db.customer_invites.find_one(
            {"tenant_id": tenant_id, "customer_user_id": user["id"]},
            {"_id": 0, "id": 1}
        )
        if invite:
            has_relationship = True

    if not has_relationship:
        raise HTTPException(status_code=403, detail="No relationship with this tenant")

    # Create token for end customer
    tenant_roles = [{"tenant_id": tenant_id, "role": "END_CUSTOMER"}]
    token = create_token(user, tenant_roles)
    safe_user = {k: v for k, v in user.items() if k != "password_hash" and k != "mfa_secret"}
    safe_user["tenant_roles"] = tenant_roles
    return {"token": token, "user": safe_user}
