from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


def get_db(request: Request):
    return request.app.state.db


@router.post("/send")
async def send_reminder(request: Request):
    """Manually send a reminder for missing documents on a case."""
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()

    case_id = body.get("case_id")
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Get missing requirements
    missing_reqs = await db.requirement_items.find({
        "case_id": case_id,
        "status": {"$in": ["missing", "rejected"]},
        "requirement_category": {"$nin": ["sanctions", "pep", "adverse_media"]}
    }, {"_id": 0}).to_list(500)

    if not missing_reqs:
        return {"message": "No missing requirements to remind about", "sent": False}

    # Get customer email from parties or questionnaire
    customer_email = body.get("email")
    if not customer_email:
        session = await db.questionnaire_sessions.find_one({"case_id": case_id}, {"_id": 0})
        if session and session.get("end_customer_user_id"):
            cust_user = await db.users.find_one({"id": session["end_customer_user_id"]}, {"_id": 0})
            if cust_user:
                customer_email = cust_user.get("email")

    missing_items = [r.get("requirement_label", r.get("requirement_key")) for r in missing_reqs]

    # Create reminder record
    reminder = {
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "case_id": case_id,
        "case_ref": case.get("case_ref", ""),
        "type": "manual",
        "recipient_email": customer_email or "unknown",
        "subject": f"Action Required: Missing KYC Documents - {case.get('case_ref', '')}",
        "missing_items": missing_items,
        "missing_count": len(missing_items),
        "sent_by": user["user_id"],
        "sent_by_name": user.get("name", ""),
        "status": "sent",  # mock - would be 'sent' after email API call
        "provider": "mock",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "opened_at": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.email_reminders.insert_one({**reminder})

    # Create notification for customer
    if customer_email:
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "tenant_id": case["tenant_id"],
            "user_id": session.get("end_customer_user_id", "all") if session else "all",
            "message": f"Reminder: {len(missing_items)} missing document(s) for case {case.get('case_ref', '')}",
            "type": "document_reminder",
            "entity_id": case_id,
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "reminder.manual_sent",
        "entity_type": "email_reminder",
        "entity_id": reminder["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": None,
        "after_json": {"to": customer_email, "missing_count": len(missing_items)},
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })

    return {
        "message": f"Reminder sent for {len(missing_items)} missing items (MOCK - configure email in Settings)",
        "sent": True,
        "reminder": reminder
    }


@router.get("")
async def list_reminders(request: Request, case_id: Optional[str] = None, tenant_id: Optional[str] = None):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)

    query = {}
    if case_id:
        query["case_id"] = case_id
    if tenant_id:
        query["tenant_id"] = tenant_id

    reminders = await db.email_reminders.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return reminders


@router.post("/auto-config")
async def configure_auto_reminders(request: Request):
    """Configure automatic reminder schedule."""
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()

    config = {
        "enabled": body.get("enabled", True),
        "intervals_days": body.get("intervals_days", [7, 14, 21, 28]),
        "max_reminders": body.get("max_reminders", 5),
        "updated_by": user["user_id"],
        "updated_at": datetime.now(timezone.utc).isoformat()
    }

    await db.system_settings.update_one(
        {"key": "auto_reminders"},
        {"$set": config},
        upsert=True
    )
    return {"message": "Auto-reminder config updated", "config": config}


@router.get("/auto-config")
async def get_auto_config(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)

    config = await db.system_settings.find_one({"key": "auto_reminders"}, {"_id": 0})
    if not config:
        config = {
            "key": "auto_reminders",
            "enabled": True,
            "intervals_days": [7, 14, 21, 28],
            "max_reminders": 5
        }
    return config


@router.post("/invite-customer")
async def invite_customer(request: Request):
    """Send a customer invitation link from inside the system."""
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()

    case_id = body.get("case_id")
    email = body.get("email")

    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Generate invite token
    invite_token = str(uuid.uuid4())

    # Create or find customer user
    cust_user = await db.users.find_one({"email": email, "global_role": "END_CUSTOMER"}, {"_id": 0})
    if not cust_user:
        cust_user = {
            "id": str(uuid.uuid4()),
            "email": email,
            "name": email.split("@")[0],
            "global_role": "END_CUSTOMER",
            "password_hash": "",
            "mfa_enabled": False,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.users.insert_one({**cust_user})

    # Save invite
    invite = {
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "case_id": case_id,
        "case_ref": case.get("case_ref", ""),
        "email": email,
        "customer_user_id": cust_user["id"],
        "token": invite_token,
        "status": "sent",
        "created_by": user["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "accepted_at": None
    }
    await db.customer_invites.insert_one({**invite})

    # Link questionnaire session if not exists
    existing_session = await db.questionnaire_sessions.find_one({"case_id": case_id}, {"_id": 0})
    if not existing_session:
        await db.questionnaire_sessions.insert_one({
            "id": str(uuid.uuid4()),
            "tenant_id": case["tenant_id"],
            "case_id": case_id,
            "end_customer_user_id": cust_user["id"],
            "token": invite_token,
            "started_at": None,
            "completed_at": None,
            "current_step": "entity_type",
            "answers_json": {},
            "entity_type_determined": None,
            "derived_requirements_json": [],
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    else:
        await db.questionnaire_sessions.update_one(
            {"case_id": case_id},
            {"$set": {"end_customer_user_id": cust_user["id"], "token": invite_token}}
        )

    # Update case status
    if case.get("status") == "draft":
        await db.cases.update_one(
            {"id": case_id},
            {"$set": {"status": "customer_in_progress", "updated_at": datetime.now(timezone.utc).isoformat()}}
        )

    invite_url = f"/portal/invite/{invite_token}"

    # Create reminder record for tracking
    await db.email_reminders.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "case_id": case_id,
        "case_ref": case.get("case_ref", ""),
        "type": "invitation",
        "recipient_email": email,
        "subject": f"KYC Onboarding Invitation - {case.get('case_ref', '')}",
        "missing_items": [],
        "missing_count": 0,
        "sent_by": user["user_id"],
        "sent_by_name": user.get("name", ""),
        "status": "sent",
        "provider": "mock",
        "sent_at": datetime.now(timezone.utc).isoformat(),
        "opened_at": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "customer.invited",
        "entity_type": "customer_invite",
        "entity_id": invite["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": None,
        "after_json": {"email": email, "case_ref": case.get("case_ref"), "invite_url": invite_url},
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })

    return {
        "message": f"Invitation sent to {email} (MOCK - configure email in Settings)",
        "invite_url": invite_url,
        "invite_token": invite_token,
        "invite": invite
    }
