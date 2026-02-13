import uuid
from datetime import datetime, timezone


async def compute_risk(db, case: dict, inputs: dict) -> dict:
    """Compute risk assessment using CRRM-like scoring."""
    
    tenant_id = case["tenant_id"]
    
    # Get policy rules for scoring
    rules = await db.policy_rules.find({"tenant_id": tenant_id, "enabled": True}, {"_id": 0}).to_list(100)
    
    # Default scoring inputs
    country_score = inputs.get("country_score", 2)  # 1-5
    industry_score = inputs.get("industry_score", 2)
    product_score = inputs.get("product_score", 2)
    delivery_channel_score = inputs.get("delivery_channel_score", 2)
    entity_type_score = inputs.get("entity_type_score", 2)
    
    # Per-se flags
    per_se_flags = {
        "pep": inputs.get("is_pep", False),
        "high_risk_country": inputs.get("high_risk_country", False),
        "gambling": inputs.get("gambling", False),
        "bearer_shares": inputs.get("bearer_shares", False),
        "correspondent_banking": inputs.get("correspondent_banking", False),
        "sanctions_nexus": inputs.get("sanctions_nexus", False),
    }
    
    # Compute weighted score
    weights = {
        "country": 0.30,
        "industry": 0.20,
        "product": 0.15,
        "delivery_channel": 0.15,
        "entity_type": 0.20
    }
    
    computed_score = (
        country_score * weights["country"] +
        industry_score * weights["industry"] +
        product_score * weights["product"] +
        delivery_channel_score * weights["delivery_channel"] +
        entity_type_score * weights["entity_type"]
    )
    
    # Determine rating
    if computed_score <= 2.0:
        computed_rating = "low"
    elif computed_score <= 3.5:
        computed_rating = "medium"
    else:
        computed_rating = "high"
    
    # Per-se flags override to high
    if any(per_se_flags.values()):
        computed_rating = "high"
    
    # Determine due diligence level
    dd_level = "edd" if computed_rating == "high" else "cdd"
    
    assessment = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "case_id": case["id"],
        "methodology": "CRRM-like",
        "inputs_json": {
            "country": country_score,
            "industry": industry_score,
            "product": product_score,
            "delivery_channel": delivery_channel_score,
            "entity_type": entity_type_score
        },
        "per_se_flags_json": per_se_flags,
        "computed_score": round(computed_score, 2),
        "computed_rating": computed_rating,
        "final_rating": computed_rating,
        "due_diligence_level": dd_level,
        "challenged": False,
        "challenge_reason": None,
        "approved_by_mlro": None,
        "approved_at": None,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.risk_assessments.insert_one({**assessment})
    
    # Update case with risk rating
    await db.cases.update_one(
        {"id": case["id"]},
        {"$set": {
            "risk_rating": computed_rating,
            "due_diligence_level": dd_level,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    return assessment
