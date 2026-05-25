from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI(
    title="DDYs Compliance Platform",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Store db in app state for route access
app.state.db = db

# Security Middleware (order matters: first added = outermost)
from middleware.security_middleware import (
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    InputSanitizationMiddleware,
    RequestLoggingMiddleware,
)

app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(InputSanitizationMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    default_limit=int(os.environ.get('RATE_LIMIT_DEFAULT', '100').split('/')[0]),
    window_seconds=60,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import and include routers
from routes.auth import router as auth_router
from routes.tenants import router as tenants_router
from routes.cases import router as cases_router
from routes.documents import router as documents_router
from routes.screening import router as screening_router
from routes.risk import router as risk_router
from routes.waivers import router as waivers_router
from routes.approvals import router as approvals_router
from routes.audit import router as audit_router
from routes.mi import router as mi_router
from routes.policy import router as policy_router
from routes.admin import router as admin_router
from routes.customer_portal import router as customer_router
from routes.notifications import router as notifications_router
from routes.edr import router as edr_router
from routes.qa import router as qa_router
from routes.video_ident import router as video_ident_router
from routes.reminders import router as reminders_router
from routes.integrations import router as integrations_router
from routes.intake import router as intake_router

app.include_router(auth_router)
app.include_router(tenants_router)
app.include_router(cases_router)
app.include_router(documents_router)
app.include_router(screening_router)
app.include_router(risk_router)
app.include_router(waivers_router)
app.include_router(approvals_router)
app.include_router(audit_router)
app.include_router(mi_router)
app.include_router(policy_router)
app.include_router(admin_router)
app.include_router(customer_router)
app.include_router(notifications_router)
app.include_router(edr_router)
app.include_router(qa_router)
app.include_router(video_ident_router)
app.include_router(reminders_router)
app.include_router(integrations_router)
app.include_router(intake_router)


@app.get("/api")
async def root():
    return {"message": "DDYs Compliance Platform API", "version": "1.0.0"}


@app.get("/api/health")
async def health():
    jobs_status = await db.system_settings.find_one({"key": "periodic_jobs"}, {"_id": 0})
    return {
        "status": "healthy",
        "service": "ddys-compliance",
        "periodic_jobs": jobs_status or {"status": "not_started"}
    }


@app.on_event("startup")
async def startup_event():
    """Run migrations, then start periodic background jobs."""
    run_migrations_on_startup = os.environ.get("RUN_MIGRATIONS_ON_STARTUP", "true").lower() == "true"
    if run_migrations_on_startup:
        from migrations import run_migrations
        try:
            summary = await run_migrations(db)
            logger.info(
                "Migrations applied=%d skipped=%d total=%d",
                len(summary["applied"]),
                len(summary["skipped"]),
                summary["total"],
            )
        except Exception:
            logger.exception("Migration run failed; continuing startup")

    from services.periodic_jobs import start_periodic_jobs
    await start_periodic_jobs(db)
    logger.info("Periodic background jobs started")


@app.post("/api/jobs/run-now")
async def run_jobs_now_endpoint(request: Request):
    """Manually trigger all periodic jobs."""
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    if user.get("global_role") not in ["ADMIN"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    from services.periodic_jobs import run_jobs_now
    result = await run_jobs_now(db)
    return result


@app.get("/api/jobs/status")
async def get_jobs_status(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    status = await db.system_settings.find_one({"key": "periodic_jobs"}, {"_id": 0})
    config = await db.system_settings.find_one({"key": "job_intervals"}, {"_id": 0})
    defaults = {
        "nrd_rr_check": 24,
        "edr_deadlines": 24,
        "waiver_expiry": 24,
        "document_expiry": 72,
        "screening_refresh": 168,
    }
    intervals = config.get("intervals", defaults) if config else defaults
    return {
        **(status or {"key": "periodic_jobs", "status": "not_started"}),
        "intervals": intervals
    }


@app.get("/api/jobs/intervals")
async def get_job_intervals(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    config = await db.system_settings.find_one({"key": "job_intervals"}, {"_id": 0})
    defaults = {
        "nrd_rr_check": 24,
        "edr_deadlines": 24,
        "waiver_expiry": 24,
        "document_expiry": 72,
        "screening_refresh": 168,
    }
    return config.get("intervals", defaults) if config else defaults


@app.put("/api/jobs/intervals")
async def update_job_intervals(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    if user.get("global_role") not in ["ADMIN"]:
        from fastapi import HTTPException as HE
        raise HE(status_code=403, detail="Insufficient permissions")
    body = await request.json()
    
    intervals = {}
    for key in ["nrd_rr_check", "edr_deadlines", "waiver_expiry", "document_expiry", "screening_refresh"]:
        val = body.get(key)
        if val is not None:
            intervals[key] = max(24, int(val))  # minimum 24h
    
    await db.system_settings.update_one(
        {"key": "job_intervals"},
        {"$set": {"intervals": intervals, "updated_at": datetime.now(timezone.utc).isoformat()}},
        upsert=True
    )
    return {"message": "Intervals updated", "intervals": intervals}


@app.post("/api/seed")
async def seed_data():
    """Public seed endpoint for initial setup."""
    existing = await db.tenants.find_one({"name": "Demo Bank"}, {"_id": 0})
    if existing:
        return {"message": "Demo data already exists", "tenant_id": existing["id"]}
    from routes.seed import seed_all
    result = await seed_all(db)
    return result


# OSINT endpoint
@app.post("/api/osint/analyze")
async def osint_analyze(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    body = await request.json()
    from services.osint_service import run_osint_analysis
    result = await run_osint_analysis(db, body["case_id"], body["party_id"])
    return result


# Prompt Management
DEFAULT_OSINT_SYSTEM_PROMPT = """You are an OSINT and risk analysis expert for KYC/AML compliance.
Analyze the provided entity information and generate a risk intelligence report.
Return a JSON object with:
- risk_indicators: list of risk indicators found
- pep_likelihood: low/medium/high
- adverse_media_summary: summary of any adverse media concerns
- sanctions_risk: low/medium/high
- country_risk: risk level of associated countries
- recommendations: list of recommendations for the compliance team
- overall_risk_assessment: low/medium/high with rationale
Respond ONLY with valid JSON."""

DEFAULT_OSINT_USER_PROMPT = """Perform OSINT risk analysis for KYC compliance:

Entity Name: {name}
Entity Type: {party_type}
Nationality: {nationality}
Role in Case: {role_in_case}
Addresses: {addresses}
Identifiers: {identifiers}

Analyze this entity for:
1. PEP (Politically Exposed Person) indicators
2. Adverse media and reputation risks
3. Sanctions exposure
4. Country/jurisdiction risks
5. Overall risk profile

Return ONLY valid JSON."""

DEFAULT_DOCINT_SYSTEM_PROMPT = """You are a KYC document analysis expert performing OCR and compliance checks.
Analyze the document and return a JSON object:
{
  "classification": "id_passport|id_national|proof_of_address|utility_bill|tax_return|tax_report|police_report|registry_extract|annual_report|ownership_chart|attestation|bank_statement|other",
  "extracted_fields": {"document_date": "YYYY-MM-DD", "issuer": "", "name_on_doc": "", "address_on_doc": "", "expiry_date": ""},
  "ocr_text_preview": "first 200 chars of extracted text",
  "authenticity_score": 0.85,
  "tamper_signals": [],
  "mismatches": [],
  "wrong_document_type": false,
  "psi_detected": false,
  "decision": "auto_accept|auto_reject|needs_human",
  "rationale": "explanation"
}
IMPORTANT: Check if the document type matches what was expected. Flag wrong_document_type=true if mismatch.
Respond ONLY with valid JSON."""


@app.get("/api/prompts")
async def get_prompts(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    
    saved = await db.system_settings.find_one({"key": "prompts"}, {"_id": 0})
    return {
        "osint_system": saved.get("osint_system", DEFAULT_OSINT_SYSTEM_PROMPT) if saved else DEFAULT_OSINT_SYSTEM_PROMPT,
        "osint_user": saved.get("osint_user", DEFAULT_OSINT_USER_PROMPT) if saved else DEFAULT_OSINT_USER_PROMPT,
        "docint_system": saved.get("docint_system", DEFAULT_DOCINT_SYSTEM_PROMPT) if saved else DEFAULT_DOCINT_SYSTEM_PROMPT,
        "defaults": {
            "osint_system": DEFAULT_OSINT_SYSTEM_PROMPT,
            "osint_user": DEFAULT_OSINT_USER_PROMPT,
            "docint_system": DEFAULT_DOCINT_SYSTEM_PROMPT,
        }
    }


@app.put("/api/prompts")
async def update_prompts(request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    if user.get("global_role") not in ["ADMIN"]:
        from fastapi import HTTPException as HE
        raise HE(status_code=403, detail="Insufficient permissions")
    
    body = await request.json()
    updates = {"key": "prompts", "updated_at": datetime.now(timezone.utc).isoformat()}
    for key in ["osint_system", "osint_user", "docint_system"]:
        if key in body:
            updates[key] = body[key]
    
    await db.system_settings.update_one({"key": "prompts"}, {"$set": updates}, upsert=True)
    
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": "",
        "actor_user_id": user["user_id"],
        "actor_role": user.get("global_role", ""),
        "action_key": "prompts.updated",
        "entity_type": "system_settings",
        "entity_id": "prompts",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": None,
        "after_json": {k: v[:50] + "..." for k, v in updates.items() if k != "key"},
        "ip_address": request.client.host if request.client else "",
        "user_agent": request.headers.get("user-agent", "")
    })
    
    return {"message": "Prompts updated"}


# Document file viewer
@app.get("/api/documents/view/{doc_id}")
async def view_document_file(doc_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    from services.storage import backend_for
    from fastapi import HTTPException as HE
    from fastapi.responses import Response, RedirectResponse

    user = await get_current_user(request)
    doc = await db.documents.find_one({"id": doc_id}, {"_id": 0})
    if not doc:
        raise HE(status_code=404, detail="Document not found")

    storage_ref = doc.get("blob_path") or doc.get("storage_path")
    if not storage_ref:
        raise HE(status_code=404, detail="File not available")

    backend = backend_for(doc)
    tenant_id = doc.get("tenant_id", "")
    mime = doc.get("mime_type", "application/octet-stream")
    filename = doc.get("original_filename", "document")

    # For GCS, prefer a short-lived signed URL so we don't proxy bytes through
    # the API. Local files are streamed directly via FileResponse.
    if (doc.get("storage_type") or "local").lower() == "gcs":
        try:
            signed = await backend.generate_view_url(tenant_id, storage_ref, expiration_minutes=15)
            if signed:
                return RedirectResponse(url=signed, status_code=302)
        except Exception:
            logger.exception("Signed URL generation failed; falling back to proxy download")
        try:
            content, content_type = await backend.download(tenant_id, storage_ref)
        except PermissionError as exc:
            raise HE(status_code=403, detail=str(exc))
        except Exception:
            raise HE(status_code=404, detail="File not found in storage")
        return Response(
            content=content,
            media_type=content_type or mime,
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )

    # Local backend
    if not os.path.exists(storage_ref):
        raise HE(status_code=404, detail="File not found on disk")
    return FileResponse(storage_ref, media_type=mime, filename=filename)




# KYC Export endpoint
@app.post("/api/export/kyc/{case_id}")
async def export_kyc(case_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    user = await get_current_user(request)
    from services.export_service import export_kyc_file
    result = await export_kyc_file(db, case_id)
    return result


@app.get("/api/export/download/{export_id}")
async def download_export(export_id: str, request: Request):
    from middleware.auth_middleware import get_current_user
    from services.storage import backend_for
    from fastapi import HTTPException
    from fastapi.responses import Response, RedirectResponse

    user = await get_current_user(request)
    export_rec = await db.kyc_exports.find_one({"id": export_id}, {"_id": 0})
    if not export_rec:
        raise HTTPException(status_code=404, detail="Export not found")

    storage_ref = export_rec.get("blob_path") or export_rec.get("storage_path")
    tenant_id = export_rec.get("tenant_id", "")
    filename = export_rec["filename"]

    if (export_rec.get("storage_type") or "local").lower() == "gcs":
        backend = backend_for(export_rec)
        try:
            signed = await backend.generate_view_url(tenant_id, storage_ref, expiration_minutes=15)
            if signed:
                return RedirectResponse(url=signed, status_code=302)
        except Exception:
            logger.exception("Signed URL generation failed; falling back to proxy download")
        content, content_type = await backend.download(tenant_id, storage_ref)
        return Response(
            content=content,
            media_type=content_type or "application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return FileResponse(
        storage_ref,
        media_type="application/zip",
        filename=filename
    )


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
