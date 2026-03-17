from fastapi import APIRouter, HTTPException, Request
from typing import Optional
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/api/mi", tags=["mi"])


def get_db(request: Request):
    return request.app.state.db


@router.get("/dashboard")
async def get_dashboard(request: Request, tenant_id: Optional[str] = None):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    query = {"deleted": {"$ne": True}}
    if tenant_id:
        query["tenant_id"] = tenant_id
    
    # Pipeline volumes by stage - only fetch fields needed for aggregation
    cases = await db.cases.find(query, {
        "_id": 0, "id": 1, "status": 1, "risk_rating": 1, "case_type": 1, "nrd_date": 1
    }).to_list(5000)
    
    pipeline = {}
    risk_dist = {"low": 0, "medium": 0, "high": 0, "unrated": 0}
    type_dist = {}
    
    for c in cases:
        status = c.get("status", "unknown")
        pipeline[status] = pipeline.get(status, 0) + 1
        
        risk = c.get("risk_rating") or "unrated"
        risk_dist[risk] = risk_dist.get(risk, 0) + 1
        
        ct = c.get("case_type", "unknown")
        type_dist[ct] = type_dist.get(ct, 0) + 1
    
    # Overdue NRD
    now = datetime.now(timezone.utc).isoformat()
    nrd_query = {**query, "nrd_date": {"$ne": None, "$lt": now}, "status": "completed"}
    overdue_nrd = await db.cases.count_documents(nrd_query)
    
    # NRD due in 30/60/90 days
    nrd_30 = await db.cases.count_documents({
        **query,
        "nrd_date": {"$ne": None, "$lt": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(), "$gte": now},
        "status": "completed"
    })
    nrd_60 = await db.cases.count_documents({
        **query,
        "nrd_date": {"$ne": None, "$lt": (datetime.now(timezone.utc) + timedelta(days=60)).isoformat(), "$gte": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()},
        "status": "completed"
    })
    nrd_90 = await db.cases.count_documents({
        **query,
        "nrd_date": {"$ne": None, "$lt": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(), "$gte": (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()},
        "status": "completed"
    })
    
    # EDR alerts
    edr_query = {}
    if tenant_id:
        edr_query["tenant_id"] = tenant_id
    edr_total = await db.edr_alerts.count_documents(edr_query)
    edr_open = await db.edr_alerts.count_documents({**edr_query, "status": "open"})
    edr_breached = await db.edr_alerts.count_documents({
        **edr_query,
        "alert_review_due_at": {"$lt": now},
        "status": "open"
    })
    
    # Waivers
    waiver_query = {}
    if tenant_id:
        waiver_query["tenant_id"] = tenant_id
    waiver_pending = await db.waivers.count_documents({**waiver_query, "status": "pending"})
    waiver_active = await db.waivers.count_documents({**waiver_query, "status": "approved"})
    
    # Screening hits
    hit_query = {}
    if tenant_id:
        runs = await db.screening_runs.find({"tenant_id": tenant_id}, {"_id": 0, "id": 1}).to_list(1000)
        run_ids = [r["id"] for r in runs]
        hit_query["screening_run_id"] = {"$in": run_ids}
    hits_open = await db.screening_hits.count_documents({**hit_query, "disposition": "open"})
    hits_total = await db.screening_hits.count_documents(hit_query)
    
    return {
        "total_cases": len(cases),
        "pipeline": pipeline,
        "risk_distribution": risk_dist,
        "case_type_distribution": type_dist,
        "nrd": {
            "overdue": overdue_nrd,
            "due_30d": nrd_30,
            "due_60d": nrd_60,
            "due_90d": nrd_90
        },
        "edr": {
            "total": edr_total,
            "open": edr_open,
            "sla_breached": edr_breached
        },
        "waivers": {
            "pending": waiver_pending,
            "active": waiver_active
        },
        "screening": {
            "hits_open": hits_open,
            "hits_total": hits_total
        }
    }


@router.get("/global")
async def get_global_dashboard(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    if user.get("global_role") not in ["ADMIN", "CASE_MANAGER"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    
    # Get per-tenant stats
    tenants = await db.tenants.find({"deleted": {"$ne": True}}, {"_id": 0}).to_list(500)
    tenant_stats = []
    
    total_cases = 0
    total_open_hits = 0
    total_overdue = 0
    
    for t in tenants:
        case_count = await db.cases.count_documents({"tenant_id": t["id"], "deleted": {"$ne": True}})
        active_cases = await db.cases.count_documents({"tenant_id": t["id"], "deleted": {"$ne": True}, "status": {"$nin": ["completed", "rejected", "offboarded"]}})
        total_cases += case_count
        
        tenant_stats.append({
            "tenant_id": t["id"],
            "tenant_name": t["name"],
            "total_cases": case_count,
            "active_cases": active_cases,
            "status": t["status"]
        })
    
    return {
        "total_tenants": len(tenants),
        "total_cases": total_cases,
        "tenant_stats": tenant_stats,
        "system_health": {
            "status": "operational",
            "uptime": "99.9%"
        }
    }
