#!/usr/bin/env python3
# ╔══════════════════════════════════════════════════════════════╗
# ║  BewerbLens — Main Pipeline                                   ║
# ║  Orchestrates the entire flow: ingest → classify →           ║
# ║  deduplicate → store → notify.                              ║
# ║                                                             ║
# ║  This file replaces the entire n8n canvas (~30 nodes)       ║
# ║  with a linear pipeline of ~100 lines of logic.             ║
# ╚══════════════════════════════════════════════════════════════╝

import sys
from datetime import date, timedelta

from loguru import logger

from config import settings
from gemini_classifier import classify_emails
from gmail_service import fetch_emails
from models import CLASSIFICATION_TO_STATUS, ProcessingLog
from pre_filter import apply_pre_filters
from supabase_service import (
    get_existing_thread_ids,
    get_last_checkpoint,
    insert_raw_email,
    log_processing,
    upsert_application,
    get_client,
)
from telegram_notifier import send_notification

# ── Configure logging with loguru ────────────────────────────
# Clean, structured format instead of n8n's console.log mess
logger.remove()
logger.add(
    sys.stderr,
    format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{message}</cyan> <dim>{extra}</dim>",
    level="INFO",
)
logger.add(
    "tracker.log",
    rotation="10 MB",
    retention="30 days",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message} {extra}",
    level="DEBUG",
)


def run_pipeline(since_date: date = None) -> dict:
    """
    Runs the complete email tracking pipeline.
    If since_date is provided, it overrides the database checkpoint.

    The flow is identical to the n8n workflow but with key improvements:
    1. Incremental checkpoint (only looks for new emails)
    2. Native deduplication via Postgres
    3. Typed validation with Pydantic
    4. Structured logging with loguru

    Returns a dictionary with execution statistics.
    """
    stats = {
        "fetched": 0,
        "after_prefilter": 0,
        "after_dedup": 0,
        "classified": 0,
        "added": 0,
        "updated": 0,
        "skipped": 0,
        "errors": 0,
    }

    logger.info("=" * 60)
    logger.info("BewerbLens - Starting pipeline")
    logger.info("=" * 60)

    # ── STEP 1: Get checkpoint from Supabase ────────────────
    client = get_client()
    # Override with since_date if provided, else query DB
    if since_date:
        fetch_from = since_date
        logger.info(f"Using forced backfill start date: {fetch_from.isoformat()}")
    else:
        checkpoint_date = get_last_checkpoint(client)
        # Go back 2 days as a safety margin
        fetch_from = checkpoint_date - timedelta(days=2)
        logger.info(f"Fetching emails since: {fetch_from.isoformat()}")

    # ── STEP 2: Fetch emails from Gmail ──────────────────────
    # In n8n: "Build Gmail Queries" + "Fetch Emails (Per Month)" (4 calls)
    # Here: a single call with after: fetch_from
    raw_emails = fetch_emails(fetch_from)
    stats["fetched"] = len(raw_emails)
    logger.info(f"Fetched {len(raw_emails)} emails from Gmail")

    if not raw_emails:
        logger.info("No emails found - pipeline complete")
        return stats

    # ── STEP 2.5: Ingest raw emails into Bronze layer ────────
    # v2.0: Store raw emails before processing for audit trail
    bronze_count = 0
    for email in raw_emails:
        if insert_raw_email(client, email):
            bronze_count += 1
    logger.info(f"Bronze layer: {bronze_count}/{len(raw_emails)} raw emails ingested")

    # ── STEP 3: Pre-filter emails ───────────────────────────
    # In n8n: "Pre-Filter" node with 5 JavaScript filters
    # Here: same logic but with O(1) sets and typed code
    filtered_emails, filter_stats = apply_pre_filters(raw_emails)
    stats["after_prefilter"] = len(filtered_emails)
    logger.info(f"Pre-filter: {len(filtered_emails)}/{len(raw_emails)} passed")

    if not filtered_emails:
        logger.info("All emails filtered - pipeline complete")
        return stats

    # ── STEP 4: Deduplicate against database ─────────────────
    # In n8n: "Deduplicate Emails" used an in-memory Map
    # Here: we query existing thread_ids from Supabase (persistent)
    existing_threads = get_existing_thread_ids(client)
    new_emails = [
        email for email in filtered_emails
        if email.thread_id not in existing_threads
    ]
    stats["after_dedup"] = len(new_emails)

    # Also count those that are new threads but email already processed
    logger.info(
        f"Dedup: {len(new_emails)} new threads "
        f"({len(filtered_emails) - len(new_emails)} already in DB)"
    )

    # Solo clasificar emails nuevos — los existentes ya están en la DB
    # Las actualizaciones de estado llegan como nuevos threads (nuevo email_id)
    emails_to_classify = new_emails

    if not emails_to_classify:
        logger.info("No new emails to classify — pipeline complete")
        return stats

    logger.info(f"Sending {len(emails_to_classify)} new emails to Gemini for classification")

    # ── STEP 5: Classify with Gemini ─────────────────────────
    # In n8n: "Build Gemini Batches" -> "Loop Over Batches" -> "Gemini API Call"
    #         -> "Expand Results" -> "Classification Filter" (5 nodes, complex loop)
    # Here: a single function with internal batching
    classifications = classify_emails(emails_to_classify)
    stats["classified"] = len(classifications)

    # ── STEP 6: Process results ──────────────────────────────
    # In n8n: "Read Applications Sheet" -> "Dedup Engine" -> "Route: Add/Update"
    #         -> "Add New Row" / "Update Existing Row" (4+ nodes)
    # Here: a loop with upsert_application that handles everything
    min_confidence = settings.min_confidence

    for email, classification in zip(emails_to_classify, classifications):
        status_enum = CLASSIFICATION_TO_STATUS.get(classification.classification)

        # Confidence filter (same as n8n's "Classification Filter" node)
        is_valid_job = (
            status_enum is not None
            and classification.confidence >= min_confidence
        )

        if not is_valid_job:
            stats["skipped"] += 1
            # Log for auditing
            log_processing(client, ProcessingLog(
                thread_id=email.thread_id,
                email_subject=email.subject[:150],
                classification_result=classification.classification.value,
                error_message=f"Skipped: conf={classification.confidence:.2f}, status={status_enum}",
            ))
            continue

        try:
            # Upsert to Supabase (handles add/update/skip internally)
            action = upsert_application(client, email, classification)

            if action == "added":
                stats["added"] += 1
            elif action == "updated":
                stats["updated"] += 1
            else:
                stats["skipped"] += 1

            # Notify if added or updated
            if action in ("added", "updated"):
                send_notification(
                    action=action,
                    company_name=classification.company_name,
                    job_title=classification.job_title,
                    platform=classification.platform,
                    status=status_enum.value if status_enum else "",
                    email_subject=email.subject,
                    date_applied=email.date.isoformat(),
                    notes=classification.reasoning,
                )

            # Audit log
            log_processing(client, ProcessingLog(
                thread_id=email.thread_id,
                email_subject=email.subject[:150],
                classification_result=f"{classification.classification.value} -> {action}",
            ))

        except Exception as error:
            stats["errors"] += 1
            logger.bind(
                email_id=email.email_id,
                error=str(error)
            ).error("Failed to process application")
            log_processing(client, ProcessingLog(
                thread_id=email.thread_id,
                email_subject=email.subject[:150],
                error_message=str(error)[:300],
            ))

    # ── Final summary ────────────────────────────────────────
    logger.info("=" * 60)
    logger.info("Pipeline complete")
    logger.info(f"   Fetched:      {stats['fetched']}")
    logger.info(f"   Pre-filtered: {stats['after_prefilter']}")
    logger.info(f"   New threads:  {stats['after_dedup']}")
    logger.info(f"   Classified:   {stats['classified']}")
    logger.info(f"   Added:        {stats['added']}")
    logger.info(f"   Updated:      {stats['updated']}")
    logger.info(f"   Skipped:      {stats['skipped']}")
    logger.info(f"   Errors:       {stats['errors']}")
    logger.info("=" * 60)

    return stats


if __name__ == "__main__":
    import argparse
    import traceback

    parser = argparse.ArgumentParser(description="BewerbLens — Main Pipeline")
    parser.add_argument(
        "--since",
        type=str,
        help="Forced backfill start date (YYYY-MM-DD)",
        default=None
    )
    args = parser.parse_args()

    # Parse since_date if provided
    forced_date = None
    if args.since:
        try:
            forced_date = date.fromisoformat(args.since)
        except ValueError:
            logger.error(f"Invalid date format: {args.since}. Use YYYY-MM-DD")
            sys.exit(1)

    try:
        result = run_pipeline(since_date=forced_date)
        # Exit code 0 = success, 1 = errors
        sys.exit(0 if result["errors"] == 0 else 1)
    except Exception as fatal_error:
        logger.bind(error=str(fatal_error)).critical("Pipeline crashed")
        traceback.print_exc()
        sys.exit(2)
