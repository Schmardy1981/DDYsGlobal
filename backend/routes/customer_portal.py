from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import os
import secrets
import uuid
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/api/customer", tags=["customer_portal"])


# How long an invite token is valid for, before it's considered expired.
INVITE_TTL_DAYS = 14


def get_db(request: Request):
    return request.app.state.db


def _parse_iso_utc(value: str | None) -> Optional[datetime]:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


@router.get("/case")
async def get_customer_case(request: Request, case_ref: Optional[str] = None, tenant_id: Optional[str] = None):
    """Customer view of a case, identified by case_ref + tenant_id.

    Ownership is enforced: the END_CUSTOMER's JWT must reference the case
    being requested (either by case_id or by being created_by==user.id and
    having a tenant binding). Without this check, case_ref enumeration was
    the entire attack surface.
    """
    from middleware.auth_middleware import (
        get_current_user, require_customer_case_access, require_tenant_access
    )
    user = await get_current_user(request)
    db = get_db(request)

    query = {"deleted": {"$ne": True}}
    if case_ref:
        query["case_ref"] = case_ref
    if tenant_id:
        query["tenant_id"] = tenant_id

    case = await db.cases.find_one(query, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    role = user.get("global_role")
    if role == "END_CUSTOMER":
        require_customer_case_access(user, case)
    else:
        require_tenant_access(case["tenant_id"], user)

    requirements = await db.requirement_items.find({"case_id": case["id"]}, {"_id": 0}).to_list(500)
    documents = await db.documents.find({"case_id": case["id"]}, {"_id": 0}).to_list(500)
    parties = await db.parties.find({"case_id": case["id"], "deleted": {"$ne": True}}, {"_id": 0}).to_list(100)

    session = await db.questionnaire_sessions.find_one({"case_id": case["id"]}, {"_id": 0})

    return {
        "case": case,
        "requirements": requirements,
        "documents": [{"id": d["id"], "doc_type": d["doc_type"], "status": d["status"], "original_filename": d.get("original_filename"), "requirement_item_id": d.get("requirement_item_id")} for d in documents],
        "parties": parties,
        "questionnaire": session
    }


@router.post("/questionnaire/start")
async def start_questionnaire(request: Request):
    from middleware.auth_middleware import get_current_user, require_customer_case_access
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()

    case_id = body.get("case_id")
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    require_customer_case_access(user, case)

    existing = await db.questionnaire_sessions.find_one({"case_id": case_id}, {"_id": 0})
    if existing:
        return existing

    session = {
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "case_id": case_id,
        "end_customer_user_id": user.get("user_id"),
        "token": str(uuid.uuid4()),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "current_step": "entity_type",
        "answers_json": {},
        "entity_type_determined": None,
        "derived_requirements_json": [],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.questionnaire_sessions.insert_one({**session})

    await db.cases.update_one(
        {"id": case_id},
        {"$set": {"status": "customer_in_progress", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    return session


@router.put("/questionnaire/{session_id}")
async def update_questionnaire(session_id: str, request: Request):
    from middleware.auth_middleware import get_current_user, require_customer_case_access
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()

    session = await db.questionnaire_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify the caller actually owns the underlying case.
    case = await db.cases.find_one({"id": session["case_id"]}, {"_id": 0})
    require_customer_case_access(user, case)

    updates = {}
    if "current_step" in body:
        updates["current_step"] = body["current_step"]
    if "answers_json" in body:
        current_answers = session.get("answers_json", {})
        current_answers.update(body["answers_json"])
        updates["answers_json"] = current_answers
    if "entity_type_determined" in body:
        updates["entity_type_determined"] = body["entity_type_determined"]

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.questionnaire_sessions.update_one({"id": session_id}, {"$set": updates})

    return await db.questionnaire_sessions.find_one({"id": session_id}, {"_id": 0})


@router.post("/questionnaire/{session_id}/complete")
async def complete_questionnaire(session_id: str, request: Request):
    """Finalize the customer questionnaire and materialize parties.

    Idempotent: re-calling this endpoint does not duplicate UBO parties,
    fixing the previous bug where two completion calls created two sets
    of UBOs.
    """
    from middleware.auth_middleware import get_current_user, require_customer_case_access
    user = await get_current_user(request)
    db = get_db(request)

    session = await db.questionnaire_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    case_id = session["case_id"]
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    require_customer_case_access(user, case)

    already_completed = session.get("completed_at")

    await db.questionnaire_sessions.update_one(
        {"id": session_id},
        {"$set": {"completed_at": datetime.now(timezone.utc).isoformat(), "current_step": "completed"}}
    )

    if already_completed:
        # Idempotent re-call: do not re-create parties / requirements.
        return {"message": "Questionnaire already completed", "parties_created": 0, "idempotent": True}

    answers = session.get("answers_json", {})
    entity_type = session.get("entity_type_determined", "legal_entity")

    # Frontend posts address fields as flat `address_*`; preserve them as
    # a dict so addresses_json is no longer overwritten with an empty {}.
    address = answers.get("address")
    if not isinstance(address, dict):
        address = {
            "street": answers.get("address_street", ""),
            "city": answers.get("address_city", ""),
            "country": answers.get("address_country", ""),
        }

    existing_parties = await db.parties.find({"case_id": case_id, "role_in_case": "client"}, {"_id": 0}).to_list(1)
    if not existing_parties:
        from routes.cases import _generate_requirements
        client_party = {
            "id": str(uuid.uuid4()),
            "tenant_id": case["tenant_id"],
            "case_id": case_id,
            "party_type": entity_type,
            "role_in_case": "client",
            "first_name": answers.get("first_name", ""),
            "last_name": answers.get("last_name", ""),
            "legal_name": answers.get("legal_name", answers.get("company_name", "")),
            "dob": answers.get("dob"),
            "nationality": answers.get("nationality", ""),
            "addresses_json": address,
            "identifiers_json": answers.get("identifiers", {}),
            "ownership_percent": None,
            "control_flags_json": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "deleted": False
        }
        await db.parties.insert_one({**client_party})
        await _generate_requirements(db, case, client_party)

    ubos = answers.get("ubos", [])
    created_ubos = 0
    for ubo in ubos:
        # Dedup UBO inserts by (case_id, first_name, last_name, dob).
        existing_ubo = await db.parties.find_one({
            "case_id": case_id,
            "role_in_case": "ubo",
            "first_name": ubo.get("first_name", ""),
            "last_name": ubo.get("last_name", ""),
            "dob": ubo.get("dob"),
        }, {"_id": 0, "id": 1})
        if existing_ubo:
            continue
        ubo_party = {
            "id": str(uuid.uuid4()),
            "tenant_id": case["tenant_id"],
            "case_id": case_id,
            "party_type": "natural_person",
            "role_in_case": "ubo",
            "first_name": ubo.get("first_name", ""),
            "last_name": ubo.get("last_name", ""),
            "legal_name": "",
            "dob": ubo.get("dob"),
            "nationality": ubo.get("nationality", ""),
            "addresses_json": ubo.get("address", {}),
            "identifiers_json": {},
            "ownership_percent": ubo.get("ownership_percent"),
            "control_flags_json": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "deleted": False
        }
        await db.parties.insert_one({**ubo_party})
        from routes.cases import _generate_requirements
        await _generate_requirements(db, case, ubo_party)
        created_ubos += 1

    reqs = await db.requirement_items.find({"case_id": case_id}, {"_id": 0}).to_list(500)
    doc_reqs = [r for r in reqs if r["requirement_category"] not in ["sanctions", "pep", "adverse_media", "video_ident"]]
    all_submitted = all(r["status"] != "missing" for r in doc_reqs) if doc_reqs else False

    if all_submitted:
        await db.cases.update_one({"id": case_id}, {"$set": {"status": "customer_submitted", "updated_at": datetime.now(timezone.utc).isoformat()}})

    return {"message": "Questionnaire completed", "parties_created": created_ubos + (1 if not existing_parties else 0)}


@router.post("/submit")
async def submit_case(request: Request):
    """Customer submits the case after completing all requirements."""
    from middleware.auth_middleware import get_current_user, require_customer_case_access
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()

    case_id = body.get("case_id")
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    require_customer_case_access(user, case)

    await db.cases.update_one(
        {"id": case_id},
        {"$set": {"status": "customer_submitted", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    return {"message": "Case submitted successfully"}


@router.get("/notifications")
async def get_customer_notifications(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)

    notifs = await db.notifications.find(
        {"user_id": user["user_id"], "read": False},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return notifs


@router.get("/invite/{token}")
async def get_invite(token: str, request: Request):
    """Get *limited* invite metadata by token (no auth required).

    Previously this leaked the full invite document — including
    customer_user_id, case_id, tenant_id — which made token enumeration
    materially useful. We now return only the case_ref, tenant name and
    branding, which is the minimum the landing page needs.
    """
    db = get_db(request)
    invite = await db.customer_invites.find_one({"token": token}, {"_id": 0})
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid invite link")

    # Expiry check
    expires_at = _parse_iso_utc(invite.get("expires_at"))
    if expires_at and datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=410, detail="Invite has expired")

    if invite.get("status") in ("accepted", "revoked"):
        # Already consumed or canceled; treat as expired to avoid leaking
        # exact lifecycle state.
        raise HTTPException(status_code=410, detail="Invite is no longer valid")

    case = await db.cases.find_one({"id": invite["case_id"]}, {"_id": 0, "case_ref": 1})
    tenant = await db.tenants.find_one({"id": invite["tenant_id"]}, {"_id": 0, "name": 1, "branding_json": 1})

    return {
        "case_ref": case.get("case_ref") if case else None,
        "tenant_name": tenant.get("name") if tenant else None,
        "tenant_branding": tenant.get("branding_json") if tenant else None,
    }


@router.post("/invite/{token}/accept")
async def accept_invite(token: str, request: Request):
    """Accept invite, send OTP to the invitee's email.

    Hardened:
    - Expiry on the invite is enforced.
    - The invite must still be `sent` (not already accepted / revoked).
    - The OTP value is generated cryptographically when not using the
      mock email provider — no hardcoded `123456` outside of mock.
    """
    db = get_db(request)
    body = await request.json()
    email = (body.get("email") or "").strip().lower()

    invite = await db.customer_invites.find_one({"token": token}, {"_id": 0})
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid invite")

    if invite.get("status") not in (None, "sent", "opened"):
        raise HTTPException(status_code=410, detail="Invite is no longer valid")

    expires_at = _parse_iso_utc(invite.get("expires_at"))
    if expires_at and datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=410, detail="Invite has expired")

    if (invite.get("email") or "").lower() != email:
        raise HTTPException(status_code=400, detail="Email does not match the invitation")

    # Generate OTP — mock only emits the fixed code; real providers get a
    # 6-digit secret value that's never echoed in the response.
    from services.providers import get_email_provider
    from services.providers.base import EmailMessage

    email_provider = await get_email_provider(db)
    if email_provider.name == "mock":
        otp_code = "123456"
    else:
        otp_code = f"{secrets.randbelow(1_000_000):06d}"

    await db.otp_codes.insert_one({
        "user_id": invite["customer_user_id"],
        "email": email,
        "code": otp_code,
        "tenant_id": invite["tenant_id"],
        "case_ref": invite.get("case_ref"),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat(),
        "used": False,
        "attempts": 0,
    })

    send_result = await email_provider.send(EmailMessage(
        to=email,
        subject=f"Your DDYs verification code",
        body_text=f"Your code is: {otp_code}\nIt expires in 10 minutes.",
        metadata={"tenant_id": invite["tenant_id"], "kind": "invite_otp"},
    ))

    payload = {
        "message": "OTP sent",
        "provider": email_provider.name,
        "delivered": send_result.success,
    }
    if email_provider.name == "mock":
        payload["demo_otp"] = otp_code
    return payload


@router.post("/invite/{token}/verify")
async def verify_invite_otp(token: str, request: Request):
    """Verify OTP, mark invite consumed, return a session JWT.

    Hardened:
    - The OTP code's `expires_at` is enforced.
    - The invite must be unconsumed (`sent`/`opened`); replays are rejected.
    - Single-use: once we issue a token we flip the invite to `accepted`.
    """
    db = get_db(request)
    body = await request.json()
    code = body.get("code")

    invite = await db.customer_invites.find_one({"token": token}, {"_id": 0})
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid invite")
    if invite.get("status") not in (None, "sent", "opened"):
        raise HTTPException(status_code=410, detail="Invite already used or revoked")

    expires_at = _parse_iso_utc(invite.get("expires_at"))
    if expires_at and datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=410, detail="Invite has expired")

    otp = await db.otp_codes.find_one(
        {"email": invite["email"], "code": code, "used": False, "tenant_id": invite["tenant_id"]},
        {"_id": 0}
    )
    if not otp:
        raise HTTPException(status_code=401, detail="Invalid OTP")

    otp_expires = _parse_iso_utc(otp.get("expires_at"))
    if otp_expires and datetime.now(timezone.utc) > otp_expires:
        raise HTTPException(status_code=401, detail="OTP has expired")

    await db.otp_codes.update_one({"email": invite["email"], "code": code}, {"$set": {"used": True}})

    # Mark invite consumed atomically.
    accept_result = await db.customer_invites.update_one(
        {"token": token, "status": {"$in": [None, "sent", "opened"]}},
        {"$set": {"status": "accepted", "accepted_at": datetime.now(timezone.utc).isoformat()}}
    )
    if accept_result.modified_count == 0:
        raise HTTPException(status_code=410, detail="Invite already accepted")

    user = await db.users.find_one({"id": invite["customer_user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    import jwt as pyjwt
    JWT_SECRET = os.environ.get('JWT_SECRET')
    token_payload = {
        "user_id": user["id"],
        "email": user["email"],
        "name": user.get("name", ""),
        "global_role": "END_CUSTOMER",
        "tenant_roles": [{"tenant_id": invite["tenant_id"], "role": "END_CUSTOMER"}],
        "case_id": invite["case_id"],
        "mfa_verified": True,
        "exp": datetime.now(timezone.utc) + timedelta(hours=24)
    }
    auth_token = pyjwt.encode(token_payload, JWT_SECRET, algorithm="HS256")

    safe_user = {k: v for k, v in user.items() if k not in ["password_hash", "mfa_secret"]}
    safe_user["tenant_roles"] = [{"tenant_id": invite["tenant_id"], "role": "END_CUSTOMER"}]
    safe_user["case_id"] = invite["case_id"]

    return {
        "token": auth_token,
        "user": safe_user,
        "case_id": invite["case_id"],
        "tenant_id": invite["tenant_id"]
    }


@router.get("/case-by-id/{case_id}")
async def get_case_by_id(case_id: str, request: Request):
    """Get case data directly by case_id for invited customers."""
    from middleware.auth_middleware import (
        get_current_user, require_customer_case_access, require_tenant_access
    )
    user = await get_current_user(request)
    db = get_db(request)

    case = await db.cases.find_one({"id": case_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    role = user.get("global_role")
    if role == "END_CUSTOMER":
        require_customer_case_access(user, case)
    else:
        require_tenant_access(case["tenant_id"], user)

    requirements = await db.requirement_items.find({"case_id": case_id}, {"_id": 0}).to_list(500)
    documents = await db.documents.find({"case_id": case_id}, {"_id": 0}).to_list(500)
    parties = await db.parties.find({"case_id": case_id, "deleted": {"$ne": True}}, {"_id": 0}).to_list(100)
    session = await db.questionnaire_sessions.find_one({"case_id": case_id}, {"_id": 0})
    reminders = await db.email_reminders.find({"case_id": case_id}, {"_id": 0}).sort("created_at", -1).to_list(50)

    return {
        "case": case,
        "requirements": requirements,
        "documents": [{
            "id": d["id"], "doc_type": d["doc_type"], "status": d["status"],
            "original_filename": d.get("original_filename"),
            "requirement_item_id": d.get("requirement_item_id"),
            "ai_result_id": d.get("ai_result_id"),
            "created_at": d.get("created_at")
        } for d in documents],
        "parties": parties,
        "questionnaire": session,
        "reminders": reminders
    }
