from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


def get_db(request: Request):
    return request.app.state.db


@router.get("")
async def list_approvals(request: Request, tenant_id: Optional[str] = None, status: Optional[str] = None, case_id: Optional[str] = None):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    query = {}
    if tenant_id:
        query["tenant_id"] = tenant_id
    if status:
        query["status"] = status
    if case_id:
        query["case_id"] = case_id
    
    tasks = await db.approval_tasks.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return tasks


@router.post("")
async def create_approval(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()
    
    task = {
        "id": str(uuid.uuid4()),
        "tenant_id": body.get("tenant_id"),
        "case_id": body.get("case_id"),
        "task_type": body.get("task_type"),
        "status": "pending",
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
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()
    
    task = await db.approval_tasks.find_one({"id": task_id}, {"_id": 0})
    if not task:
        raise HTTPException(status_code=404, detail="Approval task not found")
    
    decision = body.get("decision")  # approved, rejected
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
