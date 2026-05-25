from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/api/risk", tags=["risk"])


def get_db(request: Request):
    return request.app.state.db


@router.post("/assess")
async def assess_risk(request: Request):
    from middleware.auth_middleware import (
        get_current_user, has_permission, require_tenant_access
    )
    user = await get_current_user(request)
    if not has_permission(user, "can_run_screening"):
        raise HTTPException(status_code=403, detail="Missing permission: can_run_screening")
    db = get_db(request)
    body = await request.json()

    case_id = body.get("case_id")
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    require_tenant_access(case["tenant_id"], user)

    inputs = body.get("inputs") or {}
    from services.risk_engine import compute_risk
    assessment = await compute_risk(db, case, inputs)

    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "risk.assessed",
        "entity_type": "risk_assessment",
        "entity_id": assessment["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": None,
        "after_json": assessment,
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })

    return assessment


@router.get("/{case_id}")
async def get_risk_assessments(case_id: str, request: Request):
    from middleware.auth_middleware import get_current_user, require_tenant_access
    user = await get_current_user(request)
    db = get_db(request)

    case = await db.cases.find_one({"id": case_id}, {"_id": 0, "tenant_id": 1})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    require_tenant_access(case["tenant_id"], user)

    assessments = await db.risk_assessments.find({"case_id": case_id}, {"_id": 0}).sort("created_at", -1).to_list(10)
    return assessments


@router.post("/challenge")
async def challenge_risk(request: Request):
    from middleware.auth_middleware import (
        get_current_user, has_permission, require_tenant_access
    )
    user = await get_current_user(request)
    if not has_permission(user, "can_approve_cases"):
        raise HTTPException(status_code=403, detail="Missing permission: can_approve_cases")
    db = get_db(request)
    body = await request.json()

    assessment_id = body.get("assessment_id")
    challenge_reason = body.get("challenge_reason")
    proposed_rating = body.get("proposed_rating")

    assessment = await db.risk_assessments.find_one({"id": assessment_id}, {"_id": 0})
    if not assessment:
        raise HTTPException(status_code=404, detail="Assessment not found")
    require_tenant_access(assessment.get("tenant_id", ""), user)

    # Per-se flags prevent downgrade to low
    per_se = assessment.get("per_se_flags_json", {})
    if per_se.get("pep") or per_se.get("high_risk_country"):
        if proposed_rating == "low":
            raise HTTPException(status_code=400, detail="Per-se high risk flags prevent downgrade to low")

    await db.risk_assessments.update_one(
        {"id": assessment_id},
        {"$set": {
            "challenged": True,
            "challenge_reason": challenge_reason,
            "challenge_proposed_rating": proposed_rating,
            "challenge_by": user["user_id"],
            "challenge_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    case = await db.cases.find_one({"id": assessment["case_id"]}, {"_id": 0})
    await db.approval_tasks.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": assessment["tenant_id"],
        "case_id": assessment["case_id"],
        "task_type": "risk_challenge_approve",
        "required_role": "mlro",
        "status": "pending",
        "assigned_to": case.get("assigned_mlro_id"),
        "requested_by": user["user_id"],
        "due_at": None,
        "completed_at": None,
        "decision": None,
        "decision_notes": None,
        "metadata_json": {"assessment_id": assessment_id, "proposed_rating": proposed_rating, "reason": challenge_reason},
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": assessment["tenant_id"],
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "risk.challenged",
        "entity_type": "risk_assessment",
        "entity_id": assessment_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": {"rating": assessment.get("computed_rating")},
        "after_json": {"proposed_rating": proposed_rating, "reason": challenge_reason},
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })

    return {"message": "Challenge submitted, pending MLRO approval"}
