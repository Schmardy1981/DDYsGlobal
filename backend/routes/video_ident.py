from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import uuid
import random
from datetime import datetime, timezone

router = APIRouter(prefix="/api/video-ident", tags=["video_ident"])


def get_db(request: Request):
    return request.app.state.db


@router.post("/sessions")
async def create_session(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()

    case_id = body.get("case_id")
    party_id = body.get("party_id")
    scheduled_at = body.get("scheduled_at")

    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    party = await db.parties.find_one({"id": party_id}, {"_id": 0})
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")

    # Generate unique tokens for customer and agent
    customer_token = str(uuid.uuid4())
    agent_token = str(uuid.uuid4())
    room_id = str(uuid.uuid4())[:12]

    session = {
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "case_id": case_id,
        "party_id": party_id,
        "party_name": party.get("legal_name") or f"{party.get('first_name', '')} {party.get('last_name', '')}".strip(),
        "scheduled_at": scheduled_at,
        "started_at": None,
        "ended_at": None,
        "agent_user_id": None,
        "provider": "internal_webrtc",
        "room_id": room_id,
        "customer_token": customer_token,
        "agent_token": agent_token,
        "meeting_url": f"/video-room/{room_id}",
        "recording_storage_path": None,
        "liveness_score": None,
        "deepfake_score": None,
        "outcome": None,
        "notes": "",
        "status": "scheduled",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.video_ident_sessions.insert_one({**session})

    # Update requirement
    await db.requirement_items.update_one(
        {"case_id": case_id, "party_id": party_id, "requirement_category": "video_ident"},
        {"$set": {"status": "submitted", "notes": f"Video ident scheduled", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "video_ident.session_created",
        "entity_type": "video_ident_session",
        "entity_id": session["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": None,
        "after_json": {"party": party_id, "scheduled_at": scheduled_at},
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })

    return session


@router.get("/sessions")
async def list_sessions(request: Request, case_id: Optional[str] = None, tenant_id: Optional[str] = None, status: Optional[str] = None):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)

    query = {}
    if case_id:
        query["case_id"] = case_id
    if tenant_id:
        query["tenant_id"] = tenant_id
    if status:
        query["status"] = status

    sessions = await db.video_ident_sessions.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return sessions


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)

    session = await db.video_ident_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/sessions/{session_id}/join")
async def join_session(session_id: str, request: Request):
    """Join a video ident session (either as agent or customer via token)."""
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()

    session = await db.video_ident_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    role = body.get("role", "agent")

    if role == "agent":
        await db.video_ident_sessions.update_one(
            {"id": session_id},
            {"$set": {
                "agent_user_id": user["user_id"],
                "started_at": datetime.now(timezone.utc).isoformat() if not session.get("started_at") else session["started_at"],
                "status": "in_progress",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )

    return {
        "session": await db.video_ident_sessions.find_one({"id": session_id}, {"_id": 0}),
        "role": role,
        "room_id": session["room_id"]
    }


@router.post("/sessions/{session_id}/complete")
async def complete_session(session_id: str, request: Request):
    """Agent completes the video ident session with outcome."""
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()

    session = await db.video_ident_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    outcome = body.get("outcome")  # pass, fail, retry
    notes = body.get("notes", "")
    identity_confirmed = body.get("identity_confirmed", False)
    document_match = body.get("document_match", False)

    # Mock liveness/deepfake scores
    liveness_score = body.get("liveness_score", round(random.uniform(0.7, 0.99), 2))
    deepfake_score = body.get("deepfake_score", round(random.uniform(0.01, 0.15), 2))

    # Get policy thresholds
    liveness_threshold = 0.70
    deepfake_threshold = 0.30

    rules = await db.policy_rules.find(
        {"tenant_id": session["tenant_id"], "enabled": True},
        {"_id": 0}
    ).to_list(100)
    for rule in rules:
        if rule["rule_key"] == "liveness_threshold":
            liveness_threshold = rule["rule_value_json"].get("min_score", 0.70)
        if rule["rule_key"] == "deepfake_threshold":
            deepfake_threshold = rule["rule_value_json"].get("max_score", 0.30)

    # Check thresholds
    liveness_pass = liveness_score >= liveness_threshold
    deepfake_pass = deepfake_score <= deepfake_threshold

    # Force escalation on suspected deepfake
    if not deepfake_pass:
        outcome = "fail"
        notes += " [SYSTEM: Deepfake score exceeds threshold. Escalated to MLRO.]"
        # Create MLRO escalation
        case = await db.cases.find_one({"id": session["case_id"]}, {"_id": 0})
        if case:
            await db.approval_tasks.insert_one({
                "id": str(uuid.uuid4()),
                "tenant_id": session["tenant_id"],
                "case_id": session["case_id"],
                "task_type": "deepfake_escalation",
                "status": "pending",
                "assigned_to": case.get("assigned_mlro_id"),
                "due_at": None,
                "completed_at": None,
                "decision": None,
                "decision_notes": None,
                "metadata_json": {
                    "session_id": session_id,
                    "deepfake_score": deepfake_score,
                    "liveness_score": liveness_score
                },
                "created_at": datetime.now(timezone.utc).isoformat()
            })

    update = {
        "ended_at": datetime.now(timezone.utc).isoformat(),
        "liveness_score": liveness_score,
        "deepfake_score": deepfake_score,
        "outcome": outcome,
        "notes": notes,
        "identity_confirmed": identity_confirmed,
        "document_match": document_match,
        "liveness_pass": liveness_pass,
        "deepfake_pass": deepfake_pass,
        "status": "completed",
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.video_ident_sessions.update_one({"id": session_id}, {"$set": update})

    # Update requirement
    req_status = "approved" if outcome == "pass" else "rejected" if outcome == "fail" else "needs_review"
    await db.requirement_items.update_one(
        {"case_id": session["case_id"], "party_id": session["party_id"], "requirement_category": "video_ident"},
        {"$set": {"status": req_status, "notes": f"Video ident: {outcome}", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": session["tenant_id"],
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": f"video_ident.completed.{outcome}",
        "entity_type": "video_ident_session",
        "entity_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": None,
        "after_json": {
            "outcome": outcome,
            "liveness_score": liveness_score,
            "deepfake_score": deepfake_score,
            "liveness_pass": liveness_pass,
            "deepfake_pass": deepfake_pass
        },
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })

    return await db.video_ident_sessions.find_one({"id": session_id}, {"_id": 0})


@router.get("/join/{token}")
async def join_by_token(token: str, request: Request):
    """Join video ident by customer or agent token (no auth required for customer)."""
    db = get_db(request)

    session = await db.video_ident_sessions.find_one(
        {"$or": [{"customer_token": token}, {"agent_token": token}]},
        {"_id": 0}
    )
    if not session:
        raise HTTPException(status_code=404, detail="Invalid session token")

    role = "customer" if session.get("customer_token") == token else "agent"
    return {"session": session, "role": role, "room_id": session["room_id"]}
