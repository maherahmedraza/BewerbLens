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
from models import NotificationAction

STATUS_EMOJI: dict[str, str] = {
    "Applied": "📝",
    "Rejected": "❌",
    "Positive Response": "🎉",
    "Interview": "🤝",
    "Offer": "🏆",
}

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


def _build_message(
    action: NotificationAction,
    company_name: str,
    job_title: str = "Not Specified",
    platform: str = "Direct",
    status: str = "Applied",
    email_subject: str = "",
    notes: str = "",
    date_applied: str = "",
) -> str | None:
    """
    Builds a Telegram-formatted notification message.
    Returns the message text or None if the action is unknown.
    """
    emoji = STATUS_EMOJI.get(status, "📌")

    safe_company = _escape_md(company_name)
    safe_title = _escape_md(job_title)
    safe_platform = _escape_md(platform)
    safe_subject = _escape_md(email_subject[:80])
    safe_notes = _escape_md(notes[:120])
    safe_date = _escape_md(date_applied)

    if action == NotificationAction.ADDED:
        return (
            f"{emoji} *New Application Tracked*\n"
            f"🏢 *Company:* {safe_company}\n"
            f"💼 *Role:* {safe_title}\n"
            f"🔗 *Platform:* {safe_platform}\n"
            f"📅 *Date:* {safe_date}\n"
            f"📧 {safe_subject}"
        )
    elif action == NotificationAction.UPDATED:
        return (
            f"{emoji} *Status Update*\n"
            f"🏢 *Company:* {safe_company}\n"
            f"💼 *Role:* {safe_title}\n"
            f"📋 *Update:* {safe_notes}"
        )
    elif action == NotificationAction.ERROR:
        return (
            f"⚠️ *Pipeline Error*\n"
            f"📛 *Error:* {safe_company}\n"
            f"🔍 *Detail:* {safe_title}\n"
            f"🕐 *Time:* {_escape_md(datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'))}"
        )

    logger.warning(f"Unknown notification action: {action}")
    return None


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
    Sends a notification via Telegram using global config credentials.
    Only runs if telegram_enabled=True in config.

    action: NotificationAction enum (ADDED | UPDATED | ERROR).
    Returns True if sent successfully, False if disabled or failed.
    """
    if not settings.telegram_enabled:
        return False

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram enabled but bot_token or chat_id is missing")
        return False

    text = _build_message(
        action=action, company_name=company_name, job_title=job_title,
        platform=platform, status=status, email_subject=email_subject,
        notes=notes, date_applied=date_applied,
    )
    if not text:
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
