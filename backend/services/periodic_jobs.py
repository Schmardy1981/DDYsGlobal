"""
Periodic Background Jobs for DDYs Compliance Platform
- Regular Review (RR) auto-generation from NRD dates
- EDR deadline monitoring (28d review, 90d completion)
- Waiver expiry monitoring (30/14/7/1 day alerts, auto-restrict)
- Document expiry monitoring
- Ongoing screening refresh
"""
import asyncio
import uuid
import logging
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)

JOB_INTERVAL_SECONDS = 3600  # Run every hour


async def start_periodic_jobs(db: AsyncIOMotorDatabase):
    """Start all periodic background jobs."""
    logger.info("Starting periodic background jobs...")
    asyncio.create_task(_periodic_loop(db))


async def _periodic_loop(db: AsyncIOMotorDatabase):
    """Main loop that runs all periodic checks."""
    # Wait a bit for app startup
    await asyncio.sleep(10)
    while True:
        try:
            logger.info("Running periodic jobs cycle...")
            now = datetime.now(timezone.utc)

            await _check_nrd_and_generate_rr(db, now)
            await _check_edr_deadlines(db, now)
            await _check_waiver_expiry(db, now)
            await _check_document_expiry(db, now)
            await _run_screening_refresh(db, now)

            # Record last run
            await db.system_settings.update_one(
                {"key": "periodic_jobs"},
                {"$set": {
                    "last_run": now.isoformat(),
                    "status": "healthy",
                    "next_run": (now + timedelta(seconds=JOB_INTERVAL_SECONDS)).isoformat()
                }},
                upsert=True
            )
            logger.info("Periodic jobs cycle complete.")
        except Exception as e:
            logger.error(f"Periodic jobs error: {e}")
            await db.system_settings.update_one(
                {"key": "periodic_jobs"},
                {"$set": {"last_run": datetime.now(timezone.utc).isoformat(), "status": f"error: {str(e)[:200]}"}},
                upsert=True
            )

        await asyncio.sleep(JOB_INTERVAL_SECONDS)


async def _check_nrd_and_generate_rr(db, now: datetime):
    """Check NRD dates and auto-generate Regular Review cases."""
    # Get policy rules for review cycles
    # Default: High=12mo, Medium=24mo, Low=60mo
    # Generate RR 60 days before NRD is due
    LEAD_DAYS = 60

    completed_cases = await db.cases.find({
        "status": "completed",
        "nrd_date": {"$ne": None},
        "deleted": {"$ne": True}
    }, {
        "_id": 0, "id": 1, "nrd_date": 1, "tenant_id": 1, "case_ref": 1,
        "risk_rating": 1, "due_diligence_level": 1, "jurisdiction": 1,
        "product_scope": 1, "assigned_maker_id": 1, "assigned_checker_id": 1,
        "assigned_mlro_id": 1
    }).to_list(5000)

    rr_created = 0
    for case in completed_cases:
        nrd_str = case.get("nrd_date")
        if not nrd_str:
            continue

        try:
            nrd = datetime.fromisoformat(nrd_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue

        trigger_date = nrd - timedelta(days=LEAD_DAYS)
        if now >= trigger_date:
            # Check if RR already exists for this case
            existing_rr = await db.cases.find_one({
                "case_type": "rr",
                "tenant_id": case["tenant_id"],
                "parent_case_id": case["id"],
                "status": {"$nin": ["completed", "rejected", "offboarded"]},
                "deleted": {"$ne": True}
            }, {"_id": 0})

            if not existing_rr:
                rr_case = {
                    "id": str(uuid.uuid4()),
                    "case_ref": f"DDY-{now.strftime('%Y%m%d')}-RR{str(uuid.uuid4())[:4].upper()}",
                    "tenant_id": case["tenant_id"],
                    "case_type": "rr",
                    "status": "draft",
                    "risk_rating": case.get("risk_rating"),
                    "due_diligence_level": case.get("due_diligence_level"),
                    "jurisdiction": case.get("jurisdiction", "EU"),
                    "product_scope": case.get("product_scope"),
                    "nrd_date": nrd_str,
                    "parent_case_id": case["id"],
                    "created_by": "system",
                    "assigned_maker_id": case.get("assigned_maker_id"),
                    "assigned_checker_id": case.get("assigned_checker_id"),
                    "assigned_mlro_id": case.get("assigned_mlro_id"),
                    "sla_json": {"nrd_due": nrd_str, "auto_generated": True},
                    "narrative": "",
                    "narrative_sections": {},
                    "last_action_at": now.isoformat(),
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                    "deleted": False
                }
                await db.cases.insert_one({**rr_case})
                rr_created += 1

                # Create notification
                await _create_notification(
                    db, case["tenant_id"],
                    case.get("assigned_maker_id"),
                    f"Regular Review auto-generated for case {case.get('case_ref')}. NRD: {nrd_str[:10]}",
                    "rr_auto_generated",
                    rr_case["id"]
                )

                # Audit log
                await db.audit_logs.insert_one({
                    "id": str(uuid.uuid4()),
                    "tenant_id": case["tenant_id"],
                    "actor_user_id": "system",
                    "actor_role": "SYSTEM",
                    "action_key": "rr.auto_generated",
                    "entity_type": "case",
                    "entity_id": rr_case["id"],
                    "timestamp": now.isoformat(),
                    "before_json": None,
                    "after_json": {"parent_case": case["id"], "nrd": nrd_str},
                    "ip_address": "",
                    "user_agent": "periodic_jobs"
                })

    if rr_created:
        logger.info(f"Auto-generated {rr_created} Regular Review cases")


async def _check_edr_deadlines(db, now: datetime):
    """Monitor EDR alerts for SLA breaches."""
    open_alerts = await db.edr_alerts.find({
        "status": "open"
    }, {
        "_id": 0, "id": 1, "alert_review_due_at": 1, "completion_due_at": 1,
        "tenant_id": 1, "case_id": 1, "status": 1
    }).to_list(5000)

    for alert in open_alerts:
        alert_review_due = alert.get("alert_review_due_at")
        completion_due = alert.get("completion_due_at")

        # Check 28-day review SLA breach
        if alert_review_due:
            try:
                review_due_dt = datetime.fromisoformat(alert_review_due.replace("Z", "+00:00"))
                if now > review_due_dt:
                    # SLA breached - escalate
                    await db.edr_alerts.update_one(
                        {"id": alert["id"]},
                        {"$set": {
                            "status": "review_sla_breached",
                            "updated_at": now.isoformat()
                        }}
                    )
                    await _create_notification(
                        db, alert["tenant_id"], None,
                        f"EDR Alert review SLA breached (28 days). Case: {alert.get('case_id', '')[:8]}",
                        "edr_review_sla_breach",
                        alert["id"]
                    )
                elif (review_due_dt - now).days <= 3:
                    # Warning - approaching deadline
                    await _create_notification(
                        db, alert["tenant_id"], None,
                        f"EDR Alert review due in {(review_due_dt - now).days} days",
                        "edr_review_approaching",
                        alert["id"]
                    )
            except (ValueError, AttributeError):
                pass

        # Check 90-day completion SLA
        if completion_due:
            try:
                comp_due_dt = datetime.fromisoformat(completion_due.replace("Z", "+00:00"))
                if now > comp_due_dt:
                    # Completion SLA breached - auto-restrict case
                    await db.edr_alerts.update_one(
                        {"id": alert["id"]},
                        {"$set": {
                            "status": "completion_sla_breached",
                            "escalation_to_mlro_at": now.isoformat(),
                            "updated_at": now.isoformat()
                        }}
                    )
                    # Restrict the case
                    if alert.get("case_id"):
                        await db.cases.update_one(
                            {"id": alert["case_id"]},
                            {"$set": {"status": "restricted", "updated_at": now.isoformat()}}
                        )
                    await _create_notification(
                        db, alert["tenant_id"], None,
                        f"EDR completion SLA breached (90 days). Case restricted. Escalated to MLRO.",
                        "edr_completion_sla_breach",
                        alert["id"]
                    )
            except (ValueError, AttributeError):
                pass


async def _check_waiver_expiry(db, now: datetime):
    """Monitor waiver expiry dates."""
    active_waivers = await db.waivers.find({
        "status": "approved",
        "waiver_type": "temporary",
        "expires_at": {"$ne": None}
    }, {"_id": 0}).to_list(5000)

    for waiver in active_waivers:
        expires_str = waiver.get("expires_at")
        if not expires_str:
            continue

        try:
            expires_dt = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue

        days_until = (expires_dt - now).days

        # Expired - auto-restrict
        if days_until < 0:
            await db.waivers.update_one(
                {"id": waiver["id"]},
                {"$set": {"status": "expired", "updated_at": now.isoformat()}}
            )
            # Restrict the case
            if waiver.get("case_id"):
                await db.cases.update_one(
                    {"id": waiver["case_id"]},
                    {"$set": {"status": "restricted", "updated_at": now.isoformat()}}
                )
            # Revert waived requirements
            for req_key in waiver.get("requirement_keys_json", []):
                await db.requirement_items.update_one(
                    {"case_id": waiver["case_id"], "requirement_key": req_key, "status": "waived"},
                    {"$set": {"status": "missing", "updated_at": now.isoformat()}}
                )
            await _create_notification(
                db, waiver["tenant_id"], waiver.get("requested_by"),
                f"Temporary waiver expired. Case restricted pending resolution.",
                "waiver_expired",
                waiver["id"]
            )
            await db.audit_logs.insert_one({
                "id": str(uuid.uuid4()),
                "tenant_id": waiver["tenant_id"],
                "actor_user_id": "system",
                "actor_role": "SYSTEM",
                "action_key": "waiver.auto_expired",
                "entity_type": "waiver",
                "entity_id": waiver["id"],
                "timestamp": now.isoformat(),
                "before_json": {"status": "approved"},
                "after_json": {"status": "expired"},
                "ip_address": "",
                "user_agent": "periodic_jobs"
            })

        # Pre-expiry alerts: 30, 14, 7, 1 days
        elif days_until in [30, 14, 7, 1]:
            await _create_notification(
                db, waiver["tenant_id"], waiver.get("requested_by"),
                f"Temporary waiver expires in {days_until} day{'s' if days_until > 1 else ''}. Action required.",
                f"waiver_expiry_{days_until}d",
                waiver["id"]
            )


async def _check_document_expiry(db, now: datetime):
    """Monitor document expiry dates."""
    docs_with_expiry = await db.documents.find({
        "expiry_date": {"$ne": None}
    }, {"_id": 0}).to_list(5000)

    for doc in docs_with_expiry:
        expiry_str = doc.get("expiry_date")
        if not expiry_str:
            continue
        try:
            expiry_dt = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            continue

        if now > expiry_dt and doc.get("status") != "expired":
            await db.documents.update_one(
                {"id": doc["id"]},
                {"$set": {"status": "expired", "updated_at": now.isoformat()}}
            )
            # Update linked requirement
            if doc.get("requirement_item_id"):
                await db.requirement_items.update_one(
                    {"id": doc["requirement_item_id"]},
                    {"$set": {"status": "missing", "notes": "Document expired", "updated_at": now.isoformat()}}
                )
            # Create EDR alert for document expiry
            if doc.get("case_id"):
                await db.edr_alerts.insert_one({
                    "id": str(uuid.uuid4()),
                    "tenant_id": doc.get("tenant_id", ""),
                    "case_id": doc["case_id"],
                    "trigger_event_type": "document_expiry",
                    "trigger_event_date": now.isoformat(),
                    "detected_by": "system",
                    "alert_generated_at": now.isoformat(),
                    "alert_review_due_at": (now + timedelta(days=28)).isoformat(),
                    "completion_due_at": (now + timedelta(days=90)).isoformat(),
                    "status": "open",
                    "escalation_to_mlro_at": None,
                    "notes": f"Document expired: {doc.get('original_filename', 'unknown')}",
                    "created_at": now.isoformat()
                })


async def _run_screening_refresh(db, now: datetime):
    """Re-screen active clients periodically (weekly check)."""
    # Only run on Mondays (day 0)
    if now.weekday() != 0:
        return

    # Get completed cases that haven't been screened in 7+ days
    seven_days_ago = (now - timedelta(days=7)).isoformat()
    active_cases = await db.cases.find({
        "status": "completed",
        "deleted": {"$ne": True}
    }, {"_id": 0}).to_list(1000)

    for case in active_cases:
        # Check last screening run
        last_run = await db.screening_runs.find_one(
            {"case_id": case["id"]},
            {"_id": 0}
        )
        if last_run and last_run.get("created_at", "") > seven_days_ago:
            continue

        # Run mock screening refresh
        parties = await db.parties.find({"case_id": case["id"], "deleted": {"$ne": True}}, {"_id": 0}).to_list(100)
        if not parties:
            continue

        screening_run = {
            "id": str(uuid.uuid4()),
            "tenant_id": case["tenant_id"],
            "case_id": case["id"],
            "run_type": "sanctions",
            "provider": "mock",
            "started_at": now.isoformat(),
            "finished_at": now.isoformat(),
            "status": "completed",
            "parameters_json": {"type": "ongoing_monitoring", "parties_count": len(parties)},
            "created_at": now.isoformat()
        }
        await db.screening_runs.insert_one({**screening_run})

        from services.screening_service import mock_screen_party
        for party in parties:
            hits = await mock_screen_party(db, screening_run, party, "sanctions")
            if hits:
                await _create_notification(
                    db, case["tenant_id"], case.get("assigned_maker_id"),
                    f"Ongoing screening hit detected for case {case.get('case_ref')}",
                    "screening_refresh_hit",
                    screening_run["id"]
                )


async def _create_notification(db, tenant_id: str, user_id: str, message: str, notif_type: str, entity_id: str):
    """Create an in-app notification."""
    notif = {
        "id": str(uuid.uuid4()),
        "tenant_id": tenant_id,
        "user_id": user_id or "all",
        "message": message,
        "type": notif_type,
        "entity_id": entity_id,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.notifications.insert_one({**notif})


async def run_jobs_now(db: AsyncIOMotorDatabase) -> dict:
    """Manually trigger all periodic jobs (for admin use)."""
    now = datetime.now(timezone.utc)
    results = {"timestamp": now.isoformat(), "jobs": {}}

    try:
        await _check_nrd_and_generate_rr(db, now)
        results["jobs"]["nrd_rr_check"] = "completed"
    except Exception as e:
        results["jobs"]["nrd_rr_check"] = f"error: {str(e)[:100]}"

    try:
        await _check_edr_deadlines(db, now)
        results["jobs"]["edr_deadlines"] = "completed"
    except Exception as e:
        results["jobs"]["edr_deadlines"] = f"error: {str(e)[:100]}"

    try:
        await _check_waiver_expiry(db, now)
        results["jobs"]["waiver_expiry"] = "completed"
    except Exception as e:
        results["jobs"]["waiver_expiry"] = f"error: {str(e)[:100]}"

    try:
        await _check_document_expiry(db, now)
        results["jobs"]["document_expiry"] = "completed"
    except Exception as e:
        results["jobs"]["document_expiry"] = f"error: {str(e)[:100]}"

    try:
        await _run_screening_refresh(db, now)
        results["jobs"]["screening_refresh"] = "completed"
    except Exception as e:
        results["jobs"]["screening_refresh"] = f"error: {str(e)[:100]}"

    # Update last run
    await db.system_settings.update_one(
        {"key": "periodic_jobs"},
        {"$set": {"last_run": now.isoformat(), "status": "manual_run_complete"}},
        upsert=True
    )

    return results
