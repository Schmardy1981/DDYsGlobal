from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import uuid
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/api/waivers", tags=["waivers"])


def get_db(request: Request):
    return request.app.state.db


@router.post("")
async def create_waiver(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()
    
    case_id = body.get("case_id")
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    waiver_type = body.get("waiver_type", "temporary")
    expires_at = None
    if waiver_type == "temporary":
        days = min(body.get("duration_days", 90), 90)
        expires_at = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    
    # Build approval chain based on risk
    risk = case.get("risk_rating", "medium")
    approval_chain = []
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
        "approved_by": None,
        "approved_at": None,
        "expires_at": expires_at,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.waivers.insert_one({**waiver})
    
    # Create approval task
    await db.approval_tasks.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "case_id": case_id,
        "task_type": "waiver_approve",
        "status": "pending",
        "assigned_to": None,
        "due_at": None,
        "completed_at": None,
        "decision": None,
        "decision_notes": None,
        "metadata_json": {"waiver_id": waiver["id"], "approval_chain": approval_chain},
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
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    query = {}
    if tenant_id:
        query["tenant_id"] = tenant_id
    if status:
        query["status"] = status
    
    waivers = await db.waivers.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return waivers


@router.put("/{waiver_id}/approve")
async def approve_waiver(waiver_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()
    
    waiver = await db.waivers.find_one({"id": waiver_id}, {"_id": 0})
    if not waiver:
        raise HTTPException(status_code=404, detail="Waiver not found")
    
    # Cannot approve own waiver
    if waiver["requested_by"] == user["user_id"]:
        raise HTTPException(status_code=400, detail="Cannot approve your own waiver request")
    
    decision = body.get("decision", "approved")
    notes = body.get("notes", "")
    
    update = {
        "status": "approved" if decision == "approved" else "rejected",
        "approved_by": user["user_id"],
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.waivers.update_one({"id": waiver_id}, {"$set": update})
    
    # If approved, update requirement statuses
    if decision == "approved":
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
        "action_key": f"waiver.{decision}",
        "entity_type": "waiver",
        "entity_id": waiver_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": {"status": "pending"},
        "after_json": {"status": update["status"], "notes": notes},
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })
    
    return await db.waivers.find_one({"id": waiver_id}, {"_id": 0})
