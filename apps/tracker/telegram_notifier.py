# ╔══════════════════════════════════════════════════════════════╗
# ║  Telegram Notifier — Status notifications                   ║
# ║                                                             ║
# ║  Fixes applied:                                             ║
# ║  #12 — datetime.utcnow() replaced with timezone-aware now() ║
# ║  #15 — Markdown special chars escaped to prevent breakage   ║
# ║  #16 — action param is now NotificationAction enum          ║
# ╚══════════════════════════════════════════════════════════════╝

import re
from datetime import datetime, timezone

import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_fixed

from config import settings
from models import NotificationAction, PipelineRunReport

STATUS_EMOJI: dict[str, str] = {
    "Applied": "📝",
    "Rejected": "❌",
    "Positive Response": "🎉",
    "Interview": "🤝",
    "Offer": "🏆",
}

def send_run_report_for_user(user: dict, report: PipelineRunReport) -> bool:
    """
    Sends a consolidated run report via Telegram.
    """
    if not settings.telegram_enabled or not user.get("telegram_enabled"):
        return False

    chat_id = user.get("telegram_chat_id") or settings.telegram_chat_id
    if not settings.telegram_bot_token or not chat_id:
        logger.warning("Telegram report failed: bot_token or chat_id is missing")
        return False

    # Format the report
    duration_min = report.duration_seconds / 60
    
    status_summary = ""
    for status, count in report.status_counts.items():
        emoji = STATUS_EMOJI.get(status, "📌")
        status_summary += f"{emoji} *{status}:* {count}\n"

    # Limit lists to prevent massive messages
    added_str = ", ".join(report.added_companies[:10])
    if len(report.added_companies) > 10:
        added_str += f" (+{len(report.added_companies) - 10} more)"
    
    updated_str = ", ".join(report.updated_companies[:10])
    if len(report.updated_companies) > 10:
        updated_str += f" (+{len(report.updated_companies) - 10} more)"

    text = (
        f"📊 *Pipeline Run Report*\n"
        f"📧 *User:* {_escape_md(report.user_email)}\n"
        f"🏷️ *Run:* {_escape_md(report.run_label)}\n"
        f"⏱️ *Duration:* {duration_min:.1f} min\n\n"
        f"✅ *New:* {report.added}\n"
        f"🔄 *Updated:* {report.updated}\n"
        f"⏭️ *Skipped:* {report.skipped}\n"
        f"❌ *Errors:* {report.errors}\n\n"
        f"{status_summary}\n"
    )

    if report.added_companies:
        text += f"🆕 *Added:* {added_str}\n"
    if report.updated_companies:
        text += f"🆙 *Updated:* {updated_str}\n"
    
    if report.error_messages:
        text += f"\n⚠️ *Errors:* {', '.join(report.error_messages[:3])}"

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }

    try:
        _post_to_telegram(url, payload)
        logger.bind(user=report.user_email, run=report.run_label).info("Consolidated Telegram report sent")
        return True
    except Exception as error:
        logger.bind(error=str(error)).error("Failed to send consolidated report")
        return False

# Telegram Markdown v1 special characters that break message rendering
_MD_SPECIAL = re.compile(r"([*_`\[\]])")


def _escape_md(text: str) -> str:
    """
    Escapes Telegram Markdown v1 special characters in user-sourced strings.
    Fixes: review issue #15 — Markdown injection from company names / job titles.

    Example: "Acme *Corp*" → "Acme \*Corp\*"
    """
    if not text:
        return ""
    return _MD_SPECIAL.sub(r"\\\1", str(text))


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    reraise=False,  # notification failure must never crash the pipeline
)
def _post_to_telegram(url: str, payload: dict) -> None:
    """
    Sends a single HTTP request to the Telegram Bot API.
    Retried up to 3 times with 2s wait between attempts.
    reraise=False: if all attempts fail we log and move on.
    """
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()


def send_notification(
    action: NotificationAction,
    company_name: str,
    job_title: str = "Not Specified",
    platform: str = "Direct",
    status: str = "Applied",
    email_subject: str = "",
    notes: str = "",
    date_applied: str = "",
) -> bool:
    """
    Sends a notification via Telegram.
    Only runs if telegram_enabled=True in config.

    action: NotificationAction enum (ADDED | UPDATED | ERROR).
    Returns True if sent successfully, False if disabled or failed.
    """
    if not settings.telegram_enabled:
        return False

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram enabled but bot_token or chat_id is missing")
        return False

    emoji = STATUS_EMOJI.get(status, "📌")

    # Escape all user-sourced strings before embedding in Markdown
    safe_company = _escape_md(company_name)
    safe_title = _escape_md(job_title)
    safe_platform = _escape_md(platform)
    safe_subject = _escape_md(email_subject[:80])
    safe_notes = _escape_md(notes[:120])
    safe_date = _escape_md(date_applied)

    if action == NotificationAction.ADDED:
        text = (
            f"{emoji} *New Application Tracked*\n"
            f"🏢 *Company:* {safe_company}\n"
            f"💼 *Role:* {safe_title}\n"
            f"🔗 *Platform:* {safe_platform}\n"
            f"📅 *Date:* {safe_date}\n"
            f"📧 {safe_subject}"
        )
    elif action == NotificationAction.UPDATED:
        text = (
            f"{emoji} *Status Update*\n"
            f"🏢 *Company:* {safe_company}\n"
            f"💼 *Role:* {safe_title}\n"
            f"📋 *Update:* {safe_notes}"
        )
    elif action == NotificationAction.ERROR:
        # Dedicated error template — fixes the misleading crash notification
        # from scheduler.py (review issue — scheduler passed action="added" for errors)
        text = (
            f"⚠️ *Pipeline Error*\n"
            f"📛 *Error:* {safe_company}\n"
            f"🔍 *Detail:* {safe_title}\n"
            f"🕐 *Time:* {_escape_md(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))}"
        )
    else:
        logger.warning(f"Unknown notification action: {action}")
        return False

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }

    try:
        _post_to_telegram(url, payload)
        logger.bind(company=company_name, action=action).info("Telegram notification sent")
        return True
    except Exception as error:
        # All retries exhausted — log and continue, never crash pipeline
        logger.bind(error=str(error)).error("Telegram notification failed after 3 attempts")
        return False
