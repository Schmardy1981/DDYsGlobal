import uuid
import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / '.env')
logger = logging.getLogger(__name__)

LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')


async def analyze_document(db, doc: dict, content: bytes) -> dict:
    """Analyze a document using LLM + deterministic checks."""
    
    doc_type = doc.get("doc_type", "unknown")
    filename = doc.get("original_filename", "")
    file_size = len(content)
    mime = doc.get("mime_type", "")
    
    # Deterministic checks
    deterministic_results = {
        "file_integrity": "pass" if file_size > 0 else "fail",
        "file_size_ok": "pass" if file_size < 50_000_000 else "fail",
        "format_accepted": "pass" if mime in ["application/pdf", "image/jpeg", "image/png", "image/jpg"] else "warning",
    }
    
    # LLM Analysis (using Claude via Emergent LLM key)
    llm_result = {}
    try:
        llm_result = await _run_llm_analysis(doc, filename, doc_type, mime)
    except Exception as e:
        logger.error(f"LLM analysis failed: {e}")
        llm_result = {
            "classification": doc_type,
            "extracted_fields": {},
            "anomalies": [],
            "psi_detected": False,
            "decision": "needs_human",
            "rationale": f"LLM analysis unavailable: {str(e)}"
        }
    
    # Compute overall decision
    decision = "needs_human"
    if deterministic_results["file_integrity"] == "fail":
        decision = "auto_reject"
    elif llm_result.get("psi_detected"):
        decision = "auto_reject"
    elif llm_result.get("decision") == "auto_accept" and all(v == "pass" for v in deterministic_results.values()):
        decision = "auto_accept"
    elif llm_result.get("decision") == "auto_reject":
        decision = "auto_reject"
    
    ai_result = {
        "id": str(uuid.uuid4()),
        "document_id": doc["id"],
        "provider": "claude_emergent",
        "classification": llm_result.get("classification", doc_type),
        "extracted_fields_json": llm_result.get("extracted_fields", {}),
        "authenticity_score": llm_result.get("authenticity_score", 0.85),
        "tamper_signals_json": llm_result.get("tamper_signals", []),
        "recency_check": llm_result.get("recency_check", "unknown"),
        "mismatch_signals_json": llm_result.get("mismatches", []),
        "decision": decision,
        "rationale_text": llm_result.get("rationale", "Document requires manual review"),
        "deterministic_checks": deterministic_results,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.document_ai_results.insert_one({**ai_result})
    
    # Update requirement item status based on decision
    if doc.get("requirement_item_id"):
        status_map = {
            "auto_accept": "auto_passed",
            "auto_reject": "rejected",
            "needs_human": "needs_review"
        }
        new_status = status_map.get(decision, "needs_review")
        await db.requirement_items.update_one(
            {"id": doc["requirement_item_id"]},
            {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )
    
    # PSI Detection - block and create incident
    if llm_result.get("psi_detected"):
        await _handle_psi_incident(db, doc)
    
    # Audit
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": doc.get("tenant_id", ""),
        "actor_user_id": "system",
        "actor_role": "SYSTEM",
        "action_key": "document.ai_analyzed",
        "entity_type": "document",
        "entity_id": doc["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": None,
        "after_json": {"decision": decision, "classification": ai_result["classification"]},
        "ip_address": "",
        "user_agent": "document_intelligence_service"
    })
    
    return ai_result


async def _run_llm_analysis(doc: dict, filename: str, doc_type: str, mime: str) -> dict:
    """Run LLM analysis on document metadata."""
    
    if not LLM_KEY:
        return _mock_llm_result(doc_type, filename)
    
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        chat = LlmChat(
            api_key=LLM_KEY,
            session_id=f"doc-analysis-{doc['id']}",
            system_message="""You are a KYC document analysis expert. Analyze document metadata and provide structured assessment.
Return a JSON object with these fields:
- classification: document type (id_passport, id_national, proof_of_address, registry_extract, annual_report, ownership_chart, attestation, bank_statement, other)
- extracted_fields: dict of key fields you can infer
- authenticity_score: 0.0-1.0 confidence
- tamper_signals: list of any suspicious indicators
- recency_check: pass/fail/unknown
- mismatches: list of inconsistencies
- psi_detected: boolean - true if content suggests Price Sensitive Information
- decision: auto_accept, auto_reject, or needs_human
- rationale: explanation of decision
Respond ONLY with valid JSON."""
        )
        chat.with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        prompt = f"""Analyze this KYC document:
- Filename: {filename}
- Declared type: {doc_type}
- MIME type: {mime}
- File size: {doc.get('file_size', 'unknown')} bytes

Based on the filename and type, classify this document and assess it for KYC compliance.
Return ONLY valid JSON."""
        
        response = await chat.send_message(UserMessage(text=prompt))
        
        import json
        # Try to parse JSON from response
        try:
            # Find JSON in response
            resp_text = str(response)
            if "```json" in resp_text:
                resp_text = resp_text.split("```json")[1].split("```")[0]
            elif "```" in resp_text:
                resp_text = resp_text.split("```")[1].split("```")[0]
            result = json.loads(resp_text.strip())
            return result
        except (json.JSONDecodeError, IndexError):
            logger.warning(f"Could not parse LLM response as JSON: {response}")
            return _mock_llm_result(doc_type, filename)
    
    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return _mock_llm_result(doc_type, filename)


def _mock_llm_result(doc_type: str, filename: str) -> dict:
    """Fallback mock LLM result."""
    type_map = {
        "id": "id_passport",
        "proof_of_address": "proof_of_address",
        "registry_extract": "registry_extract",
        "annual_report": "annual_report",
        "ownership_chart": "ownership_chart",
        "attestation": "attestation",
        "bank_statement": "bank_statement",
    }
    
    return {
        "classification": type_map.get(doc_type, doc_type),
        "extracted_fields": {"document_type": doc_type, "filename": filename},
        "authenticity_score": 0.85,
        "tamper_signals": [],
        "recency_check": "unknown",
        "mismatches": [],
        "psi_detected": False,
        "decision": "needs_human",
        "rationale": "Document uploaded and basic checks passed. Manual review recommended for verification."
    }


async def _handle_psi_incident(db, doc: dict):
    """Handle PSI (Price Sensitive Information) detection."""
    incident = {
        "id": str(uuid.uuid4()),
        "tenant_id": doc.get("tenant_id", ""),
        "case_id": doc.get("case_id", ""),
        "document_id": doc["id"],
        "incident_type": "psi_suspected",
        "status": "open",
        "description": "PSI suspected in uploaded document. Document has been blocked from storage.",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.compliance_incidents.insert_one({**incident})
    
    # Remove file from storage
    storage_path = doc.get("storage_path")
    if storage_path:
        try:
            os.remove(storage_path)
        except OSError:
            pass
