# ╔══════════════════════════════════════════════════════════════╗
# ║  Telegram Notifier — Status notifications                   ║
# ║  Replaces the "Build Notification" and                      ║
# ║  "Send Telegram" nodes from the n8n workflow.               ║
# ╚══════════════════════════════════════════════════════════════╝

import requests
from loguru import logger

from config import settings

# Emojis per status, same as in the n8n workflow
STATUS_EMOJI: dict[str, str] = {
    "Applied": "📝",
    "Rejected": "❌",
    "Positive Response": "🎉",
    "Interview": "🤝",
    "Offer": "🏆",
}


def send_notification(
    action: str,
    company_name: str,
    job_title: str,
    platform: str,
    status: str,
    email_subject: str = "",
    notes: str = "",
    date_applied: str = "",
) -> bool:
    """
    Sends a notification via Telegram.
    Only runs if telegram_enabled is True in the configuration.

    Returns True if sent successfully, False if error or disabled.
    """
    if not settings.telegram_enabled:
        return False

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram enabled but credentials are missing")
        return False

    emoji = STATUS_EMOJI.get(status, "📌")

    # Build message based on whether it is a new application or update
    if action == "added":
        text = (
            f"{emoji} *New Application Tracked*\n"
            f"🏢 *Company:* {company_name}\n"
            f"💼 *Role:* {job_title}\n"
            f"🔗 *Platform:* {platform}\n"
            f"📅 *Date:* {date_applied}\n"
            f"📧 {email_subject[:80]}"
        )
    elif action == "updated":
        text = (
            f"{emoji} *Status Update*\n"
            f"🏢 *Company:* {company_name}\n"
            f"💼 *Role:* {job_title}\n"
            f"📋 *Update:* {notes[:120]}"
        )
    else:
        return False

    # Send via Telegram Bot API
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": settings.telegram_chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.bind(company=company_name, action=action).info("Telegram notification sent")
        return True
    except requests.RequestException as error:
        logger.bind(error=str(error)).error("Telegram notification failed")
        return False
