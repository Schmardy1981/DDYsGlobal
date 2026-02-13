import uuid
import bcrypt
from datetime import datetime, timezone, timedelta


async def seed_all(db):
    """Seed demo data for the DDYs platform."""
    
    # 1. Create Demo Bank tenant
    tenant_id = str(uuid.uuid4())
    tenant = {
        "id": tenant_id,
        "name": "Demo Bank",
        "legal_name": "Demo Bank AG",
        "default_jurisdiction": "EU",
        "branding_json": {"primary_color": "#1E40AF", "logo_url": "", "bank_name": "Demo Bank"},
        "status": "active",
        "created_by": "system",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "deleted": False
    }
    await db.tenants.insert_one({**tenant})
    
    # 2. Create default policy
    policy_id = str(uuid.uuid4())
    policy = {
        "id": policy_id,
        "tenant_id": tenant_id,
        "version_name": "KOS v1.11 Baseline",
        "based_on_kos_version": "1.11",
        "effective_from": datetime.now(timezone.utc).isoformat(),
        "effective_to": None,
        "status": "active",
        "change_summary": "Initial KOS v1.11 baseline",
        "approved_by": "system",
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.tenant_policy_versions.insert_one({**policy})
    
    # Default rules
    rules = [
        {"rule_key": "rr_cycle_high", "rule_value_json": {"months": 12}, "scope": "global"},
        {"rule_key": "rr_cycle_medium", "rule_value_json": {"months": 24}, "scope": "global"},
        {"rule_key": "rr_cycle_low", "rule_value_json": {"months": 60}, "scope": "global"},
        {"rule_key": "edr_alert_review_days", "rule_value_json": {"days": 28}, "scope": "global"},
        {"rule_key": "edr_completion_days", "rule_value_json": {"days": 90}, "scope": "global"},
        {"rule_key": "temp_waiver_max_days", "rule_value_json": {"days": 90}, "scope": "global"},
        {"rule_key": "liveness_threshold", "rule_value_json": {"min_score": 0.70}, "scope": "global"},
        {"rule_key": "deepfake_threshold", "rule_value_json": {"max_score": 0.30}, "scope": "global"},
        {"rule_key": "poa_recency_natural_months", "rule_value_json": {"months": 3}, "scope": "global"},
        {"rule_key": "poa_recency_legal_months", "rule_value_json": {"months": 12}, "scope": "global"},
        {"rule_key": "attestation_max_months_before_signoff", "rule_value_json": {"months": 6}, "scope": "global"},
    ]
    for r in rules:
        await db.policy_rules.insert_one({
            "id": str(uuid.uuid4()),
            "tenant_policy_version_id": policy_id,
            "tenant_id": tenant_id,
            **r,
            "priority": 1,
            "enabled": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    # 3. Create demo users
    users_data = [
        {"email": "admin@ddys.com", "name": "Platform Admin", "global_role": "GLOBAL_SUPER_ADMIN", "password": "Admin123!"},
        {"email": "maker@ddys.com", "name": "Sarah Maker", "global_role": "DDYS_RCM_MAKER", "password": "Maker123!"},
        {"email": "checker@ddys.com", "name": "Michael Checker", "global_role": "DDYS_RCM_CHECKER", "password": "Checker123!"},
        {"email": "qa1@ddys.com", "name": "QA First Line", "global_role": "DDYS_QA_FIRST_LINE", "password": "QA1123!"},
        {"email": "qa2@ddys.com", "name": "QA Second Line", "global_role": "DDYS_QA_SECOND_LINE", "password": "QA2123!"},
        {"email": "compliance@ddys.com", "name": "Compliance Manager", "global_role": "DDYS_COMPLIANCE_MANAGER", "password": "Comp123!"},
        {"email": "bankadmin@demobank.com", "name": "Bank Admin", "global_role": "TENANT_ADMIN", "password": "Bank123!"},
        {"email": "business@demobank.com", "name": "Key Account Mgr", "global_role": "TENANT_BUSINESS_USER", "password": "Biz123!"},
        {"email": "mlro@demobank.com", "name": "Dr. MLRO", "global_role": "TENANT_MLRO", "password": "MLRO123!"},
        {"email": "compliance@demobank.com", "name": "Bank Compliance", "global_role": "TENANT_COMPLIANCE_USER", "password": "BComp123!"},
        {"email": "customer@example.com", "name": "John Customer", "global_role": "END_CUSTOMER", "password": "Cust123!"},
    ]
    
    user_ids = {}
    for ud in users_data:
        uid = str(uuid.uuid4())
        user_ids[ud["email"]] = uid
        pw_hash = bcrypt.hashpw(ud["password"].encode(), bcrypt.gensalt()).decode()
        user = {
            "id": uid,
            "email": ud["email"],
            "name": ud["name"],
            "global_role": ud["global_role"],
            "password_hash": pw_hash,
            "mfa_enabled": False,
            "mfa_secret": None,
            "status": "active",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        }
        await db.users.insert_one({**user})
    
    # 4. Assign tenant roles
    tenant_role_assignments = [
        ("maker@ddys.com", "DDYS_RCM_MAKER"),
        ("checker@ddys.com", "DDYS_RCM_CHECKER"),
        ("qa1@ddys.com", "DDYS_QA_FIRST_LINE"),
        ("qa2@ddys.com", "DDYS_QA_SECOND_LINE"),
        ("compliance@ddys.com", "DDYS_COMPLIANCE_MANAGER"),
        ("bankadmin@demobank.com", "TENANT_ADMIN"),
        ("business@demobank.com", "TENANT_BUSINESS_USER"),
        ("mlro@demobank.com", "TENANT_MLRO"),
        ("compliance@demobank.com", "TENANT_COMPLIANCE_USER"),
    ]
    
    for email, role in tenant_role_assignments:
        await db.user_tenant_roles.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_ids[email],
            "tenant_id": tenant_id,
            "role": role,
            "active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    
    # 5. Create demo onboarding case
    case_id = str(uuid.uuid4())
    case_ref = f"DDY-{datetime.now(timezone.utc).strftime('%Y%m%d')}-DEMO01"
    case = {
        "id": case_id,
        "case_ref": case_ref,
        "tenant_id": tenant_id,
        "case_type": "onboarding",
        "status": "customer_in_progress",
        "risk_rating": "medium",
        "due_diligence_level": "cdd",
        "jurisdiction": "EU",
        "product_scope": "Corporate Banking",
        "nrd_date": None,
        "created_by": user_ids["business@demobank.com"],
        "assigned_maker_id": user_ids["maker@ddys.com"],
        "assigned_checker_id": user_ids["checker@ddys.com"],
        "assigned_mlro_id": user_ids["mlro@demobank.com"],
        "sla_json": {"onboarding_target_days": 30},
        "narrative": "",
        "narrative_sections": {},
        "last_action_at": datetime.now(timezone.utc).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "deleted": False
    }
    await db.cases.insert_one({**case})
    
    # 6. Create parties - legal entity client + 2 UBOs + 1 director
    client_party_id = str(uuid.uuid4())
    client_party = {
        "id": client_party_id,
        "tenant_id": tenant_id,
        "case_id": case_id,
        "party_type": "legal_entity",
        "role_in_case": "client",
        "first_name": "",
        "last_name": "",
        "legal_name": "Acme Trading GmbH",
        "dob": None,
        "nationality": "DE",
        "addresses_json": {"registered": "Friedrichstrasse 100, 10117 Berlin, Germany"},
        "identifiers_json": {"lei": "529900T8BM49AURSDO55", "registration_number": "HRB 123456"},
        "ownership_percent": None,
        "control_flags_json": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "deleted": False
    }
    await db.parties.insert_one({**client_party})
    
    ubo1_id = str(uuid.uuid4())
    ubo1 = {
        "id": ubo1_id,
        "tenant_id": tenant_id,
        "case_id": case_id,
        "party_type": "natural_person",
        "role_in_case": "ubo",
        "first_name": "Hans",
        "last_name": "Mueller",
        "legal_name": "",
        "dob": "1975-03-15",
        "nationality": "DE",
        "addresses_json": {"residential": "Kurfuerstendamm 50, Berlin, Germany"},
        "identifiers_json": {"passport": "C01X00T47"},
        "ownership_percent": 60,
        "control_flags_json": {"managing_director": True},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "deleted": False
    }
    await db.parties.insert_one({**ubo1})
    
    ubo2_id = str(uuid.uuid4())
    ubo2 = {
        "id": ubo2_id,
        "tenant_id": tenant_id,
        "case_id": case_id,
        "party_type": "natural_person",
        "role_in_case": "ubo",
        "first_name": "Maria",
        "last_name": "Schmidt",
        "legal_name": "",
        "dob": "1980-07-22",
        "nationality": "AT",
        "addresses_json": {"residential": "Mariahilfer Strasse 10, Vienna, Austria"},
        "identifiers_json": {"passport": "P4455667"},
        "ownership_percent": 40,
        "control_flags_json": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "deleted": False
    }
    await db.parties.insert_one({**ubo2})
    
    director_id = str(uuid.uuid4())
    director = {
        "id": director_id,
        "tenant_id": tenant_id,
        "case_id": case_id,
        "party_type": "natural_person",
        "role_in_case": "director",
        "first_name": "Peter",
        "last_name": "Weber",
        "legal_name": "",
        "dob": "1968-11-08",
        "nationality": "CH",
        "addresses_json": {"residential": "Bahnhofstrasse 20, Zurich, Switzerland"},
        "identifiers_json": {"passport": "X1234567"},
        "ownership_percent": None,
        "control_flags_json": {"authorized_signatory": True},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "deleted": False
    }
    await db.parties.insert_one({**director})
    
    # 7. Create requirements for each party
    # Legal entity requirements
    le_reqs = [
        {"key": "registry_extract", "cat": "existence", "label": "Registry Extract / Certificate of Incorporation"},
        {"key": "ownership_chart", "cat": "ownership", "label": "Ownership Structure Chart"},
        {"key": "articles_of_association", "cat": "authority", "label": "Articles of Association"},
        {"key": "board_resolution", "cat": "authority", "label": "Board Resolution"},
        {"key": "proof_of_address_entity", "cat": "address", "label": "Proof of Business Address"},
        {"key": "sanctions_screening_entity", "cat": "sanctions", "label": "Entity Sanctions Screening"},
        {"key": "adverse_media_entity", "cat": "adverse_media", "label": "Entity Adverse Media Check"},
        {"key": "financial_statements", "cat": "sof_sow", "label": "Financial Statements"},
    ]
    for r in le_reqs:
        await db.requirement_items.insert_one({
            "id": str(uuid.uuid4()),
            "tenant_id": tenant_id,
            "case_id": case_id,
            "party_id": client_party_id,
            "requirement_key": r["key"],
            "requirement_label": r["label"],
            "requirement_category": r["cat"],
            "status": "missing",
            "due_date": None,
            "rule_source": "kos",
            "notes": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat()
        })
    
    # Natural person requirements (for each UBO and director)
    for pid in [ubo1_id, ubo2_id, director_id]:
        np_reqs = [
            {"key": "identity_doc", "cat": "identity", "label": "Government-issued ID"},
            {"key": "proof_of_address", "cat": "address", "label": "Proof of Address"},
            {"key": "sanctions_screening", "cat": "sanctions", "label": "Sanctions Screening"},
            {"key": "pep_screening", "cat": "pep", "label": "PEP Screening"},
            {"key": "adverse_media", "cat": "adverse_media", "label": "Adverse Media Check"},
        ]
        if pid in [ubo1_id, ubo2_id]:
            np_reqs.append({"key": "sof_sow", "cat": "sof_sow", "label": "Source of Funds / Wealth"})
            np_reqs.append({"key": "video_ident", "cat": "video_ident", "label": "Video Identification"})
        
        for r in np_reqs:
            await db.requirement_items.insert_one({
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "case_id": case_id,
                "party_id": pid,
                "requirement_key": r["key"],
                "requirement_label": r["label"],
                "requirement_category": r["cat"],
                "status": "missing",
                "due_date": None,
                "rule_source": "kos",
                "notes": "",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
    
    # 8. Create questionnaire session
    await db.questionnaire_sessions.insert_one({
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "case_id": case_id,
        "end_customer_user_id": user_ids["customer@example.com"],
        "token": str(uuid.uuid4()),
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "current_step": "entity_type",
        "answers_json": {
            "entity_type": "legal_entity",
            "company_name": "Acme Trading GmbH",
            "jurisdiction": "DE"
        },
        "entity_type_determined": "legal_entity",
        "derived_requirements_json": [],
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {
        "message": "Demo data seeded successfully",
        "tenant_id": tenant_id,
        "case_id": case_id,
        "case_ref": case_ref,
        "users": {u["email"]: {"password": u["password"], "role": u["global_role"]} for u in users_data}
    }
