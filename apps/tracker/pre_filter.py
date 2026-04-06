# ╔══════════════════════════════════════════════════════════════╗
# ║  Pre-Filter — Fast rule-based filtering                     ║
# ║  Replaces the "Pre-Filter" node from the n8n workflow.      ║
# ║                                                             ║
# ║  Runs BEFORE Gemini to avoid wasting tokens                 ║
# ║  on emails we know are not job offers.                      ║
# ╚══════════════════════════════════════════════════════════════╝

from dataclasses import dataclass, field

from loguru import logger

from config import settings
from models import EmailMetadata

# ── Blocked senders (exact match) ──────────────────────────────
BLOCKED_SENDERS_EXACT: set[str] = {
    "notifications-noreply@linkedin.com",
    "jobs-listings@linkedin.com",
    "jobalerts-noreply@linkedin.com",
    "inmail-hit-reply@linkedin.com",
    "updates-noreply@linkedin.com",
    "messages-noreply@linkedin.com",
    "learning-noreply@linkedin.com",
    "news-noreply@linkedin.com",
    "premium-noreply@linkedin.com",
    "news@mail.xing.com",
    "info@jobagent.stepstone.de",
    "jobalert@indeed.com",
    "alert@indeed.com",
    "noreply@indeed.com",
    "hello@dataquest.io",
    "stefan.huber@hokify.com",
    "noreply@arbeitsagentur.de",
}

# ── Blocked sender patterns (substring match) ─────────────────
SENDER_BLOCK_PATTERNS: list[str] = [
    "jobalerts-noreply@",
    "jobs-listings@linkedin",
    "notifications-noreply@linkedin",
    "updates-noreply@linkedin",
    "messages-noreply@linkedin",
    "learning-noreply@linkedin",
    "news-noreply@linkedin",
    "premium-noreply@linkedin",
    "jobagent@stepstone",
    "jobagent@indeed",
    "@hokify.com",
    "noreply@newsletter.",
    "jobalert@",
    "job-alert@",
    "@arbeitsagentur.de",
    "@bundesagentur",
]

# ── University patterns ───────────────────────────────────────
UNIVERSITY_PATTERNS: list[str] = [
    "uni-koblenz.de", "list.uni-", "studierende@", "@asta."
]

# ── Subjects that are always excluded ─────────────────────────
SUBJECT_EXCLUSIONS: list[str] = [
    "new jobs for you", "neue jobs fur dich",
    "jobs matching your search", "jobs you might like",
    "job recommendations", "new jobs in your area",
    "companies are looking for candidates like you",
    "read this article", "read on linkedin",
    "published a newsletter", "published an article",
    "started a new position", "is celebrating", "has a new job",
    "people viewed your profile", "search appearances",
    "your posts got", "impressions last week",
    "top voices", "trending on linkedin",
    "weekly digest", "monthly digest", "connection digest", "weekly roundup",
    "career tips", "karrieretipps",
    "job alert", "job-alert", "jobalert",
    "new jobs matching", "jobs matching your",
    "10+ new jobs", "5+ new jobs",
    "jobbenachrichtigung", "job benachrichtigung",
    "you have 1 new invitation",
    "asta sitzung", "vorlesung", "tutorium", "klausur",
    "spannende jobs fur dich", "ich denke diese jobs passen",
    "system migration",
    "one-time-passcode", "one-time password", "passcode",
    "verification code", "bestatigungscode",
    "ihr zugangscode", "dein zugangscode",
    "complete your application", "finish your application",
    "bewerbung abschlieen",
    # Eventos, ferias, mesas — no son candidaturas reales
    "seminar", "klausurtermin", "career day", "karrieretag",
    "career fair", "karrieremesse", "firmenkontaktmesse",
    "bonding", "praxisbörse",
]

# ── Keywords that indicate employment even from universities ──
JOB_KEYWORDS_FOR_UNIVERSITY: list[str] = [
    "bewerbung", "application", "absage", "rejection",
    "eingangsbestatigung", "thank you for applying",
]


@dataclass
class FilterStats:
    """Filtering process statistics."""
    total: int = 0
    blocked_sender: int = 0
    blocked_pattern: int = 0
    self_sent: int = 0
    blocked_subject: int = 0
    university: int = 0
    passed: int = 0
    details: list[dict] = field(default_factory=list)


def apply_pre_filters(emails: list[EmailMetadata]) -> tuple[list[EmailMetadata], FilterStats]:
    """
    Applies rule-based filters to emails.
    Returns a tuple of (emails that passed, statistics).

    Significantly faster than the n8n node because:
    - Uses sets for O(1) lookup of blocked senders
    - No need to serialize/deserialize JSON between nodes
    """
    stats = FilterStats()
    passed: list[EmailMetadata] = []
    user_email = settings.user_email.lower()

    for email in emails:
        stats.total += 1
        sender = email.sender_email.lower()
        subject = email.subject.lower().strip()

        # Filter 1: Exact blocked sender
        if sender in BLOCKED_SENDERS_EXACT:
            stats.blocked_sender += 1
            stats.details.append({"reason": "blocked_sender", "from": sender, "subject": subject[:60]})
            continue

        # Filter 2: Sender pattern
        if any(pattern in sender for pattern in SENDER_BLOCK_PATTERNS):
            stats.blocked_pattern += 1
            stats.details.append({"reason": "sender_pattern", "from": sender, "subject": subject[:60]})
            continue

        # Filter 3: Self-sent email
        if sender == user_email:
            stats.self_sent += 1
            stats.details.append({"reason": "self_sent", "from": sender, "subject": subject[:60]})
            continue

        # Filter 4: Excluded subject
        matching_exclusion = next(
            (kw for kw in SUBJECT_EXCLUSIONS if kw in subject),
            None,
        )
        if matching_exclusion:
            stats.blocked_subject += 1
            stats.details.append({"reason": f"subject:{matching_exclusion}", "from": sender, "subject": subject[:60]})
            continue

        # Filter 5: University (unless it contains employment keywords)
        if any(pattern in sender for pattern in UNIVERSITY_PATTERNS):
            has_job_keyword = any(kw in subject for kw in JOB_KEYWORDS_FOR_UNIVERSITY)
            if not has_job_keyword:
                stats.university += 1
                stats.details.append({"reason": "university", "from": sender, "subject": subject[:60]})
                continue

        stats.passed += 1
        passed.append(email)

    # Log results
    logger.bind(
        passed=stats.passed,
        total=stats.total,
        sender=stats.blocked_sender + stats.blocked_pattern,
        subject=stats.blocked_subject,
        university=stats.university,
        self_sent=stats.self_sent,
    ).info("Pre-filter complete")

    # Show first 15 filtered emails for debugging
    if stats.details:
        logger.debug("Filtered emails (first 15):")
        for i, detail in enumerate(stats.details[:15]):
            logger.debug(f"  {i + 1}. [{detail['reason']}] \"{detail['subject']}\" | {detail['from']}")

    return passed, stats
