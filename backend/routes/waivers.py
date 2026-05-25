from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import uuid
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/api/waivers", tags=["waivers"])


# Map approval-chain step names to the platform's user roles. A user must
# have the corresponding role (global_role for ADMIN/CASE_MANAGER MLRO
# delegation, or a tenant_role) to advance the step.
STEP_TO_ROLES = {
    "case_manager": {"ADMIN", "CASE_MANAGER"},
    "compliance_officer": {"ADMIN", "CASE_MANAGER"},
    "business_unit_head": {"ADMIN", "CASE_MANAGER"},
    "mlro": {"ADMIN", "CASE_MANAGER"},
}


def _user_can_act_at_step(user: dict, step: str) -> bool:
    allowed = STEP_TO_ROLES.get(step, set())
    role = user.get("global_role")
    if role in allowed:
        return True
    for tr in user.get("tenant_roles", []) or []:
        if tr.get("role") in allowed:
            return True
    return False


def get_db(request: Request):
    return request.app.state.db


@router.post("")
async def create_waiver(request: Request):
    from middleware.auth_middleware import (
        get_current_user, has_permission, require_tenant_access
    )
    user = await get_current_user(request)
    if not has_permission(user, "can_manage_waivers"):
        raise HTTPException(status_code=403, detail="Missing permission: can_manage_waivers")
    db = get_db(request)
    body = await request.json()

    case_id = body.get("case_id")
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    require_tenant_access(case["tenant_id"], user)

    waiver_type = body.get("waiver_type", "temporary")
    expires_at = None
    if waiver_type == "temporary":
        days = min(body.get("duration_days", 90), 90)
        expires_at = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()

    risk = case.get("risk_rating", "medium")
    if risk == "high":
        approval_chain = ["case_manager", "business_unit_head", "mlro"]
    else:
        approval_chain = ["case_manager", "compliance_officer"]

    waiver = {
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "case_id": case_id,
        "waiver_type": waiver_type,
        "requirement_keys_json": body.get("requirement_keys", []),
        "justification": body.get("justification", ""),
        "mitigation_json": body.get("mitigation", {}),
        "requested_by": user["user_id"],
        "requested_at": datetime.now(timezone.utc).isoformat(),
        "approval_chain_json": approval_chain,
        # Track per-step approvals so the chain is verifiable
        "approvals_log_json": [],
        "current_step_index": 0,
        "approved_by": None,
        "approved_at": None,
        "expires_at": expires_at,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.waivers.insert_one({**waiver})

    await db.approval_tasks.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "case_id": case_id,
        "task_type": "waiver_approve",
        "required_role": approval_chain[0] if approval_chain else None,
        "status": "pending",
        "requested_by": user["user_id"],
        "assigned_to": None,
        "due_at": None,
        "completed_at": None,
        "decision": None,
        "decision_notes": None,
        "metadata_json": {"waiver_id": waiver["id"], "approval_chain": approval_chain, "step_index": 0},
        "created_at": datetime.now(timezone.utc).isoformat()
    })

    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "waiver.requested",
        "entity_type": "waiver",
        "entity_id": waiver["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": None,
        "after_json": waiver,
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })

    return waiver


@router.get("")
async def list_waivers(request: Request, tenant_id: Optional[str] = None, status: Optional[str] = None):
    from middleware.auth_middleware import (
        get_current_user, has_permission, scope_tenant_query
    )
    user = await get_current_user(request)
    if not has_permission(user, "can_manage_waivers"):
        raise HTTPException(status_code=403, detail="Missing permission: can_manage_waivers")
    db = get_db(request)

    query = {}
    query = scope_tenant_query(user, query, tenant_id)
    if status:
        query["status"] = status

    waivers = await db.waivers.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return waivers


@router.put("/{waiver_id}/approve")
async def approve_waiver(waiver_id: str, request: Request):
    from middleware.auth_middleware import (
        get_current_user, has_permission, require_tenant_access
    )
    user = await get_current_user(request)
    if not has_permission(user, "can_manage_waivers"):
        raise HTTPException(status_code=403, detail="Missing permission: can_manage_waivers")
    db = get_db(request)
    body = await request.json()

    waiver = await db.waivers.find_one({"id": waiver_id}, {"_id": 0})
    if not waiver:
        raise HTTPException(status_code=404, detail="Waiver not found")
    require_tenant_access(waiver.get("tenant_id", ""), user)

    if waiver.get("status") != "pending":
        raise HTTPException(status_code=400, detail=f"Waiver is not pending (status={waiver.get('status')})")

    # Cannot approve own waiver
    if waiver["requested_by"] == user["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot approve your own waiver request")

    decision = body.get("decision", "approved")
    notes = body.get("notes", "")
    if decision not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="decision must be approved|rejected")

    chain = waiver.get("approval_chain_json") or []
    step_index = waiver.get("current_step_index", 0)

    if decision == "rejected":
        # A single rejection at any step fails the waiver outright.
        update = {
            "status": "rejected",
            "approved_by": user["user_id"],
            "approved_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "approvals_log_json": waiver.get("approvals_log_json", []) + [{
                "step": chain[step_index] if step_index < len(chain) else "unknown",
                "user_id": user["user_id"],
                "decision": "rejected",
                "notes": notes,
                "at": datetime.now(timezone.utc).isoformat(),
            }],
        }
        await db.waivers.update_one({"id": waiver_id}, {"$set": update})
        await db.approval_tasks.update_many(
            {"case_id": waiver["case_id"], "task_type": "waiver_approve",
             "metadata_json.waiver_id": waiver_id, "status": "pending"},
            {"$set": {
                "status": "completed", "decision": "rejected",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "decided_by": user["user_id"],
                "decision_notes": notes,
            }}
        )
        await db.audit_logs.insert_one({
            "id": str(uuid.uuid4()),
            "tenant_id": waiver["tenant_id"],
            "actor_user_id": user["user_id"],
            "actor_role": user.get("global_role", ""),
            "action_key": "waiver.rejected",
            "entity_type": "waiver",
            "entity_id": waiver_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "before_json": {"status": "pending", "step_index": step_index},
            "after_json": {"status": "rejected", "step": chain[step_index] if step_index < len(chain) else "unknown", "notes": notes},
            "ip_address": request.client.host if request.client else "",
            "user_agent": request.headers.get("user-agent", "")
        })
        return await db.waivers.find_one({"id": waiver_id}, {"_id": 0})

    # Approval path: enforce step + role + previously-approved-uniqueness.
    if step_index >= len(chain):
        raise HTTPException(status_code=400, detail="Waiver has no remaining approval steps")
    current_step = chain[step_index]
    if not _user_can_act_at_step(user, current_step):
        raise HTTPException(
            status_code=403,
            detail=f"User cannot approve at step '{current_step}'"
        )

    # Disallow the same user appearing in multiple steps of the chain.
    prior_user_ids = {entry["user_id"] for entry in waiver.get("approvals_log_json", []) if entry.get("decision") == "approved"}
    if user["user_id"] in prior_user_ids:
        raise HTTPException(status_code=400, detail="Same user cannot approve twice in the chain")

    new_log = waiver.get("approvals_log_json", []) + [{
        "step": current_step,
        "user_id": user["user_id"],
        "decision": "approved",
        "notes": notes,
        "at": datetime.now(timezone.utc).isoformat(),
    }]

    next_index = step_index + 1
    is_final = next_index >= len(chain)
    update = {
        "approvals_log_json": new_log,
        "current_step_index": next_index,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if is_final:
        update.update({
            "status": "approved",
            "approved_by": user["user_id"],
            "approved_at": datetime.now(timezone.utc).isoformat(),
        })

    await db.waivers.update_one({"id": waiver_id}, {"$set": update})

    # Update the in-flight approval task and (if more steps remain) create
    # a new one for the next step.
    await db.approval_tasks.update_many(
        {"case_id": waiver["case_id"], "task_type": "waiver_approve",
         "metadata_json.waiver_id": waiver_id, "status": "pending"},
        {"$set": {
            "status": "completed", "decision": "approved",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "decided_by": user["user_id"],
            "decision_notes": notes,
        }}
    )
    if not is_final:
        await db.approval_tasks.insert_one({
            "id": str(uuid.uuid4()),
            "tenant_id": waiver["tenant_id"],
            "case_id": waiver["case_id"],
            "task_type": "waiver_approve",
            "required_role": chain[next_index],
            "status": "pending",
            "requested_by": waiver["requested_by"],
            "assigned_to": None,
            "due_at": None,
            "completed_at": None,
            "decision": None,
            "decision_notes": None,
            "metadata_json": {"waiver_id": waiver_id, "approval_chain": chain, "step_index": next_index},
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    # If fully approved, mark related requirements as waived.
    if is_final:
        for req_key in waiver.get("requirement_keys_json", []):
            await db.requirement_items.update_one(
                {"case_id": waiver["case_id"], "requirement_key": req_key},
                {"$set": {"status": "waived", "updated_at": datetime.now(timezone.utc).isoformat()}}
            )

    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": waiver["tenant_id"],
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "waiver.step_approved" if not is_final else "waiver.fully_approved",
        "entity_type": "waiver",
        "entity_id": waiver_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": {"step_index": step_index, "status": "pending"},
        "after_json": {"step_index": next_index, "step": current_step, "notes": notes, "final": is_final},
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })

    return await db.waivers.find_one({"id": waiver_id}, {"_id": 0})
