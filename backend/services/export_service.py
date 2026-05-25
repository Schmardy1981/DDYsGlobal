import io
import json
import logging
import uuid
import zipfile
from datetime import datetime, timezone

from services.storage import backend_for, get_storage

logger = logging.getLogger(__name__)


async def export_kyc_file(db, case_id: str) -> dict:
    """Generate KYC File Export - complete evidence bundle.

    Builds a ZIP in memory and writes it through the configured storage
    backend (local FS or GCS). Document files are fetched from whichever
    backend they were originally written to.
    """

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

    run_ids = [r["id"] for r in screening_runs]
    screening_hits = await db.screening_hits.find({"screening_run_id": {"$in": run_ids}}, {"_id": 0}).to_list(500)

    doc_ids = [d["id"] for d in documents]
    ai_results = await db.document_ai_results.find({"document_id": {"$in": doc_ids}}, {"_id": 0}).to_list(500)

    tenant_id = case["tenant_id"]
    export_filename = (
        f"KYC_Export_{case.get('case_ref', case_id)}_"
        f"{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.zip"
    )

    # Build the ZIP in memory so we can hand it to either backend uniformly.
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        summary = {
            "export_date": datetime.now(timezone.utc).isoformat(),
            "case": case,
            "parties_count": len(parties),
            "documents_count": len(documents),
            "screening_runs_count": len(screening_runs),
            "risk_assessments_count": len(risk_assessments),
            "approval_tasks_count": len(approval_tasks),
            "waivers_count": len(waivers),
            "audit_entries_count": len(audit_logs),
        }
        zf.writestr("summary.json", json.dumps(summary, indent=2, default=str))
        zf.writestr("case/case.json", json.dumps(case, indent=2, default=str))

        for i, party in enumerate(parties):
            zf.writestr(
                f"parties/party_{i+1}_{party['id'][:8]}.json",
                json.dumps(party, indent=2, default=str),
            )

        zf.writestr(
            "requirements/all_requirements.json",
            json.dumps(requirements, indent=2, default=str),
        )
        zf.writestr(
            "documents/documents_index.json",
            json.dumps(documents, indent=2, default=str),
        )

        for doc in documents:
            storage_ref = doc.get("blob_path") or doc.get("storage_path")
            if not storage_ref:
                continue
            try:
                backend = backend_for(doc)
                content, _ = await backend.download(doc.get("tenant_id", ""), storage_ref)
                arcname = f"documents/files/{doc.get('original_filename', doc['id'])}"
                zf.writestr(arcname, content)
            except Exception as exc:  # noqa: BLE001 - log and continue with metadata-only
                logger.warning(
                    "Skipping document file in export: id=%s err=%s",
                    doc.get("id"),
                    exc,
                )

        zf.writestr("ai_analysis/results.json", json.dumps(ai_results, indent=2, default=str))
        zf.writestr("screening/runs.json", json.dumps(screening_runs, indent=2, default=str))
        zf.writestr("screening/hits.json", json.dumps(screening_hits, indent=2, default=str))
        zf.writestr("risk/assessments.json", json.dumps(risk_assessments, indent=2, default=str))
        zf.writestr("approvals/tasks.json", json.dumps(approval_tasks, indent=2, default=str))
        zf.writestr("waivers/waivers.json", json.dumps(waivers, indent=2, default=str))
        zf.writestr("audit/audit_trail.json", json.dumps(audit_logs, indent=2, default=str))

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

    zip_bytes = buf.getvalue()

    storage = get_storage()
    upload_meta = await storage.upload(
        tenant_id=tenant_id,
        case_id=case_id,
        filename=export_filename,
        content=zip_bytes,
        content_type="application/zip",
        metadata={"export_kind": "kyc_file"},
    )

    export_record = {
        "id": str(uuid.uuid4()),
        "case_id": case_id,
        "tenant_id": tenant_id,
        "filename": export_filename,
        "storage_type": upload_meta["storage_type"],
        "storage_path": upload_meta["storage_path"],
        "blob_path": upload_meta.get("blob_path"),
        "bucket": upload_meta.get("bucket"),
        "file_size": upload_meta["file_size"],
        "file_hash": upload_meta["file_hash"],
        "mime_type": "application/zip",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.kyc_exports.insert_one({**export_record})

    return export_record
