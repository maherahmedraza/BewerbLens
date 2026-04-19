from __future__ import annotations

from typing import Any

from loguru import logger


def categorize_errors(messages: list[str]) -> dict[str, int]:
    categories: dict[str, int] = {}

    for message in messages:
        lowered = str(message).lower()
        if not lowered:
            category = "unknown"
        elif "gmail" in lowered or "oauth" in lowered or "refresh token" in lowered:
            category = "gmail"
        elif "gemini" in lowered or "classification" in lowered or "api key" in lowered:
            category = "ai"
        elif "telegram" in lowered or "bot" in lowered or "chat_id" in lowered:
            category = "telegram"
        elif "cancel" in lowered:
            category = "cancelled"
        elif "supabase" in lowered or "database" in lowered or "sql" in lowered:
            category = "database"
        else:
            category = "other"

        categories[category] = categories.get(category, 0) + 1

    return categories


def record_usage_metrics(
    client: Any,
    *,
    user_id: str,
    run_id: str | None,
    recorded_for: str,
    emails_processed: int,
    gmail_api_calls: int,
    gmail_remaining_quota_estimate: int | None,
    ai_requests: int,
    ai_input_tokens_est: int,
    ai_output_tokens_est: int,
    ai_estimated_cost_usd: float,
    telegram_notifications_sent: int,
    telegram_notifications_failed: int,
    success_count: int,
    failure_count: int,
    error_categories: dict[str, int] | None,
    sync_status: str,
) -> None:
    payload = {
        "user_id": user_id,
        "run_id": run_id,
        "recorded_for": recorded_for,
        "emails_processed": max(emails_processed, 0),
        "gmail_api_calls": max(gmail_api_calls, 0),
        "gmail_remaining_quota_estimate": gmail_remaining_quota_estimate,
        "ai_requests": max(ai_requests, 0),
        "ai_input_tokens_est": max(ai_input_tokens_est, 0),
        "ai_output_tokens_est": max(ai_output_tokens_est, 0),
        "ai_estimated_cost_usd": round(max(ai_estimated_cost_usd, 0.0), 6),
        "telegram_notifications_sent": max(telegram_notifications_sent, 0),
        "telegram_notifications_failed": max(telegram_notifications_failed, 0),
        "success_count": max(success_count, 0),
        "failure_count": max(failure_count, 0),
        "error_categories": error_categories or {},
        "sync_status": sync_status,
    }

    try:
        if run_id:
            client.table("usage_metrics").upsert(payload, on_conflict="run_id").execute()
        else:
            client.table("usage_metrics").insert(payload).execute()
    except Exception as error:
        logger.warning(f"Failed to persist usage metrics: {error}")
