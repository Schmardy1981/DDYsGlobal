from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


# Map a task_type to the platform role(s) that are allowed to act on it.
# This is the enforcement primitive that prevents a BANK_USER from
# approving an MLRO task.
TASK_TYPE_ROLE_REQUIREMENTS = {
    "mlro_approve": {"ADMIN", "CASE_MANAGER"},  # MLRO is a CASE_MANAGER privilege in this product
    "risk_challenge_approve": {"ADMIN", "CASE_MANAGER"},
    "waiver_approve": {"ADMIN", "CASE_MANAGER"},
    "checker_review": {"ADMIN", "CASE_MANAGER"},
    "business_approval": {"ADMIN", "CASE_MANAGER"},
    "compliance_approval": {"ADMIN", "CASE_MANAGER"},
    "deepfake_escalation": {"ADMIN", "CASE_MANAGER"},
}


def _user_can_decide(user: dict, task: dict) -> bool:
    """A user may decide a task only if:

    1. They hold one of the roles required by the task type, AND
    2. They are not the requester (4-eyes), AND
    3. If the task has an explicit `assigned_to`, they match.
    """
    required = TASK_TYPE_ROLE_REQUIREMENTS.get(task.get("task_type"), {"ADMIN"})
    role = user.get("global_role")
    has_role = role in required
    if not has_role:
        for tr in user.get("tenant_roles", []) or []:
            if tr.get("role") in required:
                has_role = True
                break
    if not has_role:
        return False
    if task.get("requested_by") == user["user_id"]:
        return False
    if task.get("assigned_to") and task["assigned_to"] != user["user_id"]:
        return False
    return True


def get_db(request: Request):
    return request.app.state.db


@router.get("")
async def list_approvals(request: Request, tenant_id: Optional[str] = None, status: Optional[str] = None, case_id: Optional[str] = None):
    from middleware.auth_middleware import (
        get_current_user, has_permission, scope_tenant_query, require_tenant_access
    )
    user = await get_current_user(request)
    if not has_permission(user, "can_approve_cases"):
        raise HTTPException(status_code=403, detail="Missing permission: can_approve_cases")
    db = get_db(request)

    query = {}
    if case_id:
        case = await db.cases.find_one({"id": case_id}, {"_id": 0, "tenant_id": 1})
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        require_tenant_access(case["tenant_id"], user)
        query["case_id"] = case_id
    else:
        query = scope_tenant_query(user, query, tenant_id)
    if status:
        query["status"] = status

    tasks = await db.approval_tasks.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return tasks


@router.post("")
async def create_approval(request: Request):
    from middleware.auth_middleware import (
        get_current_user, has_permission, require_tenant_access
    )
    user = await get_current_user(request)
    if not has_permission(user, "can_approve_cases"):
        raise HTTPException(status_code=403, detail="Missing permission: can_approve_cases")
    db = get_db(request)
    body = await request.json()

    # Verify tenant_id either matches a case the user can see, or matches
    # their tenant_roles directly.
    tenant_id = body.get("tenant_id")
    case_id = body.get("case_id")
    if case_id:
        case = await db.cases.find_one({"id": case_id}, {"_id": 0, "tenant_id": 1})
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        tenant_id = case["tenant_id"]
    require_tenant_access(tenant_id or "", user)

    task_type = body.get("task_type")
    if task_type not in TASK_TYPE_ROLE_REQUIREMENTS:
        raise HTTPException(status_code=400, detail=f"Unknown task_type: {task_type}")

    task = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "case_id": case_id,
        "task_type": task_type,
        "required_role": sorted(TASK_TYPE_ROLE_REQUIREMENTS.get(task_type, set()))[0],
        "status": "pending",
        "requested_by": user["user_id"],
        "assigned_to": body.get("assigned_to"),
        "due_at": body.get("due_at"),
        "completed_at": None,
        "decision": None,
        "decision_notes": None,
        "metadata_json": body.get("metadata", {}),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.approval_tasks.insert_one({**task})

    return task


@router.put("/{task_id}")
async def decide_approval(task_id: str, request: Request):
    from middleware.auth_middleware import (
        get_current_user, has_permission, require_tenant_access
    )
    user = await get_current_user(request)
    if not has_permission(user, "can_approve_cases"):
        raise HTTPException(status_code=403, detail="Missing permission: can_approve_cases")
    db = get_db(request)
    body = await request.json()

    task = await db.approval_tasks.find_one({"id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Approval task not found")

    require_tenant_access(task.get("tenant_id", ""), user)

    if task.get("status") != "pending":
        raise HTTPException(status_code=400, detail=f"Task is not pending (status={task.get('status')})")

    if not _user_can_decide(user, task):
        raise HTTPException(
            status_code=403,
            detail="Caller cannot decide this task (role, 4-eyes, or assignment mismatch)",
        )

    decision = body.get("decision")
    notes = body.get("notes", "")

    if decision not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="Decision must be 'approved' or 'rejected'")

    before = dict(task)
    await db.approval_tasks.update_one(
        {"id": task_id},
        {"$set": {
            "status": "completed",
            "decision": decision,
            "decision_notes": notes,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "decided_by": user["user_id"]
        }}
    )

    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": task["tenant_id"],
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": f"approval.{task['task_type']}.{decision}",
        "entity_type": "approval_task",
        "entity_id": task_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": before,
        "after_json": {"decision": decision, "notes": notes},
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })

    return await db.approval_tasks.find_one({"id": task_id}, {"_id": 0})
