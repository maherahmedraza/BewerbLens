# ╔══════════════════════════════════════════════════════════════╗
# ║  Tracker Core — Pipeline coordination                       ║
# ║                                                             ║
# ║  Fixes applied:                                             ║
# ║  #2  — Snapshot existing IDs BEFORE ingest to fix dedup bug ║
# ║  #14 — heartbeat calls added between steps                  ║
# ║  #17 — fetch and pass apps_cache to minimize DB calls       ║
# ║  #G  — Correct gmail_service imports                        ║
# ║  #I  — Stats keys match upsert_application return values    ║
# ║  #J  — update_pipeline_step uses internal_id (UUID)         ║
# ║  #O  — pre_filter.apply_pre_filters() re-added              ║
# ║  #P  — Error handler marks correct step as failed           ║
# ╚══════════════════════════════════════════════════════════════╝

from datetime import date
from typing import Optional

from loguru import logger

from gemini_classifier import classify_emails
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
    Lógica principal de orquestación para la pipeline de ingestión.

    Fixes:
    - Heartbeat dedicado entre steps.
    - Snapshot pre-ingest para deduplicación fiable.
    - Cache de DB para fuzzy matching.
    - Pre-filtros para evitar gastar tokens de Gemini en basura.
    - Tracking del step actual para reportar errores correctamente.
    """
    client = get_client()
    # Fix #I: keys coinciden con los valores que retorna upsert_application
    stats = {"added": 0, "updated": 0, "skipped": 0, "errors": 0}

    # Fix #J: usar internal_id (UUID) para pipeline_run_steps,
    # no run_id (label legible como "RUN-20260409-123456")
    step_run_id = internal_id or run_id

    # Fix #P: rastrear el step actual para reportar errores correctamente
    current_step = "ingestion"

    def log_sink(level, msg):
        logger.log(level, msg)
        # insert_pipeline_log espera el UUID, no el label
        if internal_id:
            insert_pipeline_log(client, internal_id, level, msg, step_name="tracker")

    log_sink("INFO", f"Starting pipeline run: {run_id}")

    try:
        # ── Fix #2: Snapshot ANTES de ingestar ────────────────
        # Antes se obtenían IDs durante el loop, pero como insertábamos
        # en el mismo loop, aparecían como "existentes" para iteraciones
        # posteriores del MISMO run.
        log_sink("INFO", "Snapshotting existing email IDs before ingest...")
        existing_ids_snapshot = get_existing_email_ids(client)

        # ── Step 1: Ingestion ────────────────────────────────
        current_step = "ingestion"
        update_pipeline_step(client, step_run_id, "ingestion", "running", progress=0)

        service = get_gmail_service()
        if not service:
            raise Exception("Failed to initialize Gmail service")

        # Fix #G: fetch_emails ahora recibe (service, since_date)
        emails = fetch_emails(service, since_date=since_date)

        # Filtrar emails ya existentes usando el snapshot
        new_emails = [e for e in emails if e.email_id not in existing_ids_snapshot]

        # Fix #O: aplicar pre-filtros ANTES de enviar a Gemini
        # Esto ahorra tokens filtrando job alerts, newsletters, etc.
        if new_emails:
            new_emails, filter_stats = apply_pre_filters(new_emails)
            log_sink("INFO", f"Pre-filter: {filter_stats.total} total → {filter_stats.passed} passed")

        log_sink("INFO", f"Fetched {len(emails)} total; {len(new_emails)} new after dedup+filter.")

        for i, email in enumerate(new_emails):
            insert_raw_email(client, email)
            if i % 5 == 0:
                update_pipeline_step(
                    client, step_run_id, "ingestion", "running",
                    progress=int((i / len(new_emails)) * 100),
                )

        update_pipeline_step(client, step_run_id, "ingestion", "success", progress=100)
        if internal_id:
            update_heartbeat(client, internal_id)

        if not new_emails:
            log_sink("INFO", "No new emails to process. Pipeline ending.")
            return stats

        # ── Step 2: Analysis (Gemini) ────────────────────────
        current_step = "analysis"
        update_pipeline_step(client, step_run_id, "analysis", "running", progress=0)
        classifications = classify_emails(new_emails)
        update_pipeline_step(client, step_run_id, "analysis", "success", progress=100)
        if internal_id:
            update_heartbeat(client, internal_id)

        # ── Step 3: Persistence (Silver Layer) ───────────────
        current_step = "persistence"
        update_pipeline_step(client, step_run_id, "persistence", "running", progress=0)

        # Fix #17: Obtener todas las aplicaciones UNA VEZ para fuzzy matching
        log_sink("INFO", "Fetching applications cache for fuzzy matching...")
        apps_cache = client.table("applications").select("*").execute().data

        for i, (email, classification) in enumerate(zip(new_emails, classifications)):
            try:
                action = upsert_application(client, email, classification, apps_cache=apps_cache)
                stats[action] += 1

                if action in ("added", "updated"):
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

            if i % 2 == 0:
                update_pipeline_step(
                    client, step_run_id, "persistence", "running",
                    progress=int((i / len(new_emails)) * 100),
                )

        # Marcar como procesados en Bronze
        mark_raw_emails_processed(client, [e.email_id for e in new_emails])
        update_pipeline_step(client, step_run_id, "persistence", "success", progress=100)

        log_sink("INFO", f"Run Complete: {stats}")
        return stats

    except Exception as e:
        log_sink("ERROR", f"Pipeline crashed at step '{current_step}': {str(e)}")
        # Fix #P: marcar el step CORRECTO como fallido, no siempre "analysis"
        update_pipeline_step(client, step_run_id, current_step, "failed", message=str(e))
        raise


if __name__ == "__main__":
    # Ejecución local de prueba
    run_pipeline()
