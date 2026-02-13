import uuid
import os
import logging
from datetime import datetime, timezone
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).parent.parent / '.env')
logger = logging.getLogger(__name__)

LLM_KEY = os.environ.get('EMERGENT_LLM_KEY', '')


async def run_osint_analysis(db, case_id: str, party_id: str) -> dict:
    """Run OSINT/Risk analysis on a party using LLM."""
    
    party = await db.parties.find_one({"id": party_id}, {"_id": 0})
    if not party:
        raise ValueError("Party not found")
    
    case = await db.cases.find_one({"id": case_id}, {"_id": 0})
    
    name = f"{party.get('first_name', '')} {party.get('last_name', '')}".strip()
    if not name:
        name = party.get("legal_name", "Unknown")
    
    nationality = party.get("nationality", "Unknown")
    party_type = party.get("party_type", "unknown")
    
    result = {}
    
    try:
        from emergentintegrations.llm.chat import LlmChat, UserMessage
        
        chat = LlmChat(
            api_key=LLM_KEY,
            session_id=f"osint-{party_id}",
            system_message="""You are an OSINT and risk analysis expert for KYC/AML compliance.
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
        )
        chat.with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        prompt = f"""Perform OSINT risk analysis for KYC compliance:

Entity Name: {name}
Entity Type: {party_type}
Nationality: {nationality}
Role in Case: {party.get('role_in_case', 'unknown')}
Addresses: {party.get('addresses_json', {})}
Identifiers: {party.get('identifiers_json', {})}

Analyze this entity for:
1. PEP (Politically Exposed Person) indicators
2. Adverse media and reputation risks
3. Sanctions exposure
4. Country/jurisdiction risks
5. Overall risk profile

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
        except Exception:
            result = _mock_osint_result(name, party_type)
    
    except Exception as e:
        logger.error(f"OSINT analysis failed: {e}")
        result = _mock_osint_result(name, party_type)
    
    # Store result
    osint_record = {
        "id": str(uuid.uuid4()),
        "case_id": case_id,
        "party_id": party_id,
        "tenant_id": case.get("tenant_id", ""),
        "analysis_type": "osint_risk",
        "result_json": result,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.osint_results.insert_one({**osint_record})
    
    return osint_record


def _mock_osint_result(name: str, party_type: str) -> dict:
    return {
        "risk_indicators": ["Standard risk profile - no significant indicators found"],
        "pep_likelihood": "low",
        "adverse_media_summary": "No adverse media findings in mock analysis",
        "sanctions_risk": "low",
        "country_risk": "medium",
        "recommendations": [
            "Standard CDD procedures sufficient",
            "Monitor for changes in risk profile",
            "Schedule regular review per policy"
        ],
        "overall_risk_assessment": "low",
        "rationale": f"Mock OSINT analysis for {name} ({party_type}). Replace with real OSINT provider for production use."
    }
