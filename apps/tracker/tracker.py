# ╔══════════════════════════════════════════════════════════════╗
# ║  Tracker Core — Pipeline coordination                       ║
# ║                                                             ║
# ║  v3.0: Pipeline optimized with adaptive batching,           ║
# ║  abstracted AI classifiers, and two-pass Gmail fetching.    ║
# ╚══════════════════════════════════════════════════════════════╝

from datetime import date
from typing import Optional

from loguru import logger

from classifier_factory import get_classifier
from gmail_service import get_gmail_service, fetch_emails
from pre_filter import apply_pre_filters
from supabase_service import (
    get_client,
    get_existing_email_ids,
    insert_pipeline_log,
    insert_raw_email,
    mark_raw_emails_processed,
    update_heartbeat,
    update_pipeline_step,
    upsert_application,
)
from telegram_notifier import send_notification
from models import NotificationAction


def run_pipeline(
    since_date: Optional[date] = None,
    run_id: str = "manual",
    internal_id: Optional[str] = None,
) -> dict:
    """
    Orquestación de la pipeline BewerbLens v3.
    """
    client = get_client()
    stats = {"added": 0, "updated": 0, "skipped": 0, "errors": 0}
    step_run_id = internal_id or run_id
    current_step = "ingestion"

    def log_sink(level, msg):
        logger.log(level, msg)
        if internal_id:
            insert_pipeline_log(client, internal_id, level, msg, step_name="tracker")

    log_sink("INFO", f"Starting Optimized Pipeline: {run_id}")

    try:
        # ── Step 1: Ingestion (Optimized) ────────────────────
        current_step = "ingestion"
        update_pipeline_step(client, step_run_id, "ingestion", "running", progress=0)

        # Snapshot para filtrado en Gmail
        existing_ids_snapshot = get_existing_email_ids(client)
        
        service = get_gmail_service()
        if not service:
            raise Exception("Failed to initialize Gmail service")

        # Ingestion optimizada: filtrado de IDs ocurre DENTRO de fetch_emails (Pass 1)
        # Solo se descargan cuerpos completos de emails estrictamente nuevos (Pass 2)
        new_emails = fetch_emails(service, since_date=since_date, existing_ids=existing_ids_snapshot)

        if not new_emails:
            update_pipeline_step(client, step_run_id, "ingestion", "success", progress=100)
            log_sink("INFO", "No new emails found. Pipeline ending early.")
            return stats

        # Pre-filtros para ahorrar tokens
        new_emails, filter_stats = apply_pre_filters(new_emails)
        log_sink("INFO", f"Pre-filter: {filter_stats.total} total → {filter_stats.passed} passed")

        for i, email in enumerate(new_emails):
            insert_raw_email(client, email)
            if i % 10 == 0:
                update_pipeline_step(client, step_run_id, "ingestion", "running", progress=int((i/len(new_emails))*100))

        update_pipeline_step(client, step_run_id, "ingestion", "success", progress=100)
        if internal_id: update_heartbeat(client, internal_id)

        # ── Step 2: Analysis (Adaptive) ──────────────────────
        current_step = "analysis"
        update_pipeline_step(client, step_run_id, "analysis", "running", progress=0)
        
        # Abstracción de clasificador (Fábrica)
        classifier = get_classifier()
        log_sink("INFO", f"Using classifier: {classifier.provider_name}")
        
        classifications = classifier.classify(new_emails)
        update_pipeline_step(client, step_run_id, "analysis", "success", progress=100)
        if internal_id: update_heartbeat(client, internal_id)

        # ── Step 3: Persistence ──────────────────────────────
        current_step = "persistence"
        update_pipeline_step(client, step_run_id, "persistence", "running", progress=0)

        apps_cache = client.table("applications").select("*").execute().data

        for i, (email, classification) in enumerate(zip(new_emails, classifications)):
            try:
                action = upsert_application(client, email, classification, apps_cache=apps_cache)
                stats[action] += 1

                if action in ("added", "updated"):
                    # Notificación opcional
                    from models import CLASSIFICATION_TO_STATUS
                    status_enum = CLASSIFICATION_TO_STATUS.get(classification.classification)
                    status_val = status_enum.value if status_enum else "Applied"

                    send_notification(
                        action=NotificationAction.ADDED if action == "added" else NotificationAction.UPDATED,
                        company_name=classification.company_name,
                        job_title=classification.job_title,
                        status=status_val,
                        platform=classification.platform,
                        email_subject=email.subject,
                    )
            except Exception as e:
                log_sink("ERROR", f"Error persisting {email.email_id}: {str(e)}")
                stats["errors"] += 1

            if i % 5 == 0:
                update_pipeline_step(client, step_run_id, "persistence", "running", progress=int((i/len(new_emails))*100))

        mark_raw_emails_processed(client, [e.email_id for e in new_emails])
        update_pipeline_step(client, step_run_id, "persistence", "success", progress=100)

        log_sink("INFO", f"Optimized Run Complete: {stats}")
        return stats

    except Exception as e:
        log_sink("ERROR", f"Pipeline crashed at step '{current_step}': {str(e)}")
        update_pipeline_step(client, step_run_id, current_step, "failed", message=str(e))
        raise
