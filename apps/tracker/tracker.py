# ╔══════════════════════════════════════════════════════════════╗
# ║  COMPLETE Multi-User Tracker Integration                    ║
# ║                                                             ║
# ║  This file replaces tracker.py with FULL multi-user support ║
# ║  • Fetches Gmail credentials per user_id                    ║
# ║  • Applies email filters per user_id                        ║
# ║  • Writes applications with user_id                         ║
# ╚══════════════════════════════════════════════════════════════╝

from datetime import date
from typing import Optional, List
from loguru import logger

from classifier_factory import get_classifier
from gmail_service import get_gmail_service_for_user  # NEW
from pre_filter import apply_user_filters  # NEW
from supabase_service import (
    get_client,
    get_existing_email_ids,
    get_unprocessed_emails,
    insert_raw_email,
    mark_raw_emails_processed,
    update_heartbeat,
    update_pipeline_step,
)
from telegram_notifier import send_notification
from models import NotificationAction, CLASSIFICATION_TO_STATUS
from fuzzy_matcher import ApplicationMatcher, upsert_application_fixed


def run_pipeline_multiuser(
    user_id: str,  # ← NEW: Required parameter
    since_date: Optional[date] = None,
    run_id: str = "manual",
    internal_id: Optional[str] = None,
) -> dict:
    """
    MULTI-USER pipeline execution.
    
    Args:
        user_id: UUID of the user whose emails to process
        since_date: Fetch emails from this date onwards
        run_id: Human-readable run identifier
        internal_id: Database UUID for pipeline_runs table
    
    Returns:
        Stats dict: {added, updated, skipped, errors}
    """
    client = get_client()
    stats = {"added": 0, "updated": 0, "skipped": 0, "errors": 0}
    step_run_id = internal_id or run_id
    current_step = "ingestion"
    
    # ═══════════════════════════════════════════════════════════
    # STEP 0: Fetch User Profile & Credentials
    # ═══════════════════════════════════════════════════════════
    
    log_to_db(client, internal_id, "INFO", f"Fetching profile for user {user_id}", "setup")
    
    try:
        user_profile = client.table("user_profiles").select("*").eq("id", user_id).single().execute()
        if not user_profile.data:
            raise Exception(f"User profile not found: {user_id}")
        
        user = user_profile.data
        log_to_db(client, internal_id, "INFO", f"User: {user['email']} | Region: {user['region']}", "setup")
    
    except Exception as e:
        log_to_db(client, internal_id, "ERROR", f"Failed to load user profile: {e}", "setup")
        raise
    
    # Initialize matcher
    matcher = ApplicationMatcher(
        company_threshold=0.85,
        job_threshold=0.75,
        composite_threshold=0.80
    )

    try:
        # ═══════════════════════════════════════════════════════════
        # STEP 1: Ingestion (User-Specific)
        # ═══════════════════════════════════════════════════════════
        
        current_step = "ingestion"
        update_pipeline_step(client, step_run_id, "ingestion", "running", progress=0)
        log_to_db(client, internal_id, "INFO", "Starting email ingestion", "ingestion")

        # Fetch existing email IDs for THIS USER ONLY
        existing_ids_snapshot = get_existing_email_ids_for_user(client, user_id)
        
        # Get Gmail service with USER'S credentials
        service = get_gmail_service_for_user(user, db_client=client)
        if not service:
            raise Exception(f"Failed to initialize Gmail for user {user_id}")

        # Fetch emails using user's Gmail account
        new_emails = fetch_emails_for_user(
            service, 
            user_id=user_id,
            since_date=since_date, 
            existing_ids=existing_ids_snapshot
        )
        log_to_db(client, internal_id, "INFO", f"Fetched {len(new_emails)} new emails", "ingestion")

        # Recovery pass (unprocessed emails for this user)
        pending_emails = get_unprocessed_emails_for_user(client, user_id, limit=50)
        if pending_emails:
            log_to_db(client, internal_id, "INFO", f"Recovery: {len(pending_emails)} pending", "ingestion")
            new_ids = {e.email_id for e in new_emails}
            to_add = [p for p in pending_emails if p.email_id not in new_ids]
            new_emails.extend(to_add)

        if not new_emails:
            update_pipeline_step(client, step_run_id, "ingestion", "success", progress=100)
            log_to_db(client, internal_id, "INFO", "No new emails. Ending pipeline.", "ingestion")
            return stats

        # ═══ Apply USER'S custom email filters ═══
        new_emails, filter_stats = apply_user_filters(client, user_id, new_emails)
        log_to_db(
            client, internal_id, "INFO",
            f"Filtered: {filter_stats.passed}/{filter_stats.total} emails passed user filters",
            "ingestion"
        )

        # Insert to raw_emails with user_id
        for i, email in enumerate(new_emails):
            insert_raw_email_with_user(client, user_id, email)
            if i % 10 == 0:
                progress = int((i / len(new_emails)) * 100)
                update_pipeline_step(client, step_run_id, "ingestion", "running", progress=progress)

        update_pipeline_step(client, step_run_id, "ingestion", "success", progress=100)
        if internal_id:
            update_heartbeat(client, internal_id)

        # ═══════════════════════════════════════════════════════════
        # STEP 2: Analysis
        # ═══════════════════════════════════════════════════════════
        
        current_step = "analysis"
        update_pipeline_step(client, step_run_id, "analysis", "running", progress=0)
        log_to_db(client, internal_id, "INFO", f"Classifying {len(new_emails)} emails", "analysis")

        classifier = get_classifier()
        classifications = classifier.classify(new_emails)
        log_to_db(client, internal_id, "INFO", f"Classified {len(classifications)} emails", "analysis")

        update_pipeline_step(client, step_run_id, "analysis", "success", progress=100)
        if internal_id:
            update_heartbeat(client, internal_id)

        # ═══════════════════════════════════════════════════════════
        # STEP 3: Persistence (User-Scoped)
        # ═══════════════════════════════════════════════════════════
        
        current_step = "persistence"
        update_pipeline_step(client, step_run_id, "persistence", "running", progress=0)
        log_to_db(client, internal_id, "INFO", "Saving to database", "persistence")

        # Load application cache FOR THIS USER ONLY
        apps_cache = client.table("applications").select("*").eq("user_id", user_id).execute().data

        for i, (email, classification) in enumerate(zip(new_emails, classifications)):
            try:
                action = upsert_application_fixed(
                    client,
                    user_id,  # ← Pass user_id to upsert
                    email,
                    classification,
                    apps_cache,
                    matcher
                )
                stats[action] += 1
                
                # Refresh cache after each ADD
                if action == "added":
                    apps_cache = client.table("applications").select("*").eq("user_id", user_id).execute().data
                    log_to_db(
                        client, internal_id, "INFO",
                        f"Added: {classification.company_name} / {classification.job_title}",
                        "persistence"
                    )
                else:
                    log_to_db(
                        client, internal_id, "INFO",
                        f"Updated: {classification.company_name} / {classification.job_title}",
                        "persistence"
                    )

                # Telegram notification (use user's settings)
                if user.get('telegram_enabled') and action in ("added", "updated"):
                    status_enum = CLASSIFICATION_TO_STATUS.get(classification.classification)
                    status_val = status_enum.value if status_enum else "Applied"

                    send_notification_for_user(
                        user=user,
                        action=NotificationAction.ADDED if action == "added" else NotificationAction.UPDATED,
                        company_name=classification.company_name,
                        job_title=classification.job_title,
                        status=status_val,
                        platform=classification.platform,
                        email_subject=email.subject,
                    )
            
            except Exception as e:
                log_to_db(client, internal_id, "ERROR", f"Error persisting: {e}", "persistence")
                stats["errors"] += 1

            if i % 5 == 0:
                progress = int((i / len(new_emails)) * 100)
                update_pipeline_step(client, step_run_id, "persistence", "running", progress=progress)

        mark_raw_emails_processed(client, [e.email_id for e in new_emails])
        update_pipeline_step(client, step_run_id, "persistence", "success", progress=100)

        log_to_db(
            client, internal_id, "INFO",
            f"Complete: {stats['added']} added, {stats['updated']} updated, {stats['errors']} errors",
            "general"
        )
        return stats

    except Exception as e:
        log_to_db(client, internal_id, "ERROR", f"Pipeline failed at '{current_step}': {e}", current_step)
        update_pipeline_step(client, step_run_id, current_step, "failed", message=str(e))
        raise


# ══════════════════════════════════════════════════════════════
# Helper Functions (User-Scoped)
# ══════════════════════════════════════════════════════════════

def log_to_db(client, run_id, level, msg, step):
    """Write log directly to pipeline_run_logs table."""
    if not run_id:
        return
    try:
        client.table("pipeline_run_logs").insert({
            "run_id": run_id,
            "step_name": step,
            "level": level.upper(),
            "message": msg
        }).execute()
    except Exception as e:
        logger.error(f"Failed to write log: {e}")


def get_existing_email_ids_for_user(client, user_id) -> set:
    """Get existing email IDs for specific user."""
    result = client.table("raw_emails").select("email_id").eq("user_id", user_id).execute()
    return {row["email_id"] for row in result.data}


def get_unprocessed_emails_for_user(client, user_id, limit=50):
    """Get unprocessed emails for specific user."""
    result = client.table("raw_emails").select("*").eq(
        "user_id", user_id
    ).eq(
        "is_processed", False
    ).limit(limit).execute()
    
    # Convert to Email objects (assuming you have an Email model)
    from models import Email
    return [Email(**row) for row in result.data]


def insert_raw_email_with_user(client, user_id, email):
    """Insert raw email with user_id."""
    client.table("raw_emails").insert({
        "user_id": user_id,  # ← Add user_id
        "email_id": email.email_id,
        "thread_id": email.thread_id,
        "subject": email.subject,
        "sender": email.sender,
        "sender_email": email.sender_email,
        "body_preview": email.body_preview[:800],
        "email_date": str(email.email_date),
        "gmail_link": email.gmail_link,
        "raw_headers": email.raw_headers or {},
    }).execute()


def send_notification_for_user(user, **kwargs):
    """Send Telegram notification using user's credentials."""
    if not user.get('telegram_enabled'):
        return
    
    # Override global settings with user's settings
    import config
    original_token = config.settings.telegram_bot_token
    original_chat = config.settings.telegram_chat_id
    
    try:
        config.settings.telegram_bot_token = user.get('telegram_bot_token')
        config.settings.telegram_chat_id = user.get('telegram_chat_id')
        send_notification(**kwargs)
    finally:
        # Restore global settings
        config.settings.telegram_bot_token = original_token
        config.settings.telegram_chat_id = original_chat
