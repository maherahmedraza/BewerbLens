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
    get_unprocessed_emails,
    insert_pipeline_log,
    insert_raw_email,
    mark_raw_emails_processed,
    update_heartbeat,
)
from telegram_notifier import send_notification
from models import NotificationAction

from pipeline_logger import PipelineLogger, StepTimer
from failure_handler import RetryConfig, with_retry, StepExecutor, HeartbeatMonitor
from fuzzy_matcher import ApplicationMatcher, create_or_update_application


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
    
    # Initialize enterprise tools
    pipeline_log = PipelineLogger(client, step_run_id)
    executor = StepExecutor(client, step_run_id)
    monitor = HeartbeatMonitor(client)
    
    pipeline_log.info(f"Starting V3 Enterprise Pipeline: {run_id}")
    
    try:
        # Initial heartbeat
        if internal_id: 
            update_heartbeat(client, internal_id)

        # ── Step 1: Ingestion (Optimized with Retry) ─────────
        def fetch_step():
            with StepTimer(pipeline_log, "ingestion") as timer:
                existing_ids_snapshot = get_existing_email_ids(client)
                
                service = get_gmail_service()
                if not service:
                    raise Exception("Failed to initialize Gmail service")

                @with_retry(RetryConfig(max_attempts=3))
                def fetch_emails_with_retry():
                    return fetch_emails(service, since_date=since_date, existing_ids=existing_ids_snapshot)

                new_emails = fetch_emails_with_retry()
                timer.checkpoint(f"Fetched {len(new_emails)} new emails")

                # Recovery Pass
                pending_emails = get_unprocessed_emails(client, limit=50)
                if pending_emails:
                    pipeline_log.info(f"Recovery Pass: Found {len(pending_emails)} pending emails")
                    new_ids = {e.email_id for e in new_emails}
                    to_add = [p for p in pending_emails if p.email_id not in new_ids]
                    new_emails.extend(to_add)

                if not new_emails:
                    return []

                # Pre-filters
                new_emails, filter_stats = apply_pre_filters(new_emails)
                timer.checkpoint(f"Input: {len(new_emails)} passed pre-filter")

                for email in new_emails:
                    insert_raw_email(client, email)

                if internal_id: update_heartbeat(client, internal_id)
                return new_emails

        new_emails = executor.execute_step("ingestion", fetch_step)

        if not new_emails:
            pipeline_log.info("No new emails. Pipeline ending early.")
            return stats

        # ── Step 2: Analysis (Adaptive with Partial Success) ─
        def analysis_step():
            with StepTimer(pipeline_log, "analysis") as timer:
                classifier = get_classifier()
                pipeline_log.info(f"Using classifier: {classifier.provider_name}")
                
                # Classify already retries internally in the factory for gemini batches,
                # but we wrap the macro operation just in case
                @with_retry(RetryConfig(max_attempts=3))
                def classify_batch():
                    return classifier.classify(new_emails)
                    
                classifications = classify_batch()
                timer.checkpoint(f"Classified {len(classifications)} emails")
                
                if internal_id: update_heartbeat(client, internal_id)
                return classifications

        classifications = executor.execute_step("analysis", analysis_step)

        # ── Step 3: Persistence (Deduplication via Matcher) ──
        def persistence_step():
            with StepTimer(pipeline_log, "persistence") as timer:
                apps_cache = client.table("applications").select("*").execute().data
                matcher = ApplicationMatcher()

                for email, classification in zip(new_emails, classifications):
                    try:
                        action = create_or_update_application(
                            client, email, classification, apps_cache, matcher
                        )
                        stats[action] += 1
                        
                        if action == "added":
                            # Refresh cache to enable threading across same batch
                            apps_cache = client.table("applications").select("*").execute().data
                            
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
                        pipeline_log.error(f"Error persisting {email.email_id}: {str(e)}")
                        stats["errors"] += 1

                mark_raw_emails_processed(client, [e.email_id for e in new_emails])
                pipeline_log.info(f"Optimized Run Complete: {stats}")

        executor.execute_step("persistence", persistence_step)

        return stats

    except Exception as e:
        pipeline_log.error(f"Pipeline crashed: {str(e)}")
        # Note: StepExecutor already marks the specific step as failed and saves the error message.
        raise
        
    finally:
        pipeline_log.flush()

if __name__ == "__main__":
    import argparse
    from datetime import datetime
    
    parser = argparse.ArgumentParser(description="Run BewerbLens pipeline directly")
    parser.add_argument("--since-date", type=str, help="Fetch emails since date (YYYY-MM-DD)")
    args = parser.parse_args()
    
    dt = None
    if args.since_date:
        dt = datetime.strptime(args.since_date, "%Y-%m-%d").date()
        
    import uuid
    print(f"Triggering pipeline manually (since_date: {dt})...")
    result = run_pipeline(since_date=dt, run_id=str(uuid.uuid4()))
    print(f"Pipeline finished! Results: {result}")
