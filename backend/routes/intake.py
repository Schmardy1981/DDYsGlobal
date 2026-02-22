from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/api/intake", tags=["intake"])


def get_db(request: Request):
    return request.app.state.db


@router.post("/submit")
async def submit_intake(request: Request):
    """Public endpoint: Incoming client submits their data and which bank they need KYC for."""
    db = get_db(request)
    body = await request.json()

    intake = {
        "id": str(uuid.uuid4()),
        # Client info
        "client_type": body.get("client_type", "legal_entity"),  # legal_entity or natural_person
        "company_name": body.get("company_name", ""),
        "legal_name": body.get("legal_name", ""),
        "first_name": body.get("first_name", ""),
        "last_name": body.get("last_name", ""),
        "email": body.get("email", ""),
        "phone": body.get("phone", ""),
        "address": body.get("address", ""),
        "city": body.get("city", ""),
        "country": body.get("country", ""),
        "nationality": body.get("nationality", ""),
        "registration_number": body.get("registration_number", ""),
        # Bank info (which bank is this for)
        "bank_name": body.get("bank_name", ""),
        "bank_address": body.get("bank_address", ""),
        "bank_country": body.get("bank_country", ""),
        "bank_reference": body.get("bank_reference", ""),
        "product_requested": body.get("product_requested", ""),
        "notes": body.get("notes", ""),
        # Status
        "status": "new",  # new, reviewed, assigned, rejected
        "assigned_tenant_id": None,
        "assigned_case_id": None,
        "reviewed_by": None,
        "reviewed_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.intake_requests.insert_one({**intake})

    return {"message": "Your KYC onboarding request has been submitted. You will receive an invitation link shortly.", "reference": intake["id"][:8].upper()}


@router.get("")
async def list_intakes(request: Request, status: Optional[str] = None):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)

    query = {}
    if status:
        query["status"] = status

    intakes = await db.intake_requests.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)

    # Enrich with tenant name if assigned
    for i in intakes:
        if i.get("assigned_tenant_id"):
            tenant = await db.tenants.find_one({"id": i["assigned_tenant_id"]}, {"_id": 0, "name": 1})
            i["assigned_tenant_name"] = tenant.get("name") if tenant else None

    return intakes


@router.get("/{intake_id}")
async def get_intake(intake_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)

    intake = await db.intake_requests.find_one({"id": intake_id}, {"_id": 0})
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")
    return intake


@router.post("/{intake_id}/assign")
async def assign_intake(intake_id: str, request: Request):
    """Assign an intake request to a tenant and create a case."""
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()

    intake = await db.intake_requests.find_one({"id": intake_id}, {"_id": 0})
    if not intake:
        raise HTTPException(status_code=404, detail="Intake not found")

    tenant_id = body.get("tenant_id")
    tenant = await db.tenants.find_one({"id": tenant_id}, {"_id": 0})
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Create case
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

    # Create client party from intake data
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

    # Generate requirements
    from routes.cases import _generate_requirements
    await _generate_requirements(db, case, client_party)

    # Update intake status
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

    # Audit
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "intake.assigned",
        "entity_type": "intake",
        "entity_id": intake_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": {"status": "new"},
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
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()

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
    return {"message": "Intake rejected"}
