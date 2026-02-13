from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/api/customer", tags=["customer_portal"])


def get_db(request: Request):
    return request.app.state.db


@router.get("/case")
async def get_customer_case(request: Request, case_ref: Optional[str] = None, tenant_id: Optional[str] = None):
    from middleware.auth_middleware import get_current_user
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
    
    # Get requirements and their statuses (customer-facing view)
    requirements = await db.requirement_items.find({"case_id": case["id"]}, {"_id": 0}).to_list(500)
    documents = await db.documents.find({"case_id": case["id"]}, {"_id": 0}).to_list(500)
    parties = await db.parties.find({"case_id": case["id"], "deleted": {"$ne": True}}, {"_id": 0}).to_list(100)
    
    # Get questionnaire session
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
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()
    
    case_id = body.get("case_id")
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Check if session already exists
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
    
    # Update case status
    await db.cases.update_one(
        {"id": case_id},
        {"$set": {"status": "customer_in_progress", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return session


@router.put("/questionnaire/{session_id}")
async def update_questionnaire(session_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()
    
    session = await db.questionnaire_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    updates = {}
    if "current_step" in body:
        updates["current_step"] = body["current_step"]
    if "answers_json" in body:
        # Merge answers
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
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    session = await db.questionnaire_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Mark questionnaire complete
    await db.questionnaire_sessions.update_one(
        {"id": session_id},
        {"$set": {"completed_at": datetime.now(timezone.utc).isoformat(), "current_step": "completed"}}
    )
    
    # Create parties based on answers
    answers = session.get("answers_json", {})
    case_id = session["case_id"]
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    
    entity_type = session.get("entity_type_determined", "legal_entity")
    
    # Create main client party if not exists
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
            "addresses_json": answers.get("address", {}),
            "identifiers_json": answers.get("identifiers", {}),
            "ownership_percent": None,
            "control_flags_json": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "deleted": False
        }
        await db.parties.insert_one({**client_party})
        await _generate_requirements(db, case, client_party)
    
    # Create UBO parties if provided
    ubos = answers.get("ubos", [])
    for ubo in ubos:
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
    
    # Check if all documents are uploaded, if so mark as customer_submitted
    reqs = await db.requirement_items.find({"case_id": case_id}, {"_id": 0}).to_list(500)
    doc_reqs = [r for r in reqs if r["requirement_category"] not in ["sanctions", "pep", "adverse_media", "video_ident"]]
    all_submitted = all(r["status"] != "missing" for r in doc_reqs) if doc_reqs else False
    
    if all_submitted:
        await db.cases.update_one({"id": case_id}, {"$set": {"status": "customer_submitted", "updated_at": datetime.now(timezone.utc).isoformat()}})
    
    return {"message": "Questionnaire completed", "parties_created": len(ubos) + 1}


@router.post("/submit")
async def submit_case(request: Request):
    """Customer submits the case after completing all requirements."""
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()
    
    case_id = body.get("case_id")
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
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
    """Get invite details by token (no auth required)."""
    db = get_db(request)
    invite = await db.customer_invites.find_one({"token": token}, {"_id": 0})
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid invite link")

    case = await db.cases.find_one({"id": invite["case_id"]}, {"_id": 0})
    tenant = await db.tenants.find_one({"id": invite["tenant_id"]}, {"_id": 0})

    return {
        "invite": invite,
        "case_ref": case.get("case_ref") if case else None,
        "tenant_name": tenant.get("name") if tenant else None,
        "tenant_branding": tenant.get("branding_json") if tenant else None
    }


@router.post("/invite/{token}/accept")
async def accept_invite(token: str, request: Request):
    """Accept invite and get auth token. Customer enters email + receives OTP."""
    db = get_db(request)
    body = await request.json()
    email = body.get("email")

    invite = await db.customer_invites.find_one({"token": token}, {"_id": 0})
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid invite")

    # Verify email matches
    if invite["email"].lower() != email.lower():
        raise HTTPException(status_code=400, detail="Email does not match the invitation")

    # Generate OTP
    otp_code = "123456"  # MOCK
    await db.otp_codes.insert_one({
        "user_id": invite["customer_user_id"],
        "email": email,
        "code": otp_code,
        "tenant_id": invite["tenant_id"],
        "case_ref": invite.get("case_ref"),
        "expires_at": (datetime.now(timezone.utc) + __import__('datetime').timedelta(minutes=10)).isoformat(),
        "used": False
    })

    return {"message": "OTP sent (demo: 123456)", "demo_otp": "123456"}


@router.post("/invite/{token}/verify")
async def verify_invite_otp(token: str, request: Request):
    """Verify OTP and return auth token for invited customer."""
    db = get_db(request)
    body = await request.json()
    code = body.get("code")

    invite = await db.customer_invites.find_one({"token": token}, {"_id": 0})
    if not invite:
        raise HTTPException(status_code=404, detail="Invalid invite")

    # Verify OTP
    otp = await db.otp_codes.find_one(
        {"email": invite["email"], "code": code, "used": False},
        {"_id": 0}
    )
    if not otp:
        raise HTTPException(status_code=401, detail="Invalid OTP")

    await db.otp_codes.update_one({"email": invite["email"], "code": code}, {"$set": {"used": True}})

    # Mark invite accepted
    await db.customer_invites.update_one(
        {"token": token},
        {"$set": {"status": "accepted", "accepted_at": datetime.now(timezone.utc).isoformat()}}
    )

    # Get user
    user = await db.users.find_one({"id": invite["customer_user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Create JWT token
    import jwt as pyjwt
    import os
    JWT_SECRET = os.environ.get('JWT_SECRET')
    from datetime import timedelta
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
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)

    case = await db.cases.find_one({"id": case_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

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
