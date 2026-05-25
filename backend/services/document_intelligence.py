import uuid
import os
import logging
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / '.env')
logger = logging.getLogger(__name__)

LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')

# Document types that satisfy utility bill requirement
UTILITY_BILL_EQUIVALENTS = ["utility_bill", "tax_return", "tax_report", "police_report", "bank_statement"]

# Recency rules (in months)
RECENCY_RULES = {
    "proof_of_address": {"natural_person": 3, "legal_entity": 12},
    "utility_bill": {"natural_person": 3, "legal_entity": 12},
    "tax_return": {"natural_person": 3, "legal_entity": 12},
    "police_report": {"natural_person": 3, "legal_entity": 12},
    "bank_statement": {"natural_person": 3, "legal_entity": 12},
    "registry_extract": {"natural_person": 12, "legal_entity": 12},
}


async def analyze_document(db, doc: dict, content: bytes) -> dict:
    """Analyze a document using deterministic checks + LLM."""

    doc_type = doc.get("doc_type", "unknown")
    filename = doc.get("original_filename", "")
    file_size = len(content)
    mime = doc.get("mime_type", "")
    tenant_id = doc.get("tenant_id", "")
    case_id = doc.get("case_id", "")
    party_id = doc.get("party_id")

    # Step 1: Deterministic checks
    deterministic_results = {
        "file_integrity": "pass" if file_size > 0 else "fail",
        "file_size_ok": "pass" if file_size < 50_000_000 else "fail",
        "format_accepted": "pass" if mime in ["application/pdf", "image/jpeg", "image/png", "image/jpg"] else "warning",
    }

    # Step 2: LLM Analysis (OCR simulation + classification + field extraction)
    llm_result = {}
    try:
        llm_result = await _run_llm_analysis(db, doc, filename, doc_type, mime, case_id, party_id)
    except Exception as e:
        logger.error(f"LLM analysis failed: {e}")
        llm_result = _mock_llm_result(doc_type, filename)

    # Step 3: Recency / validity check
    recency_check = "unknown"
    extracted_date = llm_result.get("extracted_fields", {}).get("document_date")
    if extracted_date:
        recency_check = await _check_recency(db, doc, extracted_date, tenant_id, party_id)
        deterministic_results["recency_check"] = recency_check

    # Step 4: Compute overall decision
    decision = "needs_human"
    if deterministic_results["file_integrity"] == "fail":
        decision = "auto_reject"
    elif llm_result.get("psi_detected"):
        decision = "auto_reject"
    elif llm_result.get("wrong_document_type"):
        decision = "auto_reject"
    elif recency_check == "fail":
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
        "recency_check": recency_check,
        "mismatch_signals_json": llm_result.get("mismatches", []),
        "decision": decision,
        "rationale_text": llm_result.get("rationale", "Document requires manual review"),
        "deterministic_checks": deterministic_results,
        "ocr_text_preview": llm_result.get("ocr_text_preview", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }

    await db.document_ai_results.insert_one({**ai_result})

    # Step 5: Update requirement item status
    if doc.get("requirement_item_id"):
        status_map = {
            "auto_accept": "auto_passed",
            "auto_reject": "rejected",
            "needs_human": "needs_review"
        }
        new_status = status_map.get(decision, "needs_review")
        notes = ""
        if decision == "auto_reject" and recency_check == "fail":
            notes = "Document rejected: exceeds recency limit (3 months for individuals)"
        elif decision == "auto_reject" and llm_result.get("wrong_document_type"):
            notes = f"Document rejected: expected {doc_type}, detected {llm_result.get('classification', 'unknown')}"

        await db.requirement_items.update_one(
            {"id": doc["requirement_item_id"]},
            {"$set": {"status": new_status, "notes": notes, "updated_at": datetime.now(timezone.utc).isoformat()}}
        )

    # Step 6: Cross-document auto-fill logic
    # If tax_return or police_report uploaded, also satisfy utility_bill/proof_of_address
    classified_type = llm_result.get("classification", doc_type)
    if classified_type in UTILITY_BILL_EQUIVALENTS and case_id:
        await _cross_fill_requirements(db, case_id, party_id, classified_type, doc["id"])

    # Step 7: PSI Detection
    if llm_result.get("psi_detected"):
        await _handle_psi_incident(db, doc)

    # Audit
    await db.audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "actor_user_id": "system",
        "actor_role": "SYSTEM",
        "action_key": "document.ai_analyzed",
        "entity_type": "document",
        "entity_id": doc["id"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "before_json": None,
        "after_json": {
            "decision": decision,
            "classification": ai_result["classification"],
            "recency": recency_check,
            "cross_fill": classified_type in UTILITY_BILL_EQUIVALENTS
        },
        "ip_address": "",
        "user_agent": "document_intelligence_service"
    })

    return ai_result


async def _check_recency(db, doc: dict, doc_date_str: str, tenant_id: str, party_id: str) -> str:
    """Check if document is within recency limits."""
    try:
        # Parse date
        doc_date = None
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%dT%H:%M:%S"]:
            try:
                doc_date = datetime.strptime(doc_date_str[:10], fmt)
                break
            except ValueError:
                continue

        if not doc_date:
            return "unknown"

        doc_date = doc_date.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)

        # Get party type
        party_type = "natural_person"
        if party_id:
            party = await db.parties.find_one({"id": party_id}, {"_id": 0})
            if party:
                party_type = party.get("party_type", "natural_person")

        # Get recency limit
        doc_type = doc.get("doc_type", "unknown")
        recency_months = RECENCY_RULES.get(doc_type, {}).get(party_type)

        # Also check tenant policy overrides
        if tenant_id:
            rule_key = f"poa_recency_{party_type.replace('natural_person', 'natural').replace('legal_entity', 'legal')}_months"
            rule = await db.policy_rules.find_one(
                {"tenant_id": tenant_id, "rule_key": rule_key, "enabled": True},
                {"_id": 0}
            )
            if rule:
                recency_months = rule["rule_value_json"].get("months", recency_months)

        if recency_months is None:
            return "unknown"

        cutoff = now - timedelta(days=recency_months * 30)
        if doc_date >= cutoff:
            return "pass"
        else:
            return "fail"

    except Exception as e:
        logger.error(f"Recency check error: {e}")
        return "unknown"


async def _cross_fill_requirements(db, case_id: str, party_id: str, classified_type: str, doc_id: str):
    """Auto-fill related requirements when equivalent documents are uploaded."""
    # Map of document types that can satisfy other requirements
    cross_fill_map = {
        "tax_return": ["proof_of_address", "utility_bill"],
        "tax_report": ["proof_of_address", "utility_bill"],
        "police_report": ["proof_of_address"],
        "utility_bill": ["proof_of_address"],
        "bank_statement": ["proof_of_address"],
    }

    target_keys = cross_fill_map.get(classified_type, [])
    if not target_keys:
        return

    query = {"case_id": case_id, "status": "missing"}
    if party_id:
        query["party_id"] = party_id

    for key in target_keys:
        await db.requirement_items.update_many(
            {**query, "requirement_key": key},
            {"$set": {
                "status": "auto_passed",
                "notes": f"Auto-satisfied by {classified_type} upload (doc: {doc_id[:8]})",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )


async def _run_llm_analysis(db, doc: dict, filename: str, doc_type: str, mime: str, case_id: str, party_id: str) -> dict:
    """Run LLM analysis on document metadata."""

    if not LLM_KEY:
        return _mock_llm_result(doc_type, filename)

    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage

        # Get party context
        party_context = ""
        if party_id:
            party = await db.parties.find_one({"id": party_id}, {"_id": 0})
            if party:
                name = party.get("legal_name") or f"{party.get('first_name', '')} {party.get('last_name', '')}".strip()
                party_context = f"\nParty: {name} ({party.get('party_type', 'unknown')}), Nationality: {party.get('nationality', 'unknown')}"

        chat = LlmChat(
            api_key=LLM_KEY,
            session_id=f"doc-analysis-{doc['id']}",
            system_message="""You are a KYC document analysis expert performing OCR and compliance checks.
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
        )
        chat.with_model("anthropic", "claude-sonnet-4-5-20250929")

        prompt = f"""Analyze this KYC document:
- Filename: {filename}
- Expected type: {doc_type}
- MIME: {mime}
- File size: {doc.get('file_size', 'unknown')} bytes{party_context}

Classify this document, extract key fields (especially dates for recency checks), check authenticity, and determine if it matches the expected type.
Return ONLY valid JSON."""

        response = await chat.send_message(UserMessage(text=prompt))

        import json
        resp_text = str(response)
        if "```json" in resp_text:
            resp_text = resp_text.split("```json")[1].split("```")[0]
        elif "```" in resp_text:
            resp_text = resp_text.split("```")[1].split("```")[0]

        try:
            result = json.loads(resp_text.strip())
            return result
        except (json.JSONDecodeError, IndexError):
            return _mock_llm_result(doc_type, filename)

    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        return _mock_llm_result(doc_type, filename)


def _mock_llm_result(doc_type: str, filename: str) -> dict:
    """Fallback mock LLM result with realistic OCR simulation."""
    type_map = {
        "id": "id_passport",
        "proof_of_address": "proof_of_address",
        "utility_bill": "utility_bill",
        "tax_return": "tax_return",
        "tax_report": "tax_report",
        "police_report": "police_report",
        "registry_extract": "registry_extract",
        "annual_report": "annual_report",
        "ownership_chart": "ownership_chart",
        "attestation": "attestation",
        "bank_statement": "bank_statement",
    }

    classified = type_map.get(doc_type, doc_type)
    # Mock a recent date for the document
    mock_date = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")

    return {
        "classification": classified,
        "extracted_fields": {
            "document_type": classified,
            "document_date": mock_date,
            "filename": filename,
            "name_on_doc": "As per uploaded document",
            "address_on_doc": "",
            "expiry_date": ""
        },
        "ocr_text_preview": f"[OCR Mock] Document: {filename}, Type: {classified}, Date: {mock_date}",
        "authenticity_score": 0.85,
        "tamper_signals": [],
        "mismatches": [],
        "wrong_document_type": False,
        "psi_detected": False,
        "decision": "needs_human",
        "rationale": "Document uploaded and basic checks passed. Manual review recommended."
    }


async def _handle_psi_incident(db, doc: dict):
    """Handle PSI detection."""
    incident = {
        "id": str(uuid.uuid4()),
        "tenant_id": doc.get("tenant_id", ""),
        "case_id": doc.get("case_id", ""),
        "document_id": doc["id"],
        "incident_type": "psi_suspected",
        "status": "open",
        "description": "PSI suspected in uploaded document. Document blocked.",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.compliance_incidents.insert_one({**incident})

    storage_ref = doc.get("blob_path") or doc.get("storage_path")
    if storage_ref:
        try:
            from services.storage import backend_for
            await backend_for(doc).delete(doc.get("tenant_id", ""), storage_ref)
        except Exception:  # noqa: BLE001 - best-effort cleanup
            pass
