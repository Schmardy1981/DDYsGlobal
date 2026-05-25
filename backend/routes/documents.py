from fastapi import APIRouter, HTTPException, Request, UploadFile, File, Form
from typing import Optional
import os
import uuid
from datetime import datetime, timezone

from services.storage import get_storage, backend_for

router = APIRouter(prefix="/api/documents", tags=["documents"])


# Reasonable upload caps. The GCS backend already enforces 20 MB; mirror it
# here so a 5 GB upload doesn't get fully read into memory before being
# rejected downstream.
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", 25 * 1024 * 1024))  # 25 MB

# Allowlist of MIME types accepted for KYC documents. Anything outside this
# list is rejected at the server boundary regardless of what the client
# claims. The `<input accept="">` attribute is cosmetic — this is the real
# gate.
ALLOWED_MIME_PREFIXES = (
    "image/",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument",
    "application/msword",
    "application/vnd.ms-excel",
    "text/plain",
    "text/csv",
)

EXECUTABLE_MAGIC_BYTES = (
    b"MZ",       # Windows PE
    b"\x7fELF",  # Linux ELF
    b"\xca\xfe\xba\xbe",  # Mach-O fat
    b"\xfe\xed\xfa",      # Mach-O thin (32/64)
)


def get_db(request: Request):
    return request.app.state.db


def _is_executable(content: bytes) -> bool:
    head = content[:8]
    for magic in EXECUTABLE_MAGIC_BYTES:
        if head.startswith(magic):
            return True
    return False


def _mime_allowed(mime: str) -> bool:
    if not mime:
        return False
    mime = mime.lower()
    return any(mime.startswith(p) for p in ALLOWED_MIME_PREFIXES)


@router.post("/upload")
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    case_id: str = Form(...),
    party_id: str = Form(default=""),
    requirement_item_id: str = Form(default=""),
    doc_type: str = Form(default="other"),
    tenant_id: str = Form(default=""),  # ignored if non-ADMIN — see below
):
    from middleware.auth_middleware import (
        get_current_user, require_tenant_access, require_customer_case_access
    )
    user = await get_current_user(request)
    db = get_db(request)

    # Trust the case_id (referenced object), not the tenant_id form field.
    # We derive tenant_id from the case record so callers can't smuggle in
    # a foreign tenant_id.
    case = await db.cases.find_one({"id": case_id, "deleted": {"$ne": True}}, {"_id": 0})
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    resolved_tenant_id = case["tenant_id"]

    # Authorization differs by role:
    #  - Staff (ADMIN/CASE_MANAGER/BANK_USER/VIDEO_AGENT): tenant access.
    #  - END_CUSTOMER: must own the case.
    if user.get("global_role") == "END_CUSTOMER":
        require_customer_case_access(user, case)
    else:
        require_tenant_access(resolved_tenant_id, user)

    if requirement_item_id:
        req = await db.requirement_items.find_one(
            {"id": requirement_item_id, "case_id": case_id}, {"_id": 0, "id": 1}
        )
        if not req:
            raise HTTPException(status_code=400, detail="requirement_item_id does not belong to this case")
    if party_id:
        party = await db.parties.find_one(
            {"id": party_id, "case_id": case_id}, {"_id": 0, "id": 1}
        )
        if not party:
            raise HTTPException(status_code=400, detail="party_id does not belong to this case")

    # Read with a hard cap so a hostile client cannot OOM the worker.
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {MAX_UPLOAD_BYTES // (1024*1024)} MB",
        )

    # MIME allowlist + executable sniff. Block files that *claim* to be a
    # PDF but start with an MZ header, etc.
    if not _mime_allowed(file.content_type or ""):
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {file.content_type}")
    if _is_executable(content):
        raise HTTPException(status_code=415, detail="Executable files are not permitted")

    storage = get_storage()
    try:
        upload_meta = await storage.upload(
            tenant_id=resolved_tenant_id,
            case_id=case_id,
            filename=file.filename or "upload.bin",
            content=content,
            content_type=file.content_type,
            metadata={
                "doc_type": doc_type,
                "party_id": party_id or "",
                "requirement_item_id": requirement_item_id or "",
                "uploaded_by": user["user_id"],
            },
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    doc = {
        "id": str(uuid.uuid4()),
        "tenant_id": resolved_tenant_id,
        "case_id": case_id,
        "party_id": party_id or None,
        "requirement_item_id": requirement_item_id or None,
        "doc_type": doc_type,
        "original_filename": upload_meta["original_filename"],
        "storage_type": upload_meta["storage_type"],
        "storage_path": upload_meta["storage_path"],
        "blob_path": upload_meta.get("blob_path"),
        "bucket": upload_meta.get("bucket"),
        "file_hash": upload_meta["file_hash"],
        "file_size": upload_meta["file_size"],
        "mime_type": upload_meta["content_type"],
        "issued_date": None,
        "expiry_date": None,
        "recency_valid_until": None,
        "language": None,
        "source": "customer_upload" if user.get("global_role") == "END_CUSTOMER" else "staff_upload",
        "status": "uploaded",
        "ai_result_id": None,
        "uploaded_by": user["user_id"],
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
        "tenant_id": resolved_tenant_id,
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "document.uploaded",
        "entity_type": "document",
        "entity_id": doc["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": None,
        "after_json": {
            "id": doc["id"],
            "doc_type": doc_type,
            "filename": doc["original_filename"],
            "hash": doc["file_hash"],
            "storage_type": doc["storage_type"],
        },
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })

    return doc


@router.get("")
async def list_documents(request: Request, case_id: Optional[str] = None, tenant_id: Optional[str] = None):
    from middleware.auth_middleware import (
        get_current_user, scope_tenant_query, require_customer_case_access,
        require_tenant_access,
    )
    user = await get_current_user(request)
    db = get_db(request)

    role = user.get("global_role")

    if role == "END_CUSTOMER":
        # Customers may only see documents for cases they own.
        token_case_id = user.get("case_id")
        if case_id and token_case_id and case_id != token_case_id:
            raise HTTPException(status_code=403, detail="Not your case")
        target_case_id = case_id or token_case_id
        if not target_case_id:
            return []
        case = await db.cases.find_one({"id": target_case_id}, {"_id": 0})
        require_customer_case_access(user, case)
        docs = await db.documents.find({"case_id": target_case_id}, {"_id": 0}).to_list(500)
        return docs

    query = {}
    if case_id:
        case = await db.cases.find_one({"id": case_id}, {"_id": 0, "tenant_id": 1})
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        require_tenant_access(case["tenant_id"], user)
        query["case_id"] = case_id
    else:
        query = scope_tenant_query(user, query, tenant_id)

    docs = await db.documents.find(query, {"_id": 0}).to_list(500)
    return docs


@router.get("/{doc_id}")
async def get_document(doc_id: str, request: Request):
    from middleware.auth_middleware import (
        get_current_user, require_tenant_access, require_customer_case_access
    )
    user = await get_current_user(request)
    db = get_db(request)

    doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    role = user.get("global_role")
    if role == "END_CUSTOMER":
        case = await db.cases.find_one({"id": doc["case_id"]}, {"_id": 0})
        require_customer_case_access(user, case)
    else:
        require_tenant_access(doc.get("tenant_id", ""), user)

    if doc.get("ai_result_id"):
        ai_result = await db.document_ai_results.find_one({"id": doc["ai_result_id"]}, {"_id": 0})
        doc["ai_result"] = ai_result

    return doc


@router.get("/{doc_id}/ai-result")
async def get_ai_result(doc_id: str, request: Request):
    from middleware.auth_middleware import (
        get_current_user, require_tenant_access, require_customer_case_access
    )
    user = await get_current_user(request)
    db = get_db(request)

    doc = await db.documents.find_one({"id": doc_id}, {"_id": 0, "tenant_id": 1, "case_id": 1})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    role = user.get("global_role")
    if role == "END_CUSTOMER":
        case = await db.cases.find_one({"id": doc["case_id"]}, {"_id": 0})
        require_customer_case_access(user, case)
    else:
        require_tenant_access(doc.get("tenant_id", ""), user)

    result = await db.document_ai_results.find_one({"document_id": doc_id}, {"_id": 0})
    if not result:
        raise HTTPException(status_code=404, detail="No AI result found")
    return result


@router.post("/{doc_id}/reanalyze")
async def reanalyze_document(doc_id: str, request: Request):
    from middleware.auth_middleware import (
        get_current_user, require_tenant_access, has_permission
    )
    user = await get_current_user(request)
    if not has_permission(user, "can_manage_cases"):
        raise HTTPException(status_code=403, detail="Missing permission: can_manage_cases")
    db = get_db(request)

    doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    require_tenant_access(doc.get("tenant_id", ""), user)

    backend = backend_for(doc)
    storage_ref = doc.get("blob_path") or doc.get("storage_path")
    if not storage_ref:
        raise HTTPException(status_code=404, detail="File reference missing")
    try:
        content, _ = await backend.download(doc.get("tenant_id", ""), storage_ref)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found on disk")
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    from services.document_intelligence import analyze_document
    ai_result = await analyze_document(db, doc, content)
    return ai_result
