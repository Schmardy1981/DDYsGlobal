import uuid
import random
from datetime import datetime, timezone


async def mock_screen_party(db, screening_run: dict, party: dict, run_type: str) -> list:
    """Mock screening for a party. Returns list of hits."""
    
    name = f"{party.get('first_name', '')} {party.get('last_name', '')}".strip()
    if not name:
        name = party.get("legal_name", "Unknown")
    
    hits = []
    
    # Simulate screening with ~20% hit rate for demo
    if random.random() < 0.2:
        hit_templates = {
            "sanctions": [
                {"list_source": "UN Security Council", "hit_severity": "high", "match_score": 0.85},
                {"list_source": "EU Sanctions", "hit_severity": "high", "match_score": 0.72},
                {"list_source": "OFAC SDN", "hit_severity": "high", "match_score": 0.68},
            ],
            "pep": [
                {"list_source": "World-Check PEP", "hit_severity": "medium", "match_score": 0.78},
                {"list_source": "PEP Database", "hit_severity": "medium", "match_score": 0.65},
            ],
            "adverse_media": [
                {"list_source": "Adverse Media DB", "hit_severity": "low", "match_score": 0.55},
                {"list_source": "News Analytics", "hit_severity": "medium", "match_score": 0.62},
            ]
        }
        
        templates = hit_templates.get(run_type, hit_templates["sanctions"])
        template = random.choice(templates)
        
        hit = {
            "id": str(uuid.uuid4()),
            "screening_run_id": screening_run["id"],
            "party_id": party["id"],
            "tenant_id": screening_run["tenant_id"],
            "hit_severity": template["hit_severity"],
            "match_score": template["match_score"],
            "matched_name": name + " (partial match)",
            "list_source": template["list_source"],
            "details_json": {
                "matched_entity": name,
                "match_type": "name_fuzzy",
                "additional_info": f"Mock {run_type} hit for testing",
                "source_url": f"https://example.com/{run_type}/reference"
            },
            "disposition": "open",
            "decided_by": None,
            "decided_at": None,
            "notes": "",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.screening_hits.insert_one({**hit})
        hits.append(hit)
    
    return hits
