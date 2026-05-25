from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import re
import uuid
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/api/intake", tags=["intake"])


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def get_db(request: Request):
    return request.app.state.db


@router.post("/submit")
async def submit_intake(request: Request):
    """Public endpoint: Incoming client submits their data and which bank they need KYC for.

    Hardened: rejects malformed emails, dedups by (email, bank_name) within
    24h, accepts the canonical field set used by the frontend so we don't
    silently drop bank_street/postal_code/mobile/etc.
    """
    db = get_db(request)
    body = await request.json()

    email = (body.get("email") or "").strip().lower()
    if not _EMAIL_RE.match(email):
        raise HTTPException(status_code=400, detail="Valid email required")

    # Dedup: drop a repeat submission from the same email/bank pair within
    # 24h to push back on form-spam without locking out genuine retries.
    twenty_four_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    existing = await db.intake_requests.find_one({
        "email": email,
        "bank_name": body.get("bank_name", ""),
        "created_at": {"$gte": twenty_four_hours_ago},
    }, {"_id": 0, "id": 1})
    if existing:
        return {
            "message": "An intake from this email was already received recently. We'll be in touch.",
            "reference": existing["id"][:8].upper(),
            "duplicate": True,
        }

    intake = {
        "id": str(uuid.uuid4()),
        # Client info (incl. the previously-dropped front-end fields)
        "client_type": body.get("client_type", "legal_entity"),
        "company_name": body.get("company_name", ""),
        "legal_name": body.get("legal_name", ""),
        "first_name": body.get("first_name", ""),
        "last_name": body.get("last_name", ""),
        "email": email,
        "confirm_email": body.get("confirm_email", ""),
        "phone": body.get("phone", "") or body.get("phone_full", ""),
        "phone_code": body.get("phone_code", ""),
        "mobile": body.get("mobile_full", ""),
        "mobile_code": body.get("mobile_code", ""),
        "address": body.get("address", ""),
        "street_number": body.get("street_number", ""),
        "city": body.get("city", ""),
        "postal_code": body.get("postal_code", ""),
        "country": body.get("country", ""),
        "nationality": body.get("nationality", ""),
        "registration_number": body.get("registration_number", ""),
        # Bank info
        "bank_name": body.get("bank_name", ""),
        "bank_address": body.get("bank_address", ""),
        "bank_street": body.get("bank_street", ""),
        "bank_city": body.get("bank_city", ""),
        "bank_country": body.get("bank_country", ""),
        "bank_reference": body.get("bank_reference", ""),
        "product_requested": body.get("product_requested", ""),
        "notes": body.get("notes", ""),
        "status": "new",
        "assigned_tenant_id": None,
        "assigned_case_id": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "submitter_ip": request.client.host if request.client else "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.intake_requests.insert_one({**intake})

    return {
        "message": "Your KYC onboarding request has been submitted. You will receive an invitation link shortly.",
        "reference": intake["id"][:8].upper(),
    }


@router.get("")
async def list_intakes(request: Request, status: Optional[str] = None):
    from middleware.auth_middleware import (
        get_current_user, has_permission, scope_tenant_query
    )
    user = await get_current_user(request)
    if not has_permission(user, "can_manage_intake"):
        raise HTTPException(status_code=403, detail="Missing permission: can_manage_intake")
    db = get_db(request)

    # Tenant scoping: intake records become tenant-scoped *after* they are
    # assigned. Before assignment, only ADMIN and CASE_MANAGER (staff)
    # should see them. Bank users get only their assigned tenants' rows.
    if user.get("global_role") == "ADMIN":
        query = {}
    elif user.get("global_role") == "CASE_MANAGER":
        # CASE_MANAGER can triage incoming intakes (assignment is their job)
        query = {}
    else:
        # Other roles: restrict to assigned tenants only
        query = {}
        query = scope_tenant_query(user, query, None)
        # Mongo: assigned_tenant_id must be in the tenant_id $in set
        if isinstance(query.get("tenant_id"), dict) and "$in" in query["tenant_id"]:
            query["assigned_tenant_id"] = query.pop("tenant_id")

    if status:
        query["status"] = status

    intakes = await db.intake_requests.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)

    for i in intakes:
        if i.get("assigned_tenant_id"):
            tenant = await db.tenants.find_one({"id": i["assigned_tenant_id"]}, {"_id": 0, "name": 1})
            i["assigned_tenant_name"] = tenant.get("name") if tenant else None

    return intakes


@router.get("/{intake_id}")
async def get_intake(intake_id: str, request: Request):
    from middleware.auth_middleware import get_current_user, has_permission
    user = await get_current_user(request)
    if not has_permission(user, "can_manage_intake"):
        raise HTTPException(status_code=403, detail="Missing permission: can_manage_intake")
    db = get_db(request)

    intake = await db.intake_requests.find_one({"id": intake_id}, {"_id": 0})
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")

    # Non-staff readers can only see their own tenant's intake records.
    if user.get("global_role") not in ("ADMIN", "CASE_MANAGER"):
        assigned = intake.get("assigned_tenant_id")
        if not assigned:
            raise HTTPException(status_code=403, detail="Intake not assigned to your tenant")
        user_tenants = {tr.get("tenant_id") for tr in user.get("tenant_roles", []) or []}
        if assigned not in user_tenants:
            raise HTTPException(status_code=403, detail="No access to this intake")

    return intake


@router.post("/{intake_id}/assign")
async def assign_intake(intake_id: str, request: Request):
    """Assign an intake request to a tenant and create a case."""
    from middleware.auth_middleware import (
        get_current_user, has_permission, require_tenant_access
    )
    user = await get_current_user(request)
    # Triage is a staff (CASE_MANAGER+) action.
    if user.get("global_role") not in ("ADMIN", "CASE_MANAGER"):
        raise HTTPException(status_code=403, detail="Only staff can assign intake records")
    if not has_permission(user, "can_manage_intake"):
        raise HTTPException(status_code=403, detail="Missing permission: can_manage_intake")
    db = get_db(request)
    body = await request.json()

    intake = await db.intake_requests.find_one({"id": intake_id}, {"_id": 0})
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    if intake.get("status") not in (None, "new", "reviewed"):
        raise HTTPException(status_code=400, detail=f"Intake cannot be reassigned (status={intake.get('status')})")

    tenant_id = body.get("tenant_id")
    tenant = await db.tenants.find_one({"id": tenant_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    require_tenant_access(tenant_id, user)

    case_ref = f"DDY-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
    case = {
        "id": str(uuid.uuid4()),
        "case_ref": case_ref,
        "tenant_id": tenant_id,
        "case_type": "onboarding",
        "status": "draft",
        "risk_rating": None,
        "due_diligence_level": None,
        "jurisdiction": intake.get("bank_country") or intake.get("country") or "EU",
        "product_scope": intake.get("product_requested", ""),
        "nrd_date": None,
        "created_by": user["user_id"],
        "assigned_maker_id": None,
        "assigned_checker_id": None,
        "assigned_mlro_id": None,
        "sla_json": {},
        "narrative": "",
        "narrative_sections": {},
        "intake_id": intake_id,
        "last_action_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "deleted": False
    }
    await db.cases.insert_one({**case})

    party_type = intake.get("client_type", "legal_entity")
    client_party = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "case_id": case["id"],
        "party_type": party_type,
        "role_in_case": "client",
        "first_name": intake.get("first_name", ""),
        "last_name": intake.get("last_name", ""),
        "legal_name": intake.get("company_name") or intake.get("legal_name", ""),
        "dob": None,
        "nationality": intake.get("nationality", ""),
        "addresses_json": {"registered": f"{intake.get('address', '')}, {intake.get('city', '')}, {intake.get('country', '')}".strip(', ')},
        "identifiers_json": {"registration_number": intake.get("registration_number", "")},
        "ownership_percent": None,
        "control_flags_json": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "deleted": False
    }
    await db.parties.insert_one({**client_party})

    from routes.cases import _generate_requirements
    await _generate_requirements(db, case, client_party)

    await db.intake_requests.update_one(
        {"id": intake_id},
        {"$set": {
            "status": "assigned",
            "assigned_tenant_id": tenant_id,
            "assigned_case_id": case["id"],
            "reviewed_by": user["user_id"],
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "intake.assigned",
        "entity_type": "intake",
        "entity_id": intake_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": {"status": intake.get("status", "new")},
        "after_json": {"status": "assigned", "tenant": tenant["name"], "case_ref": case_ref},
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })

    return {
        "message": f"Assigned to {tenant['name']}. Case {case_ref} created.",
        "case_id": case["id"],
        "case_ref": case_ref
    }


@router.put("/{intake_id}/reject")
async def reject_intake(intake_id: str, request: Request):
    from middleware.auth_middleware import get_current_user, has_permission
    user = await get_current_user(request)
    if user.get("global_role") not in ("ADMIN", "CASE_MANAGER"):
        raise HTTPException(status_code=403, detail="Only staff can reject intake records")
    if not has_permission(user, "can_manage_intake"):
        raise HTTPException(status_code=403, detail="Missing permission: can_manage_intake")
    db = get_db(request)
    body = await request.json()

    intake = await db.intake_requests.find_one({"id": intake_id}, {"_id": 0})
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")

    await db.intake_requests.update_one(
        {"id": intake_id},
        {"$set": {
            "status": "rejected",
            "rejection_reason": body.get("reason", ""),
            "reviewed_by": user["user_id"],
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": intake.get("assigned_tenant_id", ""),
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "intake.rejected",
        "entity_type": "intake",
        "entity_id": intake_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": {"status": intake.get("status")},
        "after_json": {"status": "rejected", "reason": body.get("reason", "")},
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })
    return {"message": "Intake rejected"}
