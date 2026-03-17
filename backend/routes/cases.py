from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List
import uuid
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/api/cases", tags=["cases"])

CASE_STATUSES = [
    "draft", "customer_in_progress", "customer_submitted",
    "automated_checks", "maker_review", "checker_review",
    "business_approval", "compliance_approval", "mlro_approval",
    "completed", "restricted", "rejected", "offboarded"
]
CASE_TYPES = ["onboarding", "rr", "edr_full", "kup", "npe", "exit"]
RISK_RATINGS = ["low", "medium", "high"]
DD_LEVELS = ["cdd", "edd"]


class CaseCreate(BaseModel):
    tenant_id: str
    case_type: str = "onboarding"
    jurisdiction: str = "EU"
    product_scope: Optional[str] = None

class CaseUpdate(BaseModel):
    status: Optional[str] = None
    risk_rating: Optional[str] = None
    due_diligence_level: Optional[str] = None
    jurisdiction: Optional[str] = None
    product_scope: Optional[str] = None
    assigned_maker_id: Optional[str] = None
    assigned_checker_id: Optional[str] = None
    assigned_mlro_id: Optional[str] = None
    narrative: Optional[str] = None
    narrative_sections: Optional[dict] = None


def get_db(request: Request):
    return request.app.state.db


@router.get("")
async def list_cases(request: Request, tenant_id: Optional[str] = None, status: Optional[str] = None, risk_rating: Optional[str] = None, case_type: Optional[str] = None):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    query = {"deleted": {"$ne": True}}
    if tenant_id:
        query["tenant_id"] = tenant_id
    elif user.get("global_role") not in ["ADMIN"]:
        tenant_ids = [tr["tenant_id"] for tr in user.get("tenant_roles", [])]
        query["tenant_id"] = {"$in": tenant_ids}
    
    if status:
        query["status"] = status
    if risk_rating:
        query["risk_rating"] = risk_rating
    if case_type:
        query["case_type"] = case_type
    
    cases = await db.cases.find(query, {
        "_id": 0, "id": 1, "case_ref": 1, "tenant_id": 1, "case_type": 1,
        "status": 1, "risk_rating": 1, "due_diligence_level": 1, "jurisdiction": 1,
        "product_scope": 1, "nrd_date": 1, "created_at": 1, "updated_at": 1,
        "assigned_maker_id": 1, "assigned_checker_id": 1, "last_action_at": 1
    }).sort("created_at", -1).to_list(1000)
    return cases


@router.post("")
async def create_case(body: CaseCreate, request: Request):
    from middleware.auth_middleware import get_current_user, require_tenant_access
    user = await get_current_user(request)
    require_tenant_access(body.tenant_id, user)
    db = get_db(request)
    
    case_ref = f"DDY-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(uuid.uuid4())[:6].upper()}"
    
    case = {
        "id": str(uuid.uuid4()),
        "case_ref": case_ref,
        "tenant_id": body.tenant_id,
        "case_type": body.case_type,
        "status": "draft",
        "risk_rating": None,
        "due_diligence_level": None,
        "jurisdiction": body.jurisdiction,
        "product_scope": body.product_scope,
        "nrd_date": None,
        "created_by": user["user_id"],
        "assigned_maker_id": None,
        "assigned_checker_id": None,
        "assigned_mlro_id": None,
        "sla_json": {},
        "narrative": "",
        "narrative_sections": {},
        "last_action_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "deleted": False
    }
    await db.cases.insert_one({**case})
    
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": body.tenant_id,
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "case.created",
        "entity_type": "case",
        "entity_id": case["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": None,
        "after_json": case,
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })
    
    return case


@router.get("/{case_id}")
async def get_case(case_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    case = await db.cases.find_one({"id": case_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Enrich with related data
    parties = await db.parties.find({"case_id": case_id, "deleted": {"$ne": True}}, {"_id": 0}).to_list(100)
    requirements = await db.requirement_items.find({"case_id": case_id}, {"_id": 0}).to_list(500)
    documents = await db.documents.find({"case_id": case_id}, {"_id": 0}).to_list(500)
    screening_runs = await db.screening_runs.find({"case_id": case_id}, {"_id": 0}).to_list(100)
    risk_assessments = await db.risk_assessments.find({"case_id": case_id}, {"_id": 0}).to_list(10)
    approval_tasks = await db.approval_tasks.find({"case_id": case_id}, {"_id": 0}).to_list(100)
    waivers = await db.waivers.find({"case_id": case_id}, {"_id": 0}).to_list(50)
    
    case["parties"] = parties
    case["requirements"] = requirements
    case["documents"] = documents
    case["screening_runs"] = screening_runs
    case["risk_assessments"] = risk_assessments
    case["approval_tasks"] = approval_tasks
    case["waivers"] = waivers
    
    return case


@router.put("/{case_id}")
async def update_case(case_id: str, body: CaseUpdate, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    before = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Case not found")
    
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    updates["last_action_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.cases.update_one({"id": case_id}, {"$set": updates})
    after = await db.cases.find_one({"id": case_id}, {"_id": 0})
    
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": before["tenant_id"],
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "case.updated",
        "entity_type": "case",
        "entity_id": case_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": before,
        "after_json": after,
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })
    
    return after



@router.put("/{case_id}/status")
async def quick_status_change(case_id: str, request: Request):
    """Quick status change (admin/staff only, no gating)."""
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()
    new_status = body.get("status")

    if new_status not in CASE_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")

    before = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Case not found")

    await db.cases.update_one({"id": case_id}, {"$set": {
        "status": new_status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_action_at": datetime.now(timezone.utc).isoformat()
    }})

    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": before["tenant_id"],
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": f"case.status_changed.{before['status']}_to_{new_status}",
        "entity_type": "case",
        "entity_id": case_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": {"status": before["status"]},
        "after_json": {"status": new_status},
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })

    return {"message": f"Status changed to {new_status}"}



@router.post("/{case_id}/transition")
async def transition_case(case_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()
    target_status = body.get("target_status")
    notes = body.get("notes", "")
    
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    current = case["status"]
    
    # Validate transition
    valid_transitions = {
        "draft": ["customer_in_progress"],
        "customer_in_progress": ["customer_submitted"],
        "customer_submitted": ["automated_checks"],
        "automated_checks": ["maker_review"],
        "maker_review": ["checker_review", "customer_in_progress"],
        "checker_review": ["maker_review", "business_approval", "compliance_approval", "completed"],
        "business_approval": ["compliance_approval", "mlro_approval", "completed"],
        "compliance_approval": ["mlro_approval", "completed"],
        "mlro_approval": ["completed"],
        "completed": ["restricted", "offboarded"],
        "restricted": ["maker_review", "offboarded"],
    }
    
    allowed = valid_transitions.get(current, [])
    if target_status not in allowed:
        raise HTTPException(status_code=400, detail=f"Cannot transition from {current} to {target_status}")
    
    # Gating rules
    if target_status == "checker_review":
        # Maker review cannot complete unless all requirements are approved or waived
        reqs = await db.requirement_items.find({"case_id": case_id}, {"_id": 0}).to_list(500)
        for req in reqs:
            if req["status"] not in ["approved", "waived", "auto_passed"]:
                raise HTTPException(status_code=400, detail=f"Requirement '{req['requirement_key']}' is not approved/waived (status: {req['status']})")
    
    if target_status == "checker_review" and case.get("assigned_maker_id") == user["user_id"]:
        # Maker cannot be checker (but in this case we're transitioning TO checker, so the checker will validate)
        pass
    
    if target_status == "completed" and case.get("risk_rating") == "high":
        # High-risk cases need MLRO approval
        mlro_approval = await db.approval_tasks.find_one({
            "case_id": case_id,
            "task_type": "mlro_approve",
            "status": "completed",
            "decision": "approved"
        }, {"_id": 0})
        if not mlro_approval:
            raise HTTPException(status_code=400, detail="High-risk cases require MLRO approval before completion")
    
    # Perform transition
    update_data = {
        "status": target_status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "last_action_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Set NRD for completed onboarding
    if target_status == "completed" and case["case_type"] in ["onboarding", "edr_full"]:
        risk = case.get("risk_rating", "medium")
        months_map = {"high": 12, "medium": 24, "low": 60}
        months = months_map.get(risk, 24)
        nrd = datetime.now(timezone.utc) + timedelta(days=months * 30)
        update_data["nrd_date"] = nrd.isoformat()
    
    await db.cases.update_one({"id": case_id}, {"$set": update_data})
    
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": f"case.transition.{current}_to_{target_status}",
        "entity_type": "case",
        "entity_id": case_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": {"status": current},
        "after_json": {"status": target_status, "notes": notes},
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })
    
    updated = await db.cases.find_one({"id": case_id}, {"_id": 0})
    return updated


@router.post("/{case_id}/parties")
async def add_party(case_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()
    
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    party = {
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "case_id": case_id,
        "party_type": body.get("party_type", "natural_person"),
        "role_in_case": body.get("role_in_case", "client"),
        "first_name": body.get("first_name", ""),
        "last_name": body.get("last_name", ""),
        "legal_name": body.get("legal_name", ""),
        "dob": body.get("dob"),
        "nationality": body.get("nationality", ""),
        "addresses_json": body.get("addresses_json", {}),
        "identifiers_json": body.get("identifiers_json", {}),
        "ownership_percent": body.get("ownership_percent"),
        "control_flags_json": body.get("control_flags_json", {}),
        "parent_party_id": body.get("parent_party_id"),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "deleted": False
    }
    await db.parties.insert_one({**party})
    
    # Generate requirements for this party based on type and role
    await _generate_requirements(db, case, party)
    
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "party.created",
        "entity_type": "party",
        "entity_id": party["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": None,
        "after_json": party,
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })
    
    return party


@router.put("/{case_id}/parties/{party_id}")
async def update_party(case_id: str, party_id: str, request: Request):
    """Edit party data (all fields editable by hand)."""
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()

    before = await db.parties.find_one({"id": party_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Party not found")

    editable = [
        "party_type", "role_in_case", "first_name", "last_name", "legal_name",
        "dob", "nationality", "addresses_json", "identifiers_json",
        "ownership_percent", "control_flags_json", "parent_party_id"
    ]
    updates = {k: v for k, v in body.items() if k in editable}
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.parties.update_one({"id": party_id}, {"$set": updates})
    after = await db.parties.find_one({"id": party_id}, {"_id": 0})

    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": before["tenant_id"],
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "party.updated",
        "entity_type": "party",
        "entity_id": party_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": before,
        "after_json": after,
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })

    return after




async def _generate_requirements(db, case, party):
    """Generate KYC requirements based on party type and role."""
    base_reqs = []
    
    if party["party_type"] == "natural_person":
        base_reqs = [
            {"key": "identity_doc", "category": "identity", "label": "Government-issued ID"},
            {"key": "proof_of_address", "category": "address", "label": "Proof of Address"},
            {"key": "sanctions_screening", "category": "sanctions", "label": "Sanctions Screening"},
            {"key": "pep_screening", "category": "pep", "label": "PEP Screening"},
            {"key": "adverse_media", "category": "adverse_media", "label": "Adverse Media Check"},
        ]
        if party["role_in_case"] in ["client", "ubo"]:
            base_reqs.append({"key": "sof_sow", "category": "sof_sow", "label": "Source of Funds / Source of Wealth"})
            base_reqs.append({"key": "video_ident", "category": "video_ident", "label": "Video Identification"})
    
    elif party["party_type"] == "legal_entity":
        base_reqs = [
            {"key": "registry_extract", "category": "existence", "label": "Registry Extract / Certificate of Incorporation"},
            {"key": "ownership_chart", "category": "ownership", "label": "Ownership Structure Chart"},
            {"key": "articles_of_association", "category": "authority", "label": "Articles of Association / Memorandum"},
            {"key": "board_resolution", "category": "authority", "label": "Board Resolution / Authority to Act"},
            {"key": "proof_of_address_entity", "category": "address", "label": "Proof of Business Address"},
            {"key": "sanctions_screening_entity", "category": "sanctions", "label": "Entity Sanctions Screening"},
            {"key": "adverse_media_entity", "category": "adverse_media", "label": "Entity Adverse Media Check"},
            {"key": "financial_statements", "category": "sof_sow", "label": "Financial Statements / Annual Report"},
        ]
    
    elif party["party_type"] in ["trust", "foundation"]:
        base_reqs = [
            {"key": "trust_deed", "category": "existence", "label": "Trust Deed / Foundation Charter"},
            {"key": "registry_extract_trust", "category": "existence", "label": "Registry Extract (if applicable)"},
            {"key": "proof_of_address_trust", "category": "address", "label": "Proof of Address"},
            {"key": "sanctions_screening_trust", "category": "sanctions", "label": "Sanctions Screening"},
        ]
    
    for req in base_reqs:
        item = {
            "id": str(uuid.uuid4()),
            "tenant_id": case["tenant_id"],
            "case_id": case["id"],
            "party_id": party["id"],
            "requirement_key": req["key"],
            "requirement_label": req.get("label", req["key"]),
            "requirement_category": req["category"],
            "status": "missing",
            "due_date": None,
            "rule_source": "kos",
            "notes": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.requirement_items.insert_one({**item})


@router.get("/{case_id}/requirements")
async def get_requirements(case_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    reqs = await db.requirement_items.find({"case_id": case_id}, {"_id": 0}).to_list(500)
    return reqs


@router.put("/{case_id}/requirements/{req_id}")
async def update_requirement(case_id: str, req_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()
    
    before = await db.requirement_items.find_one({"id": req_id}, {"_id": 0})
    if not before:
        raise HTTPException(status_code=404, detail="Requirement not found")
    
    updates = {k: v for k, v in body.items() if k in ["status", "notes", "due_date"]}
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.requirement_items.update_one({"id": req_id}, {"$set": updates})
    
    after = await db.requirement_items.find_one({"id": req_id}, {"_id": 0})
    
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": before["tenant_id"],
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "requirement.updated",
        "entity_type": "requirement_item",
        "entity_id": req_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": before,
        "after_json": after,
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })
    
    return after
