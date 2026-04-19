# ╔══════════════════════════════════════════════════════════════╗
# ║  Telegram Notifier — Status & Run Notifications             ║
# ║                                                             ║
# ║  Features:                                                  ║
# ║  • Consolidated Pipeline Run Reports                        ║
# ║  • Thread-safe per-user Telegram credentials                ║
# ║  • Markdown escaping for all user-sourced strings          ║
# ║  • Legacy per-item alerts for critical errors               ║
# ╚══════════════════════════════════════════════════════════════╝

import re
import requests
from datetime import datetime, timezone
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

# Telegram Markdown v1 special characters that break message rendering
_MD_SPECIAL = re.compile(r"([*_`\[\]])")


def _escape_md(text: str) -> str:
    """Escapes Telegram Markdown v1 special characters."""
    if not text:
        return ""
    return _MD_SPECIAL.sub(r"\\\1", str(text))


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    reraise=False,
)
def _post_to_telegram(url: str, payload: dict) -> None:
    """Sends a single HTTP request to the Telegram Bot API."""
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()


# ══════════════════════════════════════════════════════════════
# Consolidated Run Report
# ══════════════════════════════════════════════════════════════

def _format_duration(seconds: float) -> str:
    """Format seconds into a human-readable duration string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    minutes = int(seconds // 60)
    remaining = int(seconds % 60)
    if minutes < 60:
        return f"{minutes}m {remaining}s"
    hours = int(minutes // 60)
    remaining_min = minutes % 60
    return f"{hours}h {remaining_min}m"


def _build_report_message(report: PipelineRunReport) -> str:
    """Builds a consolidated end-of-run Telegram report message."""
    has_errors = report.errors > 0
    total_processed = report.added + report.updated + report.skipped

    # Header
    status_icon = "⚠️" if has_errors else "✅"
    lines: list[str] = [
        f"{status_icon} *BewerbLens Pipeline Report*",
        "━━━━━━━━━━━━━━━━━━━━━━━━",
        "",
    ]

    # Run metadata
    if report.run_label:
        lines.append(f"🔄 *Run:* {_escape_md(report.run_label)}")
    lines.append(f"⏱️ *Duration:* {_format_duration(report.duration_seconds)}")
    if report.user_email:
        lines.append(f"👤 *User:* {_escape_md(report.user_email)}")
    lines.append("")

    # Results summary
    lines.append("📊 *Results:*")
    lines.append(f"  ✅ {report.added} new applications tracked")
    lines.append(f"  🔄 {report.updated} applications updated")
    lines.append(f"  ⏭️ {report.skipped} emails skipped")
    if has_errors:
        lines.append(f"  ❌ {report.errors} error(s)")
    lines.append("")

    # Status breakdown
    if report.status_counts:
        lines.append("📋 *Status Breakdown:*")
        for status_name, count in sorted(report.status_counts.items(), key=lambda x: -x[1]):
            emoji = STATUS_EMOJI.get(status_name, "📌")
            lines.append(f"  {emoji} {_escape_md(status_name)}: {count}")
        lines.append("")

    # Companies list (cap at 10)
    all_companies = list(dict.fromkeys(report.added_companies + report.updated_companies))
    if all_companies:
        display_companies = all_companies[:10]
        company_str = ", ".join(_escape_md(c) for c in display_companies)
        if len(all_companies) > 10:
            company_str += f" +{len(all_companies) - 10} more"
        lines.append(f"🏢 *Companies:* {company_str}")
        lines.append("")

    # Error details (cap at 3)
    if report.error_messages:
        lines.append("⚠️ *Errors:*")
        for error_msg in report.error_messages[:3]:
            lines.append(f"  • {_escape_md(error_msg[:100])}")
        if len(report.error_messages) > 3:
            lines.append(f"  _...and {len(report.error_messages) - 3} more_")
        lines.append("")

    if total_processed == 0 and not has_errors:
        lines.append("ℹ️ _No new emails to process this run._")

    return "\n".join(lines)


def send_run_report_for_user(user: dict, report: PipelineRunReport) -> bool:
    """Sends a consolidated report using per-user or global credentials."""
    if not settings.telegram_enabled or not user.get("telegram_enabled"):
        return False

    bot_token = user.get("telegram_bot_token") or settings.telegram_bot_token
    chat_id = user.get("telegram_chat_id") or settings.telegram_chat_id

    if not bot_token or not chat_id:
        logger.warning("Telegram report failed: bot_token or chat_id is missing")
        return False

    text = _build_report_message(report)
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}

    try:
        _post_to_telegram(url, payload)
        logger.bind(user=report.user_email).info("Consolidated Telegram report sent")
        return True
    except Exception as error:
        logger.bind(error=str(error)).error("Failed to send consolidated report")
        return False


# ══════════════════════════════════════════════════════════════
# Legacy Alerts (for critical errors)
# ══════════════════════════════════════════════════════════════

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
    """Sends an immediate alert for critical updates or errors."""
    if not settings.telegram_enabled:
        return False

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return False

    emoji = STATUS_EMOJI.get(status, "📌")
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
        text = (
            f"⚠️ *Pipeline Error*\n"
            f"📛 *Error:* {safe_company}\n"
            f"🔍 *Detail:* {safe_title}\n"
            f"🕐 *Time:* {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        )
    else:
        return False

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {"chat_id": settings.telegram_chat_id, "text": text, "parse_mode": "Markdown"}

    try:
        _post_to_telegram(url, payload)
        return True
    except Exception:
        return False
