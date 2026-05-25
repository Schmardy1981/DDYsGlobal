from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import uuid
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/api/screening", tags=["screening"])


def get_db(request: Request):
    return request.app.state.db


@router.post("/run")
async def run_screening(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()
    
    case_id = body.get("case_id")
    run_type = body.get("run_type", "sanctions")  # sanctions, pep, adverse_media
    
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Get all parties - only fields needed for screening
    parties = await db.parties.find({"case_id": case_id, "deleted": {"$ne": True}}, {
        "_id": 0, "id": 1, "first_name": 1, "last_name": 1, "legal_name": 1,
        "party_type": 1, "nationality": 1, "role_in_case": 1, "tenant_id": 1
    }).to_list(100)
    
    from services.providers import get_screening_provider
    provider = await get_screening_provider(db)

    screening_run = {
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "case_id": case_id,
        "run_type": run_type,
        "provider": provider.name,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "status": "running",
        "parameters_json": {"parties_count": len(parties), "run_type": run_type},
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.screening_runs.insert_one({**screening_run})

    from services.screening_service import screen_party
    hits = []
    for party in parties:
        party_hits = await screen_party(db, screening_run, party, run_type)
        hits.extend(party_hits)
    
    # Update run status
    await db.screening_runs.update_one(
        {"id": screening_run["id"]},
        {"$set": {
            "status": "completed",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "parameters_json": {**screening_run["parameters_json"], "hits_count": len(hits)}
        }}
    )
    
    # Update requirement items
    for party in parties:
        req_key = f"{run_type}_screening" if run_type != "adverse_media" else "adverse_media"
        req = await db.requirement_items.find_one(
            {"case_id": case_id, "party_id": party["id"], "requirement_category": run_type},
            {"_id": 0}
        )
        if req:
            party_hits = [h for h in hits if h["party_id"] == party["id"]]
            new_status = "needs_review" if party_hits else "auto_passed"
            await db.requirement_items.update_one(
                {"id": req["id"]},
                {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}}
            )
    
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": f"screening.{run_type}.run",
        "entity_type": "screening_run",
        "entity_id": screening_run["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": None,
        "after_json": {"hits_count": len(hits), "parties_screened": len(parties)},
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })
    
    screening_run["hits"] = hits
    return screening_run


@router.get("/hits")
async def list_hits(request: Request, tenant_id: Optional[str] = None, disposition: Optional[str] = None):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    query = {}
    if tenant_id:
        # Get screening runs for tenant
        runs = await db.screening_runs.find({"tenant_id": tenant_id}, {"_id": 0, "id": 1}).to_list(1000)
        run_ids = [r["id"] for r in runs]
        query["screening_run_id"] = {"$in": run_ids}
    if disposition:
        query["disposition"] = disposition
    else:
        query["disposition"] = {"$in": ["open", "escalated"]}
    
    hits = await db.screening_hits.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return hits


@router.put("/hits/{hit_id}")
async def dispose_hit(hit_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()
    
    hit = await db.screening_hits.find_one({"id": hit_id}, {"_id": 0})
    if not hit:
        raise HTTPException(status_code=404, detail="Hit not found")
    
    disposition = body.get("disposition")  # false_positive, true_match, escalated
    notes = body.get("notes", "")
    
    if disposition not in ["false_positive", "true_match", "escalated"]:
        raise HTTPException(status_code=400, detail="Invalid disposition")
    
    before = dict(hit)
    await db.screening_hits.update_one(
        {"id": hit_id},
        {"$set": {
            "disposition": disposition,
            "decided_by": user["user_id"],
            "decided_at": datetime.now(timezone.utc).isoformat(),
            "notes": notes
        }}
    )
    
    # If true match, may need to trigger EDR
    if disposition == "true_match":
        run = await db.screening_runs.find_one({"id": hit["screening_run_id"]}, {"_id": 0})
        if run:
            await db.edr_alerts.insert_one({
                "id": str(uuid.uuid4()),
                "tenant_id": run["tenant_id"],
                "case_id": run["case_id"],
                "trigger_event_type": f"screening_{run.get('run_type', 'unknown')}_true_match",
                "trigger_event_date": datetime.now(timezone.utc).isoformat(),
                "detected_by": "system",
                "alert_generated_at": datetime.now(timezone.utc).isoformat(),
                "alert_review_due_at": (datetime.now(timezone.utc) + timedelta(days=28)).isoformat(),
                "completion_due_at": (datetime.now(timezone.utc) + timedelta(days=90)).isoformat(),
                "status": "open",
                "escalation_to_mlro_at": None,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
    
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": hit.get("tenant_id", ""),
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": f"screening_hit.disposed.{disposition}",
        "entity_type": "screening_hit",
        "entity_id": hit_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": before,
        "after_json": {"disposition": disposition, "notes": notes},
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })
    
    after = await db.screening_hits.find_one({"id": hit_id}, {"_id": 0})
    return after


@router.get("/runs")
async def list_runs(request: Request, case_id: Optional[str] = None, tenant_id: Optional[str] = None):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    query = {}
    if case_id:
        query["case_id"] = case_id
    if tenant_id:
        query["tenant_id"] = tenant_id
    
    runs = await db.screening_runs.find(query, {"_id": 0}).sort("created_at", -1).to_list(200)
    return runs


@router.post("/osint")
async def run_osint_screening(request: Request):
    """Run OSINT screening for a specific party in a case."""
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()

    case_id = body.get("case_id")
    party_id = body.get("party_id")

    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    party = await db.parties.find_one({"id": party_id}, {"_id": 0})
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")

    # Create screening run record
    run = {
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "case_id": case_id,
        "run_type": "osint",
        "provider": "llm_osint",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "status": "running",
        "parameters_json": {"party_id": party_id, "party_name": party.get("legal_name") or f"{party.get('first_name','')} {party.get('last_name','')}"},
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.screening_runs.insert_one({**run})

    # Run OSINT analysis
    from services.osint_service import run_osint_analysis
    try:
        result = await run_osint_analysis(db, case_id, party_id)

        # Update run
        await db.screening_runs.update_one(
            {"id": run["id"]},
            {"$set": {
                "status": "completed",
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "parameters_json": {
                    **run["parameters_json"],
                    "overall_risk": result.get("result_json", {}).get("overall_risk_assessment", "unknown"),
                    "osint_result_id": result.get("id")
                }
            }}
        )

        return {"run": run, "result": result}
    except Exception as e:
        await db.screening_runs.update_one(
            {"id": run["id"]},
            {"$set": {"status": "error", "finished_at": datetime.now(timezone.utc).isoformat()}}
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/osint-results")
async def list_osint_results(request: Request, case_id: Optional[str] = None, party_id: Optional[str] = None):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)

    query = {}
    if case_id:
        query["case_id"] = case_id
    if party_id:
        query["party_id"] = party_id

    results = await db.osint_results.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return results

