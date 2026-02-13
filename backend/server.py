from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app
app = FastAPI(title="DDYs Compliance Platform", version="1.0.0")

# Store db in app state for route access
app.state.db = db

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


@app.get("/api")
async def root():
    return {"message": "DDYs Compliance Platform API", "version": "1.0.0"}


@app.get("/api/health")
async def health():
    return {"status": "healthy", "service": "ddys-compliance"}


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
    user = await get_current_user(request)
    export_rec = await db.kyc_exports.find_one({"id": export_id}, {"_id": 0})
    if not export_rec:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Export not found")
    return FileResponse(
        export_rec["storage_path"],
        media_type="application/zip",
        filename=export_rec["filename"]
    )


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
