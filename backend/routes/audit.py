from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/api/audit", tags=["audit"])


def get_db(request: Request):
    return request.app.state.db


@router.get("")
async def list_audit_logs(request: Request, tenant_id: Optional[str] = None, entity_type: Optional[str] = None, entity_id: Optional[str] = None, limit: int = 100):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    query = {}
    if tenant_id:
        query["tenant_id"] = tenant_id
    if entity_type:
        query["entity_type"] = entity_type
    if entity_id:
        query["entity_id"] = entity_id
    
    logs = await db.audit_logs.find(query, {"_id": 0}).sort("timestamp", -1).to_list(limit)
    return logs


@router.get("/case/{case_id}")
async def get_case_audit(case_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    # Get all audit entries related to this case
    logs = await db.audit_logs.find(
        {"$or": [
            {"entity_id": case_id, "entity_type": "case"},
            {"entity_id": case_id},
        ]},
        {"_id": 0}
    ).sort("timestamp", -1).to_list(500)
    
    # Also get related entity logs
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if case:
        parties = await db.parties.find({"case_id": case_id}, {"_id": 0, "id": 1}).to_list(100)
        party_ids = [p["id"] for p in parties]
        
        related_logs = await db.audit_logs.find(
            {"entity_id": {"$in": party_ids}},
            {"_id": 0}
        ).sort("timestamp", -1).to_list(500)
        
        logs.extend(related_logs)
    
    # Deduplicate and sort
    seen = set()
    unique_logs = []
    for log in logs:
        if log["id"] not in seen:
            seen.add(log["id"])
            unique_logs.append(log)
    unique_logs.sort(key=lambda x: x["timestamp"], reverse=True)
    
    return unique_logs
