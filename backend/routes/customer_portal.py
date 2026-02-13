from fastapi import APIRouter, HTTPException, Request
from typing import Optional
import uuid
from datetime import datetime, timezone

router = APIRouter(prefix="/api/customer", tags=["customer_portal"])


def get_db(request: Request):
    return request.app.state.db


@router.get("/case")
async def get_customer_case(request: Request, case_ref: Optional[str] = None, tenant_id: Optional[str] = None):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    query = {"deleted": {"$ne": True}}
    if case_ref:
        query["case_ref"] = case_ref
    if tenant_id:
        query["tenant_id"] = tenant_id
    
    case = await db.cases.find_one(query, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Get requirements and their statuses (customer-facing view)
    requirements = await db.requirement_items.find({"case_id": case["id"]}, {"_id": 0}).to_list(500)
    documents = await db.documents.find({"case_id": case["id"]}, {"_id": 0}).to_list(500)
    parties = await db.parties.find({"case_id": case["id"], "deleted": {"$ne": True}}, {"_id": 0}).to_list(100)
    
    # Get questionnaire session
    session = await db.questionnaire_sessions.find_one({"case_id": case["id"]}, {"_id": 0})
    
    return {
        "case": case,
        "requirements": requirements,
        "documents": [{"id": d["id"], "doc_type": d["doc_type"], "status": d["status"], "original_filename": d.get("original_filename"), "requirement_item_id": d.get("requirement_item_id")} for d in documents],
        "parties": parties,
        "questionnaire": session
    }


@router.post("/questionnaire/start")
async def start_questionnaire(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()
    
    case_id = body.get("case_id")
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Check if session already exists
    existing = await db.questionnaire_sessions.find_one({"case_id": case_id}, {"_id": 0})
    if existing:
        return existing
    
    session = {
        "id": str(uuid.uuid4()),
        "tenant_id": case["tenant_id"],
        "case_id": case_id,
        "end_customer_user_id": user.get("user_id"),
        "token": str(uuid.uuid4()),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "current_step": "entity_type",
        "answers_json": {},
        "entity_type_determined": None,
        "derived_requirements_json": [],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.questionnaire_sessions.insert_one({**session})
    
    # Update case status
    await db.cases.update_one(
        {"id": case_id},
        {"$set": {"status": "customer_in_progress", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return session


@router.put("/questionnaire/{session_id}")
async def update_questionnaire(session_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()
    
    session = await db.questionnaire_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    updates = {}
    if "current_step" in body:
        updates["current_step"] = body["current_step"]
    if "answers_json" in body:
        # Merge answers
        current_answers = session.get("answers_json", {})
        current_answers.update(body["answers_json"])
        updates["answers_json"] = current_answers
    if "entity_type_determined" in body:
        updates["entity_type_determined"] = body["entity_type_determined"]
    
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.questionnaire_sessions.update_one({"id": session_id}, {"$set": updates})
    
    return await db.questionnaire_sessions.find_one({"id": session_id}, {"_id": 0})


@router.post("/questionnaire/{session_id}/complete")
async def complete_questionnaire(session_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    session = await db.questionnaire_sessions.find_one({"id": session_id}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    # Mark questionnaire complete
    await db.questionnaire_sessions.update_one(
        {"id": session_id},
        {"$set": {"completed_at": datetime.now(timezone.utc).isoformat(), "current_step": "completed"}}
    )
    
    # Create parties based on answers
    answers = session.get("answers_json", {})
    case_id = session["case_id"]
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    
    entity_type = session.get("entity_type_determined", "legal_entity")
    
    # Create main client party if not exists
    existing_parties = await db.parties.find({"case_id": case_id, "role_in_case": "client"}, {"_id": 0}).to_list(1)
    if not existing_parties:
        from routes.cases import _generate_requirements
        client_party = {
            "id": str(uuid.uuid4()),
            "tenant_id": case["tenant_id"],
            "case_id": case_id,
            "party_type": entity_type,
            "role_in_case": "client",
            "first_name": answers.get("first_name", ""),
            "last_name": answers.get("last_name", ""),
            "legal_name": answers.get("legal_name", answers.get("company_name", "")),
            "dob": answers.get("dob"),
            "nationality": answers.get("nationality", ""),
            "addresses_json": answers.get("address", {}),
            "identifiers_json": answers.get("identifiers", {}),
            "ownership_percent": None,
            "control_flags_json": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "deleted": False
        }
        await db.parties.insert_one({**client_party})
        await _generate_requirements(db, case, client_party)
    
    # Create UBO parties if provided
    ubos = answers.get("ubos", [])
    for ubo in ubos:
        ubo_party = {
            "id": str(uuid.uuid4()),
            "tenant_id": case["tenant_id"],
            "case_id": case_id,
            "party_type": "natural_person",
            "role_in_case": "ubo",
            "first_name": ubo.get("first_name", ""),
            "last_name": ubo.get("last_name", ""),
            "legal_name": "",
            "dob": ubo.get("dob"),
            "nationality": ubo.get("nationality", ""),
            "addresses_json": ubo.get("address", {}),
            "identifiers_json": {},
            "ownership_percent": ubo.get("ownership_percent"),
            "control_flags_json": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "deleted": False
        }
        await db.parties.insert_one({**ubo_party})
        from routes.cases import _generate_requirements
        await _generate_requirements(db, case, ubo_party)
    
    # Check if all documents are uploaded, if so mark as customer_submitted
    reqs = await db.requirement_items.find({"case_id": case_id}, {"_id": 0}).to_list(500)
    doc_reqs = [r for r in reqs if r["requirement_category"] not in ["sanctions", "pep", "adverse_media", "video_ident"]]
    all_submitted = all(r["status"] != "missing" for r in doc_reqs) if doc_reqs else False
    
    if all_submitted:
        await db.cases.update_one({"id": case_id}, {"$set": {"status": "customer_submitted", "updated_at": datetime.now(timezone.utc).isoformat()}})
    
    return {"message": "Questionnaire completed", "parties_created": len(ubos) + 1}


@router.post("/submit")
async def submit_case(request: Request):
    """Customer submits the case after completing all requirements."""
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    body = await request.json()
    
    case_id = body.get("case_id")
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    await db.cases.update_one(
        {"id": case_id},
        {"$set": {"status": "customer_submitted", "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    return {"message": "Case submitted successfully"}


@router.get("/notifications")
async def get_customer_notifications(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    notifs = await db.notifications.find(
        {"user_id": user["user_id"], "read": False},
        {"_id": 0}
    ).sort("created_at", -1).to_list(50)
    return notifs
