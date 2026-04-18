# ╔══════════════════════════════════════════════════════════════╗
# ║  COMPLETE Multi-User Tracker Integration                    ║
# ║                                                             ║
# ║  This file replaces tracker.py with FULL multi-user support ║
# ║  • Fetches Gmail credentials per user_id                    ║
# ║  • Applies email filters per user_id                        ║
# ║  • Writes applications with user_id                         ║
# ║  • Sends consolidated Telegram report at end of run         ║
# ╚══════════════════════════════════════════════════════════════╝

import time as _time
from datetime import date
from typing import Optional

from loguru import logger

from classifier_factory import get_classifier
from fuzzy_matcher import ApplicationMatcher, upsert_application_fixed
from gmail_service import fetch_emails_for_user, get_gmail_service_for_user
from models import (
    CLASSIFICATION_TO_STATUS,
    PIPELINE_STAGE_ORDER,
    AnalysisStageStats,
    Classification,
    EmailMetadata,
    IngestionStageStats,
    PersistenceStageStats,
    PipelineRunReport,
    PipelineStage,
)
from pre_filter import apply_user_filters
from supabase_service import (
    get_client,
    mark_raw_emails_processed,
    update_heartbeat,
    update_pipeline_step,
)


class PipelineCancelledError(RuntimeError):
    """Raised when a run receives a cooperative cancellation request."""


def run_pipeline_multiuser(
    user_id: str,
    since_date: Optional[date] = None,
    run_id: str = "manual",
    internal_id: Optional[str] = None,
    start_stage: str | PipelineStage = PipelineStage.INGESTION,
) -> dict:
    """
    Execute the pipeline for a user, optionally starting from a specific stage.

    Stage outputs are persisted into pipeline_run_steps.stats so a later resume or
    stage rerun can continue from persisted artifacts instead of relying on in-memory
    state within a single worker invocation.

    Telegram: A single consolidated report is sent at the end of the run
    instead of individual per-job notifications.
    """
    client = get_client()
    stats = {"added": 0, "updated": 0, "skipped": 0, "errors": 0}
    step_run_id = internal_id or run_id
    stage_to_start = _parse_stage(start_stage)
    current_step = stage_to_start.value
    run_start_time = _time.monotonic()

    log_to_db(client, internal_id, "INFO", f"Fetching profile for user {user_id}", "setup")

    try:
        user_profile = client.table("user_profiles").select("*").eq("id", user_id).single().execute()
        if not user_profile.data:
            raise ValueError(f"User profile not found: {user_id}")

        user = user_profile.data
        log_to_db(client, internal_id, "INFO", f"User: {user['email']} | Region: {user['region']}", "setup")
    except Exception as error:
        log_to_db(client, internal_id, "ERROR", f"Failed to load user profile: {error}", "setup")
        raise

    matcher = ApplicationMatcher(
        company_threshold=0.85,
        job_threshold=0.75,
        composite_threshold=0.80,
    )

    try:
        for stage in _stages_from(stage_to_start):
            current_step = stage.value
            _set_current_phase(client, internal_id, stage)
            _ensure_run_not_cancelled(client, internal_id)

            if stage == PipelineStage.INGESTION:
                ingestion_stats = _run_ingestion_stage(
                    client=client,
                    user=user,
                    user_id=user_id,
                    since_date=since_date,
                    run_id=step_run_id,
                    internal_id=internal_id,
                )
                if internal_id:
                    update_heartbeat(client, internal_id)
                if not ingestion_stats.email_ids:
                    _skip_remaining_stages(
                        client,
                        step_run_id,
                        PipelineStage.INGESTION,
                        "No emails to process for this run.",
                    )
                    return stats

            elif stage == PipelineStage.ANALYSIS:
                analysis_stats = _run_analysis_stage(
                    client=client,
                    user_id=user_id,
                    run_id=step_run_id,
                    internal_id=internal_id,
                )
                if internal_id:
                    update_heartbeat(client, internal_id)
                if not analysis_stats.classifications:
                    update_pipeline_step(
                        client,
                        step_run_id,
                        PipelineStage.PERSISTENCE.value,
                        "skipped",
                        message="No classifications produced by analysis.",
                    )
                    return stats

            elif stage == PipelineStage.PERSISTENCE:
                persistence_stats = _run_persistence_stage(
                    client=client,
                    user=user,
                    user_id=user_id,
                    run_id=step_run_id,
                    internal_id=internal_id,
                    matcher=matcher,
                )
                stats.update(
                    {
                        "added": persistence_stats.added,
                        "updated": persistence_stats.updated,
                        "skipped": persistence_stats.skipped,
                        "errors": persistence_stats.errors,
                    }
                )

        run_duration = _time.monotonic() - run_start_time
        log_to_db(
            client,
            internal_id,
            "INFO",
            f"Complete: {stats['added']} added, {stats['updated']} updated, {stats['errors']} errors",
            "general",
        )

        # ── Consolidated Telegram report ──────────────────────
        if user.get("telegram_enabled") and hasattr(persistence_stats, "report"):
            _send_consolidated_report(
                user=user,
                report=persistence_stats.report,
                run_label=run_id,
                user_email=user.get("email", ""),
                duration_seconds=run_duration,
            )

        return stats

    except PipelineCancelledError as error:
        message = str(error) or "Cancelled by user"
        log_to_db(client, internal_id, "WARNING", message, current_step)
        update_pipeline_step(client, step_run_id, current_step, "failed", message=message)
        raise
    except Exception as error:
        log_to_db(client, internal_id, "ERROR", f"Pipeline failed at '{current_step}': {error}", current_step)
        update_pipeline_step(client, step_run_id, current_step, "failed", message=str(error))
        raise


def _run_ingestion_stage(
    client,
    user: dict,
    user_id: str,
    since_date: Optional[date],
    run_id: str,
    internal_id: Optional[str],
) -> IngestionStageStats:
    update_pipeline_step(
        client,
        run_id,
        PipelineStage.INGESTION.value,
        "running",
        progress=0,
        message="Starting email ingestion",
    )
    log_to_db(client, internal_id, "INFO", "Starting email ingestion", PipelineStage.INGESTION.value)

    existing_ids_snapshot = get_existing_email_ids_for_user(client, user_id)
    service = get_gmail_service_for_user(user, db_client=client)
    if not service:
        raise RuntimeError(f"Failed to initialize Gmail for user {user_id}")

    new_emails = fetch_emails_for_user(
        service,
        user_id=user_id,
        since_date=since_date,
        existing_ids=existing_ids_snapshot,
    )
    fetched_count = len(new_emails)
    log_to_db(client, internal_id, "INFO", f"Fetched {fetched_count} new emails", PipelineStage.INGESTION.value)

    pending_emails = get_unprocessed_emails_for_user(client, user_id, limit=50)
    recovered_count = 0
    if pending_emails:
        new_ids = {email.email_id for email in new_emails}
        recovered_emails = [email for email in pending_emails if email.email_id not in new_ids]
        recovered_count = len(recovered_emails)
        if recovered_count:
            log_to_db(
                client,
                internal_id,
                "INFO",
                f"Recovery: {recovered_count} pending",
                PipelineStage.INGESTION.value,
            )
            new_emails.extend(recovered_emails)

    if not new_emails:
        stage_stats = IngestionStageStats()
        update_pipeline_step(
            client,
            run_id,
            PipelineStage.INGESTION.value,
            "success",
            progress=100,
            message="No new emails found.",
            stats=stage_stats.model_dump(mode="json"),
        )
        return stage_stats

    # Capture all email IDs BEFORE filtering so we can mark filtered-out
    # recovery emails as processed (prevents them from re-appearing every run)
    all_email_ids_before_filter = [email.email_id for email in new_emails]

    new_emails, filter_stats = apply_user_filters(client, user_id, new_emails)
    log_to_db(
        client,
        internal_id,
        "INFO",
        f"Filtered: {filter_stats.passed}/{filter_stats.total} emails passed user filters",
        PipelineStage.INGESTION.value,
    )

    # Mark filtered-out emails as processed so they don't loop in recovery
    if filter_stats.filtered > 0:
        passed_ids = {email.email_id for email in new_emails}
        filtered_out_ids = [eid for eid in all_email_ids_before_filter if eid not in passed_ids]
        if filtered_out_ids:
            mark_raw_emails_processed(client, filtered_out_ids)
            log_to_db(
                client,
                internal_id,
                "INFO",
                f"Marked {len(filtered_out_ids)} filtered-out emails as processed",
                PipelineStage.INGESTION.value,
            )

    for index, email in enumerate(new_emails):
        _ensure_run_not_cancelled(client, internal_id)
        insert_raw_email_with_user(client, user_id, email)
        if index % 10 == 0:
            progress = int((index / max(len(new_emails), 1)) * 100)
            update_pipeline_step(
                client,
                run_id,
                PipelineStage.INGESTION.value,
                "running",
                progress=progress,
                message=f"Stored {index + 1}/{len(new_emails)} emails",
            )

    stage_stats = IngestionStageStats(
        email_ids=[email.email_id for email in new_emails],
        total_fetched=fetched_count,
        total_recovered=recovered_count,
        total_after_filters=len(new_emails),
    )
    update_pipeline_step(
        client,
        run_id,
        PipelineStage.INGESTION.value,
        "success",
        progress=100,
        message=f"Stored {len(new_emails)} emails for downstream stages",
        stats=stage_stats.model_dump(mode="json"),
    )
    return stage_stats


def _run_analysis_stage(client, user_id: str, run_id: str, internal_id: Optional[str]) -> AnalysisStageStats:
    ingestion_stats = _load_stage_stats(client, run_id, PipelineStage.INGESTION, IngestionStageStats)
    if not ingestion_stats.email_ids:
        update_pipeline_step(
            client,
            run_id,
            PipelineStage.ANALYSIS.value,
            "skipped",
            message="No ingested email artifacts available.",
        )
        return AnalysisStageStats()

    emails = _load_raw_emails_for_ids(client, user_id, ingestion_stats.email_ids)
    if not emails:
        raise RuntimeError("Ingestion artifacts were found, but raw_emails could not be loaded.")

    update_pipeline_step(
        client,
        run_id,
        PipelineStage.ANALYSIS.value,
        "running",
        progress=0,
        message="Classifying emails",
    )
    log_to_db(client, internal_id, "INFO", f"Classifying {len(emails)} emails", PipelineStage.ANALYSIS.value)

    classifier = get_classifier()
    classifications = classifier.classify(emails)
    stage_stats = AnalysisStageStats(
        email_ids=ingestion_stats.email_ids,
        classifications=classifications,
        total_classified=len(classifications),
    )

    update_pipeline_step(
        client,
        run_id,
        PipelineStage.ANALYSIS.value,
        "success",
        progress=100,
        message=f"Classified {len(classifications)} emails",
        stats=stage_stats.model_dump(mode="json"),
    )
    log_to_db(client, internal_id, "INFO", f"Classified {len(classifications)} emails", PipelineStage.ANALYSIS.value)
    return stage_stats


def _run_persistence_stage(
    client,
    user: dict,
    user_id: str,
    run_id: str,
    internal_id: Optional[str],
    matcher: ApplicationMatcher,
) -> PersistenceStageStats:
    ingestion_stats = _load_stage_stats(client, run_id, PipelineStage.INGESTION, IngestionStageStats)
    analysis_stats = _load_stage_stats(client, run_id, PipelineStage.ANALYSIS, AnalysisStageStats)

    if not ingestion_stats.email_ids:
        update_pipeline_step(
            client,
            run_id,
            PipelineStage.PERSISTENCE.value,
            "skipped",
            message="No ingested emails available for persistence.",
        )
        return PersistenceStageStats()

    if not analysis_stats.classifications:
        raise RuntimeError("Analysis artifacts are missing; rerun analysis before persistence.")

    emails = _load_raw_emails_for_ids(client, user_id, ingestion_stats.email_ids)
    if not emails:
        raise RuntimeError("Failed to load raw email artifacts for persistence.")

    update_pipeline_step(
        client,
        run_id,
        PipelineStage.PERSISTENCE.value,
        "running",
        progress=0,
        message="Saving results",
    )
    log_to_db(client, internal_id, "INFO", "Saving to database", PipelineStage.PERSISTENCE.value)

    apps_cache = client.table("applications").select("*").eq("user_id", user_id).execute().data
    stage_stats = PersistenceStageStats(email_ids=ingestion_stats.email_ids)

    # ── Report collector — accumulates data for consolidated Telegram report ──
    report = PipelineRunReport()

    for index, (email, classification) in enumerate(zip(emails, analysis_stats.classifications)):
        _ensure_run_not_cancelled(client, internal_id)

        if classification.classification == Classification.NOT_JOB_RELATED:
            stage_stats.skipped += 1
            continue

        try:
            action = upsert_application_fixed(
                client,
                user_id,
                email,
                classification,
                apps_cache,
                matcher,
            )

            status_enum = CLASSIFICATION_TO_STATUS.get(classification.classification)
            status_value = status_enum.value if status_enum else "Applied"

            if action == "added":
                stage_stats.added += 1
                report.added_companies.append(classification.company_name)
                apps_cache = client.table("applications").select("*").eq("user_id", user_id).execute().data
                log_to_db(
                    client,
                    internal_id,
                    "INFO",
                    f"Added: {classification.company_name} / {classification.job_title}",
                    PipelineStage.PERSISTENCE.value,
                )
            else:
                stage_stats.updated += 1
                report.updated_companies.append(classification.company_name)
                log_to_db(
                    client,
                    internal_id,
                    "INFO",
                    f"Updated: {classification.company_name} / {classification.job_title}",
                    PipelineStage.PERSISTENCE.value,
                )

            # Accumulate status counts for the report
            report.status_counts[status_value] = report.status_counts.get(status_value, 0) + 1

        except Exception as error:
            log_to_db(client, internal_id, "ERROR", f"Error persisting: {error}", PipelineStage.PERSISTENCE.value)
            stage_stats.errors += 1
            report.error_messages.append(str(error)[:150])

        if index % 5 == 0:
            progress = int((index / max(len(emails), 1)) * 100)
            update_pipeline_step(
                client,
                run_id,
                PipelineStage.PERSISTENCE.value,
                "running",
                progress=progress,
                message=f"Persisted {index + 1}/{len(emails)} emails",
            )

    # Finalize report stats
    report.added = stage_stats.added
    report.updated = stage_stats.updated
    report.skipped = stage_stats.skipped
    report.errors = stage_stats.errors

    # Attach report to stage_stats for the caller to use
    stage_stats.report = report  # type: ignore[attr-defined]

    mark_raw_emails_processed(client, ingestion_stats.email_ids)
    update_pipeline_step(
        client,
        run_id,
        PipelineStage.PERSISTENCE.value,
        "success",
        progress=100,
        message=(
            f"Added {stage_stats.added}, updated {stage_stats.updated}, "
            f"skipped {stage_stats.skipped}, errors {stage_stats.errors}"
        ),
        stats=stage_stats.model_dump(mode="json"),
    )
    return stage_stats


def _parse_stage(stage: str | PipelineStage) -> PipelineStage:
    if isinstance(stage, PipelineStage):
        return stage
    return PipelineStage(stage)


def _stages_from(start_stage: PipelineStage) -> list[PipelineStage]:
    start_index = PIPELINE_STAGE_ORDER.index(start_stage)
    return list(PIPELINE_STAGE_ORDER[start_index:])


def _skip_remaining_stages(client, run_id: str, completed_stage: PipelineStage, message: str) -> None:
    completed_index = PIPELINE_STAGE_ORDER.index(completed_stage)
    for stage in PIPELINE_STAGE_ORDER[completed_index + 1 :]:
        update_pipeline_step(client, run_id, stage.value, "skipped", message=message)


def _set_current_phase(client, internal_id: Optional[str], stage: PipelineStage) -> None:
    if not internal_id:
        return
    try:
        client.table("pipeline_runs").update({"current_phase": stage.value}).eq("id", internal_id).execute()
    except Exception as error:
        logger.warning(f"Failed to update current_phase for run {internal_id}: {error}")


_cancel_check_cache: dict[str, tuple[float, bool]] = {}  # run_id → (timestamp, is_cancelled)
_CANCEL_CHECK_INTERVAL = 5.0  # seconds between DB queries


def _ensure_run_not_cancelled(client, internal_id: Optional[str]) -> None:
    if not internal_id:
        return

    import time

    now = time.monotonic()
    cached = _cancel_check_cache.get(internal_id)
    if cached:
        last_check, was_cancelled = cached
        if was_cancelled:
            raise PipelineCancelledError("Run cancelled by user.")
        if now - last_check < _CANCEL_CHECK_INTERVAL:
            return

    result = client.table("pipeline_runs").select("status").eq("id", internal_id).limit(1).execute()
    if not result.data:
        return

    status = result.data[0].get("status")
    is_cancelled = status in {"cancelling", "cancelled"}
    _cancel_check_cache[internal_id] = (now, is_cancelled)

    if is_cancelled:
        raise PipelineCancelledError("Run cancelled by user.")


def _load_stage_stats(client, run_id: str, stage: PipelineStage, model_type):
    result = (
        client.table("pipeline_run_steps")
        .select("stats")
        .eq("run_id", run_id)
        .eq("step_name", stage.value)
        .limit(1)
        .execute()
    )
    raw_stats = result.data[0].get("stats") if result.data else {}
    return model_type.model_validate(raw_stats or {})


def _load_raw_emails_for_ids(client, user_id: str, email_ids: list[str]) -> list[EmailMetadata]:
    if not email_ids:
        return []

    result = (
        client.table("raw_emails")
        .select("*")
        .eq("user_id", user_id)
        .in_("email_id", email_ids)
        .execute()
    )
    rows_by_email_id = {row["email_id"]: row for row in result.data or []}

    emails: list[EmailMetadata] = []
    for email_id in email_ids:
        row = rows_by_email_id.get(email_id)
        if not row:
            continue
        emails.append(
            EmailMetadata(
                email_id=row.get("email_id", ""),
                thread_id=row.get("thread_id", ""),
                subject=row.get("subject", ""),
                sender=row.get("sender", ""),
                sender_email=row.get("sender_email", ""),
                date=row.get("email_date") or row.get("date"),
                body=row.get("body_preview", "") or row.get("body", ""),
            )
        )
    return emails


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
            "message": msg,
        }).execute()
    except Exception as error:
        logger.error(f"Failed to write log: {error}")


def get_existing_email_ids_for_user(client, user_id) -> set:
    """Get existing email IDs for specific user."""
    result = client.table("raw_emails").select("email_id").eq("user_id", user_id).execute()
    return {row["email_id"] for row in result.data}


def get_unprocessed_emails_for_user(client, user_id, limit=50):
    """Get unprocessed emails for specific user."""
    result = (
        client.table("raw_emails")
        .select("*")
        .eq("user_id", user_id)
        .eq("is_processed", False)
        .limit(limit)
        .execute()
    )

    emails = []
    for row in result.data:
        try:
            emails.append(
                EmailMetadata(
                    email_id=row.get("email_id", ""),
                    thread_id=row.get("thread_id", ""),
                    subject=row.get("subject", ""),
                    sender=row.get("sender", ""),
                    sender_email=row.get("sender_email", ""),
                    date=row.get("email_date") or row.get("date"),
                    body=row.get("body_preview", "") or row.get("body", ""),
                )
            )
        except Exception:
            pass
    return emails


def insert_raw_email_with_user(client, user_id, email):
    """Insert raw email with user_id (upsert to handle re-runs)."""
    client.table("raw_emails").upsert(
        {
            "user_id": user_id,
            "email_id": email.email_id,
            "thread_id": email.thread_id,
            "subject": email.subject,
            "sender": email.sender,
            "sender_email": email.sender_email,
            "body_preview": email.body[:800],
            "email_date": str(email.date),
            "gmail_link": email.gmail_link,
        },
        on_conflict="email_id",
    ).execute()


def _send_consolidated_report(
    user: dict,
    report: PipelineRunReport,
    run_label: str,
    user_email: str,
    duration_seconds: float,
) -> None:
    """Send a single consolidated Telegram report at end of pipeline run."""
    report.run_label = run_label
    report.user_email = user_email
    report.duration_seconds = duration_seconds

    from telegram_notifier import send_run_report_for_user

    try:
        send_run_report_for_user(user, report)
    except Exception as error:
        logger.bind(error=str(error)).error("Failed to send consolidated Telegram report")
