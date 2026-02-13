import uuid
import os
import json
import zipfile
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

EXPORT_DIR = Path("/app/backend/exports")
EXPORT_DIR.mkdir(exist_ok=True)


async def export_kyc_file(db, case_id: str) -> dict:
    """Generate KYC File Export - complete evidence bundle."""
    
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    if not case:
        raise ValueError("Case not found")
    
    parties = await db.parties.find({"case_id": case_id, "deleted": {"$ne": True}}, {"_id": 0}).to_list(100)
    requirements = await db.requirement_items.find({"case_id": case_id}, {"_id": 0}).to_list(500)
    documents = await db.documents.find({"case_id": case_id}, {"_id": 0}).to_list(500)
    screening_runs = await db.screening_runs.find({"case_id": case_id}, {"_id": 0}).to_list(100)
    risk_assessments = await db.risk_assessments.find({"case_id": case_id}, {"_id": 0}).to_list(10)
    approval_tasks = await db.approval_tasks.find({"case_id": case_id}, {"_id": 0}).to_list(100)
    waivers = await db.waivers.find({"case_id": case_id}, {"_id": 0}).to_list(50)
    audit_logs = await db.audit_logs.find({"entity_id": case_id}, {"_id": 0}).sort("timestamp", 1).to_list(1000)
    
    # Get screening hits
    run_ids = [r["id"] for r in screening_runs]
    screening_hits = await db.screening_hits.find({"screening_run_id": {"$in": run_ids}}, {"_id": 0}).to_list(500)
    
    # Get AI results
    doc_ids = [d["id"] for d in documents]
    ai_results = await db.document_ai_results.find({"document_id": {"$in": doc_ids}}, {"_id": 0}).to_list(500)
    
    # Create ZIP file
    export_filename = f"KYC_Export_{case.get('case_ref', case_id)}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.zip"
    export_path = str(EXPORT_DIR / export_filename)
    
    with zipfile.ZipFile(export_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Summary JSON
        summary = {
            "export_date": datetime.now(timezone.utc).isoformat(),
            "case": case,
            "parties_count": len(parties),
            "documents_count": len(documents),
            "screening_runs_count": len(screening_runs),
            "risk_assessments_count": len(risk_assessments),
            "approval_tasks_count": len(approval_tasks),
            "waivers_count": len(waivers),
            "audit_entries_count": len(audit_logs)
        }
        zf.writestr("summary.json", json.dumps(summary, indent=2, default=str))
        
        # Case details
        zf.writestr("case/case.json", json.dumps(case, indent=2, default=str))
        
        # Parties
        for i, party in enumerate(parties):
            zf.writestr(f"parties/party_{i+1}_{party['id'][:8]}.json", json.dumps(party, indent=2, default=str))
        
        # Requirements
        zf.writestr("requirements/all_requirements.json", json.dumps(requirements, indent=2, default=str))
        
        # Documents metadata
        zf.writestr("documents/documents_index.json", json.dumps(documents, indent=2, default=str))
        
        # Add actual document files
        for doc in documents:
            storage_path = doc.get("storage_path")
            if storage_path and os.path.exists(storage_path):
                arcname = f"documents/files/{doc.get('original_filename', doc['id'])}"
                zf.write(storage_path, arcname)
        
        # AI Results
        zf.writestr("ai_analysis/results.json", json.dumps(ai_results, indent=2, default=str))
        
        # Screening
        zf.writestr("screening/runs.json", json.dumps(screening_runs, indent=2, default=str))
        zf.writestr("screening/hits.json", json.dumps(screening_hits, indent=2, default=str))
        
        # Risk Assessments
        zf.writestr("risk/assessments.json", json.dumps(risk_assessments, indent=2, default=str))
        
        # Approvals
        zf.writestr("approvals/tasks.json", json.dumps(approval_tasks, indent=2, default=str))
        
        # Waivers
        zf.writestr("waivers/waivers.json", json.dumps(waivers, indent=2, default=str))
        
        # Audit Trail
        zf.writestr("audit/audit_trail.json", json.dumps(audit_logs, indent=2, default=str))
        
        # README
        readme = f"""# KYC File Export
## Case: {case.get('case_ref', case_id)}
## Tenant: {case.get('tenant_id', 'unknown')}
## Export Date: {datetime.now(timezone.utc).isoformat()}

### Contents
- summary.json: High-level summary
- case/: Case details
- parties/: All relevant parties
- requirements/: KYC requirement items and their statuses
- documents/: Document metadata and files
- ai_analysis/: AI analysis results for documents
- screening/: Screening runs and hits
- risk/: Risk assessments
- approvals/: Approval tasks and decisions
- waivers/: Waiver requests and approvals
- audit/: Complete audit trail

### Compliance Note
This export contains all evidence, decisions, and audit trails
for regulatory review. All timestamps are in UTC.
"""
        zf.writestr("README.md", readme)
    
    # Store export reference
    export_record = {
        "id": str(uuid.uuid4()),
        "case_id": case_id,
        "tenant_id": case["tenant_id"],
        "filename": export_filename,
        "storage_path": export_path,
        "file_size": os.path.getsize(export_path),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.kyc_exports.insert_one({**export_record})
    
    return export_record
