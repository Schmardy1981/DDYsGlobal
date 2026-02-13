from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import uuid
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/api/edr", tags=["edr"])


def get_db(request: Request):
    return request.app.state.db


@router.get("")
async def list_edr_alerts(request: Request, tenant_id: Optional[str] = None, status: Optional[str] = None):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    query = {}
    if tenant_id:
        query["tenant_id"] = tenant_id
    if status:
        query["status"] = status
    
    alerts = await db.edr_alerts.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return alerts


@router.post("")
async def create_edr_alert(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()
    
    case_id = body.get("case_id")
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    now = datetime.now(timezone.utc)
    alert = {
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "case_id": case_id,
        "trigger_event_type": body.get("trigger_event_type", "manual"),
        "trigger_event_date": body.get("trigger_event_date", now.isoformat()),
        "detected_by": body.get("detected_by", "ddys"),
        "alert_generated_at": now.isoformat(),
        "alert_review_due_at": (now + timedelta(days=28)).isoformat(),
        "completion_due_at": (now + timedelta(days=90)).isoformat(),
        "status": "open",
        "escalation_to_mlro_at": None,
        "notes": body.get("notes", ""),
        "created_at": now.isoformat()
    }
    await db.edr_alerts.insert_one({**alert})
    
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "edr_alert.created",
        "entity_type": "edr_alert",
        "entity_id": alert["id"],
        "timestamp": now.isoformat(),
        "before_json": None,
        "after_json": alert,
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })
    
    return alert


@router.put("/{alert_id}")
async def update_edr_alert(alert_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()
    
    alert = await db.edr_alerts.find_one({"id": alert_id}, {"_id": 0})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    updates = {}
    if "status" in body:
        updates["status"] = body["status"]
    if "notes" in body:
        updates["notes"] = body["notes"]
    if body.get("escalate_to_mlro"):
        updates["escalation_to_mlro_at"] = datetime.now(timezone.utc).isoformat()
    
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.edr_alerts.update_one({"id": alert_id}, {"$set": updates})
    
    return await db.edr_alerts.find_one({"id": alert_id}, {"_id": 0})


@router.post("/{alert_id}/decide")
async def decide_edr(alert_id: str, request: Request):
    """Decide: Full EDR vs KUP."""
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()
    
    alert = await db.edr_alerts.find_one({"id": alert_id}, {"_id": 0})
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    
    decision = body.get("decision")  # "edr_full" or "kup"
    
    if decision == "edr_full":
        # Create full EDR case
        from routes.cases import CaseCreate
        case = await db.cases.find_one({"id": alert["case_id"]}, {"_id": 0})
        new_case = {
            "id": str(uuid.uuid4()),
            "case_ref": f"DDY-{datetime.now(timezone.utc).strftime('%Y%m%d')}-EDR{str(uuid.uuid4())[:4].upper()}",
            "tenant_id": alert["tenant_id"],
            "case_type": "edr_full",
            "status": "draft",
            "risk_rating": case.get("risk_rating") if case else None,
            "due_diligence_level": case.get("due_diligence_level") if case else None,
            "jurisdiction": case.get("jurisdiction", "EU") if case else "EU",
            "product_scope": case.get("product_scope") if case else None,
            "nrd_date": None,
            "created_by": user["user_id"],
            "assigned_maker_id": None,
            "assigned_checker_id": None,
            "assigned_mlro_id": None,
            "sla_json": {"completion_due": alert["completion_due_at"]},
            "narrative": "",
            "narrative_sections": {},
            "last_action_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "deleted": False
        }
        await db.cases.insert_one({**new_case})
        await db.edr_alerts.update_one({"id": alert_id}, {"$set": {"status": "edr_created", "edr_case_id": new_case["id"]}})
        return {"message": "Full EDR case created", "new_case_id": new_case["id"]}
    
    elif decision == "kup":
        # Create KUP case
        case = await db.cases.find_one({"id": alert["case_id"]}, {"_id": 0})
        new_case = {
            "id": str(uuid.uuid4()),
            "case_ref": f"DDY-{datetime.now(timezone.utc).strftime('%Y%m%d')}-KUP{str(uuid.uuid4())[:4].upper()}",
            "tenant_id": alert["tenant_id"],
            "case_type": "kup",
            "status": "draft",
            "risk_rating": case.get("risk_rating") if case else None,
            "due_diligence_level": case.get("due_diligence_level") if case else None,
            "jurisdiction": case.get("jurisdiction", "EU") if case else "EU",
            "product_scope": case.get("product_scope") if case else None,
            "nrd_date": case.get("nrd_date") if case else None,  # KUP does NOT reset NRD
            "created_by": user["user_id"],
            "assigned_maker_id": None,
            "assigned_checker_id": None,
            "assigned_mlro_id": None,
            "sla_json": {"completion_due": alert["completion_due_at"]},
            "narrative": "",
            "narrative_sections": {},
            "last_action_at": datetime.now(timezone.utc).isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "deleted": False
        }
        await db.cases.insert_one({**new_case})
        await db.edr_alerts.update_one({"id": alert_id}, {"$set": {"status": "kup_created", "kup_case_id": new_case["id"]}})
        return {"message": "KUP case created (NRD not reset)", "new_case_id": new_case["id"]}
    
    raise HTTPException(status_code=400, detail="Decision must be 'edr_full' or 'kup'")
