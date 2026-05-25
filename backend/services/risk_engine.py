import uuid
from datetime import datetime, timezone


# FATF high-risk and other-monitored jurisdictions. Kept short on purpose —
# if a case touches one of these countries we elevate the score so risk
# rating is not "medium" by default.
HIGH_RISK_COUNTRIES = {
    "AF", "BY", "BI", "CF", "CD", "CU", "ER", "GN", "GW", "HT", "IR", "IQ",
    "KP", "LB", "LY", "ML", "MM", "NI", "RU", "SO", "SS", "SD", "SY", "VE",
    "YE", "ZW",
}
MEDIUM_RISK_COUNTRIES = {
    "AE", "BB", "BG", "BF", "KH", "KY", "GI", "JM", "JO", "MZ", "PA", "PH",
    "SN", "TR", "UG", "VG",
}

HIGH_RISK_INDUSTRIES = {
    "gambling", "crypto", "casino", "money_service", "msb", "arms",
    "precious_metals", "art", "real_estate",
}


async def _score_country(country_code: str) -> int:
    if not country_code:
        return 3
    cc = country_code.upper().strip()[:2]
    if cc in HIGH_RISK_COUNTRIES:
        return 5
    if cc in MEDIUM_RISK_COUNTRIES:
        return 4
    return 2


async def _derive_inputs_from_case(db, case: dict) -> dict:
    """Compute scoring inputs from the case + its parties.

    The previous implementation defaulted every score to 2 because the
    frontend always passed `inputs: {}`. This walks the parties so cases
    actually get differentiated risk ratings without requiring callers to
    supply hand-coded scores.
    """
    case_id = case["id"]
    parties = await db.parties.find(
        {"case_id": case_id, "deleted": {"$ne": True}}, {"_id": 0}
    ).to_list(200)

    # Worst-of country across all parties.
    country_score = 2
    countries: set[str] = set()
    pep_flag = False
    high_risk_country_flag = False
    for p in parties:
        nat = (p.get("nationality") or "").upper().strip()[:2]
        if nat:
            countries.add(nat)
            country_score = max(country_score, await _score_country(nat))
            if nat in HIGH_RISK_COUNTRIES:
                high_risk_country_flag = True
        if (p.get("control_flags_json") or {}).get("pep"):
            pep_flag = True

    # Industry: from product_scope hint (string match — best-effort).
    industry_score = 2
    product_scope = (case.get("product_scope") or "").lower()
    for kw in HIGH_RISK_INDUSTRIES:
        if kw in product_scope:
            industry_score = 4
            break

    # Sanctions / adverse-media signals: if there are open / true-match
    # screening hits we bump product+entity scores.
    open_hits = 0
    true_matches = 0
    try:
        runs = await db.screening_runs.find(
            {"case_id": case_id}, {"_id": 0, "id": 1}
        ).to_list(200)
        run_ids = [r["id"] for r in runs]
        if run_ids:
            open_hits = await db.screening_hits.count_documents(
                {"screening_run_id": {"$in": run_ids}, "disposition": "open"}
            )
            true_matches = await db.screening_hits.count_documents(
                {"screening_run_id": {"$in": run_ids}, "disposition": "true_match"}
            )
    except Exception:
        # screening_hits collection might not exist yet on fresh setups —
        # be defensive, don't fail risk scoring on it.
        pass

    delivery_channel_score = 3  # remote KYC by default — slightly elevated
    entity_type_score = 2
    if any(p.get("party_type") in ("trust", "foundation") for p in parties):
        entity_type_score = 4

    if true_matches > 0:
        entity_type_score = max(entity_type_score, 5)
    if open_hits > 0:
        entity_type_score = max(entity_type_score, 4)

    return {
        "country_score": country_score,
        "industry_score": industry_score,
        "product_score": min(5, 2 + (1 if true_matches else 0)),
        "delivery_channel_score": delivery_channel_score,
        "entity_type_score": entity_type_score,
        "is_pep": pep_flag,
        "high_risk_country": high_risk_country_flag,
        "sanctions_nexus": true_matches > 0,
        "country_codes": sorted(countries),
        "open_hits": open_hits,
        "true_matches": true_matches,
    }


async def compute_risk(db, case: dict, inputs: dict) -> dict:
    """Compute risk assessment using CRRM-like scoring."""

    tenant_id = case["tenant_id"]

    # If the caller didn't pass any inputs (frontend default), derive them
    # from the case data so the score isn't pinned at "medium" for every
    # case. Caller-supplied inputs win on a per-key basis.
    derived = await _derive_inputs_from_case(db, case)
    merged: dict = {**derived, **(inputs or {})}

    country_score = merged.get("country_score", 2)
    industry_score = merged.get("industry_score", 2)
    product_score = merged.get("product_score", 2)
    delivery_channel_score = merged.get("delivery_channel_score", 2)
    entity_type_score = merged.get("entity_type_score", 2)

    per_se_flags = {
        "pep": bool(merged.get("is_pep", False)),
        "high_risk_country": bool(merged.get("high_risk_country", False)),
        "gambling": bool(merged.get("gambling", False)),
        "bearer_shares": bool(merged.get("bearer_shares", False)),
        "correspondent_banking": bool(merged.get("correspondent_banking", False)),
        "sanctions_nexus": bool(merged.get("sanctions_nexus", False)),
    }

    weights = {
        "country": 0.30,
        "industry": 0.20,
        "product": 0.15,
        "delivery_channel": 0.15,
        "entity_type": 0.20
    }

    computed_score = (
        country_score * weights["country"]
        + industry_score * weights["industry"]
        + product_score * weights["product"]
        + delivery_channel_score * weights["delivery_channel"]
        + entity_type_score * weights["entity_type"]
    )

    if computed_score <= 2.0:
        computed_rating = "low"
    elif computed_score <= 3.5:
        computed_rating = "medium"
    else:
        computed_rating = "high"

    if any(per_se_flags.values()):
        computed_rating = "high"

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
            "entity_type": entity_type_score,
            "derived_signals": {
                "country_codes": merged.get("country_codes", []),
                "open_hits": merged.get("open_hits", 0),
                "true_matches": merged.get("true_matches", 0),
            },
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

    await db.cases.update_one(
        {"id": case["id"]},
        {"$set": {
            "risk_rating": computed_rating,
            "due_diligence_level": dd_level,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )

    return assessment
