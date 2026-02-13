from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from typing import Optional
import uuid
import hashlib
import os
import aiofiles
from datetime import datetime, timezone
from pathlib import Path

router = APIRouter(prefix="/api/documents", tags=["documents"])

UPLOAD_DIR = Path("/app/backend/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


def get_db(request: Request):
    return request.app.state.db


@router.post("/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    case_id: str = Form(...),
    party_id: str = Form(default=""),
    requirement_item_id: str = Form(default=""),
    doc_type: str = Form(default="other"),
    tenant_id: str = Form(...)
):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    # Read file and compute hash
    content = await file.read()
    file_hash = hashlib.sha256(content).hexdigest()
    
    # Save to disk (in production: Supabase Storage)
    file_ext = os.path.splitext(file.filename)[1] if file.filename else ".bin"
    storage_filename = f"{uuid.uuid4()}{file_ext}"
    storage_path = str(UPLOAD_DIR / storage_filename)
    
    async with aiofiles.open(storage_path, 'wb') as f:
        await f.write(content)
    
    doc = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "case_id": case_id,
        "party_id": party_id or None,
        "requirement_item_id": requirement_item_id or None,
        "doc_type": doc_type,
        "original_filename": file.filename,
        "storage_path": storage_path,
        "storage_filename": storage_filename,
        "file_hash": file_hash,
        "file_size": len(content),
        "mime_type": file.content_type,
        "issued_date": None,
        "expiry_date": None,
        "recency_valid_until": None,
        "language": None,
        "source": "customer_upload",
        "status": "uploaded",
        "ai_result_id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.documents.insert_one({**doc})
    
    # Update requirement status if linked
    if requirement_item_id:
        await db.requirement_items.update_one(
            {"id": requirement_item_id},
            {"$set": {"status": "submitted", "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
    
    # Trigger document intelligence (async in background)
    from services.document_intelligence import analyze_document
    try:
        ai_result = await analyze_document(db, doc, content)
        if ai_result:
            doc["ai_result_id"] = ai_result["id"]
            await db.documents.update_one({"id": doc["id"]}, {"$set": {"ai_result_id": ai_result["id"]}})
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Doc intelligence error: {e}")
    
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "document.uploaded",
        "entity_type": "document",
        "entity_id": doc["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": None,
        "after_json": {"id": doc["id"], "doc_type": doc_type, "filename": file.filename, "hash": file_hash},
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })
    
    return doc


@router.get("")
async def list_documents(request: Request, case_id: Optional[str] = None, tenant_id: Optional[str] = None):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    query = {}
    if case_id:
        query["case_id"] = case_id
    if tenant_id:
        query["tenant_id"] = tenant_id
    
    docs = await db.documents.find(query, {"_id": 0}).to_list(500)
    return docs


@router.get("/{doc_id}")
async def get_document(doc_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Get AI result if exists
    if doc.get("ai_result_id"):
        ai_result = await db.document_ai_results.find_one({"id": doc["ai_result_id"]}, {"_id": 0})
        doc["ai_result"] = ai_result
    
    return doc


@router.get("/{doc_id}/ai-result")
async def get_ai_result(doc_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    result = await db.document_ai_results.find_one({"document_id": doc_id}, {"_id": 0})
    if not result:
        raise HTTPException(status_code=404, detail="No AI result found")
    return result


@router.post("/{doc_id}/reanalyze")
async def reanalyze_document(doc_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    db = get_db(request)
    
    doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Read file content
    try:
        async with aiofiles.open(doc["storage_path"], 'rb') as f:
            content = await f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    from services.document_intelligence import analyze_document
    ai_result = await analyze_document(db, doc, content)
    return ai_result
