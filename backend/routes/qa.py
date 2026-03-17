from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import uuid
import random
from datetime import datetime, timezone

router = APIRouter(prefix="/api/qa", tags=["qa"])


def get_db(request: Request):
    return request.app.state.db


@router.get("/reviews")
async def list_qa_reviews(request: Request, tenant_id: Optional[str] = None, qa_type: Optional[str] = None):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)

    query = {}
    if tenant_id:
        query["tenant_id"] = tenant_id
    if qa_type:
        query["qa_type"] = qa_type

    reviews = await db.qa_reviews.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return reviews


@router.post("/reviews")
async def create_qa_review(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()

    review = {
        "id": str(uuid.uuid4()),
        "tenant_id": body.get("tenant_id"),
        "case_id": body.get("case_id"),
        "qa_type": body.get("qa_type", "first_line"),
        "sampled_at": datetime.now(timezone.utc).isoformat(),
        "reviewer_id": user["user_id"],
        "reviewer_name": user.get("name", ""),
        "findings_json": body.get("findings", []),
        "severity": body.get("severity", "low"),
        "remediation_required": body.get("remediation_required", False),
        "remediation_notes": body.get("remediation_notes", ""),
        "remediation_due_date": body.get("remediation_due_date"),
        "status": "open",
        "closed_at": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.qa_reviews.insert_one({**review})

    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": body.get("tenant_id", ""),
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "qa_review.created",
        "entity_type": "qa_review",
        "entity_id": review["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": None,
        "after_json": review,
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })

    return review


@router.put("/reviews/{review_id}")
async def update_qa_review(review_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()

    review = await db.qa_reviews.find_one({"id": review_id}, {"_id": 0})
    if not review:
        raise HTTPException(status_code=404, detail="QA review not found")

    updates = {}
    for key in ["findings_json", "severity", "remediation_required", "remediation_notes", "remediation_due_date", "status"]:
        if key in body:
            updates[key] = body[key]

    if body.get("status") == "closed":
        updates["closed_at"] = datetime.now(timezone.utc).isoformat()

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.qa_reviews.update_one({"id": review_id}, {"$set": updates})

    return await db.qa_reviews.find_one({"id": review_id}, {"_id": 0})


@router.post("/sample")
async def generate_qa_sample(request: Request):
    """Generate a QA sample from completed cases."""
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()

    tenant_id = body.get("tenant_id")
    sample_pct = body.get("sample_percent", 5)
    qa_type = body.get("qa_type", "first_line")

    # Get completed cases from last 30 days
    from datetime import timedelta
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    query = {
        "status": "completed",
        "updated_at": {"$gte": cutoff},
        "deleted": {"$ne": True}
    }
    if tenant_id:
        query["tenant_id"] = tenant_id

    completed = await db.cases.find(query, {"_id": 0}).to_list(5000)

    if not completed:
        return {"message": "No completed cases to sample", "sample": []}

    # Risk-weighted sampling: high-risk cases have 3x weight, medium 2x
    weighted_pool = []
    for c in completed:
        risk = c.get("risk_rating", "low")
        weight = 3 if risk == "high" else 2 if risk == "medium" else 1
        weighted_pool.extend([c] * weight)

    sample_size = max(1, int(len(completed) * sample_pct / 100))
    sample_size = min(sample_size, len(completed))

    # Random sample from weighted pool, deduplicated
    sampled = []
    sampled_ids = set()
    random.shuffle(weighted_pool)
    for c in weighted_pool:
        if c["id"] not in sampled_ids and len(sampled) < sample_size:
            sampled.append(c)
            sampled_ids.add(c["id"])

    # Auto-create QA reviews for each sampled case
    created_reviews = []
    for c in sampled:
        # Check if QA review already exists this month
        existing = await db.qa_reviews.find_one({
            "case_id": c["id"],
            "qa_type": qa_type,
            "sampled_at": {"$gte": cutoff}
        }, {"_id": 0})
        if existing:
            continue

        review = {
            "id": str(uuid.uuid4()),
            "tenant_id": c["tenant_id"],
            "case_id": c["id"],
            "case_ref": c.get("case_ref", ""),
            "risk_rating": c.get("risk_rating"),
            "qa_type": qa_type,
            "sampled_at": datetime.now(timezone.utc).isoformat(),
            "reviewer_id": None,
            "reviewer_name": "",
            "findings_json": [],
            "severity": None,
            "remediation_required": False,
            "remediation_notes": "",
            "remediation_due_date": None,
            "status": "pending_review",
            "closed_at": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.qa_reviews.insert_one({**review})
        created_reviews.append(review)

    return {
        "message": f"Generated {len(created_reviews)} QA samples from {len(completed)} completed cases",
        "sample_percent": sample_pct,
        "total_completed": len(completed),
        "samples_created": len(created_reviews),
        "reviews": created_reviews
    }


@router.get("/governance-pack")
async def get_governance_pack(request: Request, tenant_id: Optional[str] = None):
    """Generate monthly QA governance council pack data."""
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)

    from datetime import timedelta
    now = datetime.now(timezone.utc)
    month_ago = (now - timedelta(days=30)).isoformat()

    query = {}
    if tenant_id:
        query["tenant_id"] = tenant_id

    # All reviews this month
    reviews = await db.qa_reviews.find(
        {**query, "created_at": {"$gte": month_ago}},
        {"_id": 0}
    ).to_list(1000)

    total = len(reviews)
    by_type = {}
    by_severity = {}
    by_status = {}
    remediation_required_count = 0
    findings_summary = []

    for r in reviews:
        qt = r.get("qa_type", "unknown")
        by_type[qt] = by_type.get(qt, 0) + 1

        sev = r.get("severity") or "unrated"
        by_severity[sev] = by_severity.get(sev, 0) + 1

        st = r.get("status", "unknown")
        by_status[st] = by_status.get(st, 0) + 1

        if r.get("remediation_required"):
            remediation_required_count += 1

        for f in r.get("findings_json", []):
            findings_summary.append({
                "review_id": r["id"],
                "case_id": r.get("case_id"),
                "finding": f if isinstance(f, str) else f.get("description", str(f)),
                "severity": r.get("severity")
            })

    # Trends (compare with prior month)
    two_months_ago = (now - timedelta(days=60)).isoformat()
    prior_reviews = await db.qa_reviews.find(
        {**query, "created_at": {"$gte": two_months_ago, "$lt": month_ago}},
        {"_id": 0}
    ).to_list(1000)

    pack = {
        "period": f"{month_ago[:10]} to {now.isoformat()[:10]}",
        "generated_at": now.isoformat(),
        "summary": {
            "total_reviews": total,
            "by_type": by_type,
            "by_severity": by_severity,
            "by_status": by_status,
            "remediation_required": remediation_required_count
        },
        "trends": {
            "current_month_reviews": total,
            "prior_month_reviews": len(prior_reviews),
            "change": total - len(prior_reviews)
        },
        "findings": findings_summary,
        "remediation_tracker": [
            r for r in reviews if r.get("remediation_required") and r.get("status") != "closed"
        ]
    }

    return pack


@router.get("/settings")
async def get_qa_settings(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)

    settings = await db.system_settings.find_one({"key": "qa_settings"}, {"_id": 0})
    if not settings:
        settings = {
            "key": "qa_settings",
            "sample_percent": 5,
            "sample_frequency": "monthly",
            "risk_weighting": {"high": 3, "medium": 2, "low": 1},
            "first_line_enabled": True,
            "second_line_enabled": True
        }
    return settings


@router.put("/settings")
async def update_qa_settings(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    if user.get("global_role") not in ["ADMIN", "CASE_MANAGER"]:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    db = get_db(request)
    body = await request.json()

    updates = {}
    for key in ["sample_percent", "sample_frequency", "risk_weighting", "first_line_enabled", "second_line_enabled"]:
        if key in body:
            updates[key] = body[key]

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.system_settings.update_one(
        {"key": "qa_settings"},
        {"$set": updates},
        upsert=True
    )
    return {"message": "QA settings updated"}
