from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import uuid
from datetime import datetime, timezone, timedelta

router = APIRouter(prefix="/api/video-ident", tags=["video_ident"])


# Liveness/deepfake scoring requires a real biometric provider. Until one
# is integrated we return a NULL score and force the session to
# `needs_review` rather than fabricating a passing score with random().
# The previous random.uniform fallback created a coin-flip "biometric"
# check that would have falsely passed compliance audits.
PLACEHOLDER_LIVENESS_SCORE = None
PLACEHOLDER_DEEPFAKE_SCORE = None
# Customer / agent tokens for the join URL expire after this window. The
# old implementation generated tokens that lived forever, so a leaked URL
# was permanent PII exposure.
JOIN_TOKEN_TTL_HOURS = 48


def get_db(request: Request):
    return request.app.state.db


@router.post("/sessions")
async def create_session(request: Request):
    from middleware.auth_middleware import (
        get_current_user, has_permission, require_tenant_access
    )
    user = await get_current_user(request)
    if not has_permission(user, "can_video_ident"):
        raise HTTPException(status_code=403, detail="Missing permission: can_video_ident")
    db = get_db(request)
    body = await request.json()

    case_id = body.get("case_id")
    party_id = body.get("party_id")
    scheduled_at = body.get("scheduled_at")

    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    require_tenant_access(case["tenant_id"], user)

    party = await db.parties.find_one({"id": party_id, "case_id": case_id}, {"_id": 0})
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")

    customer_token = str(uuid.uuid4())
    agent_token = str(uuid.uuid4())
    room_id = str(uuid.uuid4())[:12]

    token_expires = (datetime.now(timezone.utc) + timedelta(hours=JOIN_TOKEN_TTL_HOURS)).isoformat()

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
        "tokens_expire_at": token_expires,
        "meeting_url": f"/video-room/{room_id}",
        "recording_storage_path": None,
        "liveness_score": None,
        "deepfake_score": None,
        "outcome": None,
        "notes": "",
        "status": "scheduled",
        "created_by": user["user_id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.video_ident_sessions.insert_one({**session})

    await db.requirement_items.update_one(
        {"case_id": case_id, "party_id": party_id, "requirement_category": "video_ident"},
        {"$set": {"status": "submitted", "notes": "Video ident scheduled", "updated_at": datetime.now(timezone.utc).isoformat()}}
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
    from middleware.auth_middleware import (
        get_current_user, has_permission, scope_tenant_query, require_tenant_access
    )
    user = await get_current_user(request)
    if not has_permission(user, "can_video_ident") and not has_permission(user, "can_manage_cases"):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
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

    sessions = await db.video_ident_sessions.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return sessions


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, request: Request):
    from middleware.auth_middleware import get_current_user, require_tenant_access
    user = await get_current_user(request)
    db = get_db(request)

    session = await db.video_ident_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    require_tenant_access(session.get("tenant_id", ""), user)
    return session


@router.post("/sessions/{session_id}/join")
async def join_session(session_id: str, request: Request):
    """Join a video ident session (staff side)."""
    from middleware.auth_middleware import (
        get_current_user, has_permission, require_tenant_access
    )
    user = await get_current_user(request)
    if not has_permission(user, "can_video_ident"):
        raise HTTPException(status_code=403, detail="Missing permission: can_video_ident")
    db = get_db(request)
    body = await request.json()

    session = await db.video_ident_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    require_tenant_access(session.get("tenant_id", ""), user)

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
    """Agent completes the video ident session with outcome.

    Liveness / deepfake scores are NOT accepted from the request body —
    those must be supplied by a server-side biometric provider. Until
    such a provider is wired up the session is forced into `needs_review`
    so a human reviews the recording. The previous code path filled the
    fields with `random.uniform()` which was effectively a coin flip and
    misrepresented compliance status.
    """
    from middleware.auth_middleware import (
        get_current_user, has_permission, require_tenant_access
    )
    user = await get_current_user(request)
    if not has_permission(user, "can_video_ident"):
        raise HTTPException(status_code=403, detail="Missing permission: can_video_ident")
    db = get_db(request)
    body = await request.json()

    session = await db.video_ident_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    require_tenant_access(session.get("tenant_id", ""), user)
    if session.get("agent_user_id") and session["agent_user_id"] != user["user_id"]:
        raise HTTPException(status_code=403, detail="Only the joined agent can complete this session")

    outcome = body.get("outcome")  # pass, fail, retry
    notes = body.get("notes", "")
    identity_confirmed = bool(body.get("identity_confirmed", False))
    document_match = bool(body.get("document_match", False))

    # TODO: Wire up a real biometric provider (e.g. DIDIT, Onfido). Until
    # then, ignore caller-supplied scores and write None so downstream
    # reporting reflects the absence of a real measurement.
    liveness_score = PLACEHOLDER_LIVENESS_SCORE
    deepfake_score = PLACEHOLDER_DEEPFAKE_SCORE

    # Without real biometrics we cannot mechanically pass / fail — we let
    # the staff outcome stand, and force "needs_review" on the requirement
    # for any non-pass case so a human signs off.
    liveness_pass = None
    deepfake_pass = None

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
        "biometric_provider": "none_configured",
        "status": "completed",
        "completed_by": user["user_id"],
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.video_ident_sessions.update_one({"id": session_id}, {"$set": update})

    # Without verified biometrics, a successful identity match still
    # routes through human review. Approve only on explicit pass + both
    # human checks affirmed.
    if outcome == "pass" and identity_confirmed and document_match:
        req_status = "needs_review"  # second-line human sign-off required
    elif outcome == "fail":
        req_status = "rejected"
    else:
        req_status = "needs_review"
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
            "identity_confirmed": identity_confirmed,
            "document_match": document_match,
            "biometric_provider": "none_configured",
        },
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })

    return await db.video_ident_sessions.find_one({"id": session_id}, {"_id": 0})


@router.get("/join/{token}")
async def join_by_token(token: str, request: Request):
    """Join video ident by customer or agent token (no auth required for customer).

    Tokens have a TTL; expired tokens are rejected so a leaked link does
    not grant indefinite access to party PII.
    """
    db = get_db(request)

    session = await db.video_ident_sessions.find_one(
        {"$or": [{"customer_token": token}, {"agent_token": token}]},
        {"_id": 0}
    )
    if not session:
        raise HTTPException(status_code=404, detail="Invalid session token")

    expires_raw = session.get("tokens_expire_at")
    if expires_raw:
        try:
            exp = datetime.fromisoformat(expires_raw)
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) > exp:
                raise HTTPException(status_code=410, detail="Token expired")
        except ValueError:
            raise HTTPException(status_code=410, detail="Token has invalid expiry")

    if session.get("status") == "completed":
        raise HTTPException(status_code=410, detail="Session already completed")

    role = "customer" if session.get("customer_token") == token else "agent"
    # Don't echo the *other* role's token back to the caller.
    safe_session = {
        k: v for k, v in session.items()
        if k not in ("customer_token", "agent_token")
    }
    return {"session": safe_session, "role": role, "room_id": session["room_id"]}
