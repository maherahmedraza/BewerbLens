# ╔══════════════════════════════════════════════════════════════╗
# ║  Supabase Service — Storage and deduplication               ║
# ║  Replaces the "Read Applications Sheet",                    ║
# ║  "Dedup Engine", "Add New Row" and "Update Existing Row".   ║
# ║                                                             ║
# ║  v2.0: Medallion architecture (Bronze raw_emails +          ║
# ║  Silver applications), new fields (location,                ║
# ║  job_listing_url, salary_range, gmail_link), multi-user.    ║
# ╚══════════════════════════════════════════════════════════════╝

import re
from datetime import date, datetime

from loguru import logger
from supabase import Client, create_client
from tenacity import retry, stop_after_attempt, wait_exponential
from thefuzz import fuzz

from config import settings
from models import (
    CLASSIFICATION_TO_STATUS,
    STATUS_PRIORITY,
    ApplicationRecord,
    EmailClassification,
    EmailMetadata,
    ProcessingLog,
    RawEmailRecord,
    Status,
)

# ── Platform detection constants ──────────────────────────────
PLATFORM_DOMAIN_MAP: list[tuple[str, str]] = [
    ("smartrecruiters", "SmartRecruiters"),
    ("onlyfy", "Onlyfy"),
    ("personio", "Personio"),
    ("workday", "Workday"),
    ("lever.co", "Lever"),
    ("greenhouse", "Greenhouse"),
    ("successfactors", "SAP SuccessFactors"),
    ("bamboohr", "BambooHR"),
    ("recruitee", "Recruitee"),
    ("softgarden", "Softgarden"),
    ("icims", "iCIMS"),
    ("taleo", "Oracle Taleo"),
    ("broadbean", "Broadbean"),
    ("workwise", "Workwise"),
    ("linkedin", "LinkedIn"),
    ("stepstone", "StepStone"),
    ("indeed", "Indeed"),
    ("xing.com", "Xing"),
    ("join.com", "JOIN"),
]

# Platform names that are NOT company names
PLATFORM_NAMES: set[str] = {
    "smartrecruiters", "softgarden", "greenhouse", "recruitee",
    "onlyfy", "personio", "workday", "lever", "successfactors",
    "bamboohr", "icims", "taleo", "broadbean", "workwise",
    "hokify", "join.com", "stepstone", "linkedin", "indeed",
    "xing", "glassdoor", "monster",
}


def get_client() -> Client:
    """Creates a Supabase client."""
    return create_client(settings.supabase_url, settings.supabase_key)


def _detect_platform(sender_email: str, ai_platform: str) -> str:
    """
    Detects the employment platform based on the sender domain.
    Uses the Gemini value if valid, otherwise detects by domain.
    """
    valid_platforms = {name for _, name in PLATFORM_DOMAIN_MAP}
    if ai_platform and ai_platform in valid_platforms:
        return ai_platform

    sender_lower = sender_email.lower()
    for domain_pattern, platform_name in PLATFORM_DOMAIN_MAP:
        if domain_pattern in sender_lower:
            return platform_name

    return "Direct"


def _clean_company_name(name: str, sender_email: str) -> str:
    """
    Cleans the company name.
    - Rejects ATS platform names
    - Extracts name from domain as fallback
    """
    if not name or not name.strip():
        return _extract_company_from_domain(sender_email)

    cleaned = name.strip()
    name_lower = cleaned.lower()

    # Reject if it is a platform name
    if any(platform in name_lower for platform in PLATFORM_NAMES):
        return _extract_company_from_domain(sender_email)

    # Reject generic values
    if name_lower in {"unknown", "not specified", "n/a", "none", ""}:
        return _extract_company_from_domain(sender_email)

    return cleaned


def _extract_company_from_domain(sender_email: str) -> str:
    """
    Extracts a reasonable company name from the email domain.
    "anna@dekra.com" -> "Dekra"
    """
    match = re.search(r"@([\w.-]+)", sender_email)
    if not match:
        return "Unknown"

    domain = match.group(1).lower()

    # Exclude generic email domains
    generic_domains = {
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com",
        "web.de", "gmx.de", "gmx.net",
    }
    if domain in generic_domains:
        return "Unknown"

    # Exclude if it is an ATS platform domain
    if any(platform in domain for platform in PLATFORM_NAMES):
        return "Unknown"

    # Clean common recruitment subdomains
    name = re.sub(
        r"\.(com|de|io|net|org|eu|jobs|at|ch|fr|nl|co\.uk)$",
        "", domain,
    )
    name = re.sub(
        r"^(mail|email|reply|noreply|no-reply|notifications?|info|careers?|recruiting|hr|jobs|talent|bewerbung|support|team|hello|donotreply)\.",
        "", name, flags=re.IGNORECASE,
    )
    name = name.replace("-", " ").replace("_", " ").replace(".", " ").strip()

    if len(name) < 2:
        return "Unknown"

    # Capitalize each word
    return " ".join(word.capitalize() for word in name.split())


def _should_update_status(current_status: str, new_status: str) -> bool:
    """
    Decides if a status should be updated based on priority.
    Rejected (99) can overwrite everything except Offer (100).
    """
    try:
        current = Status(current_status)
        new = Status(new_status)
    except ValueError:
        return True  # If we don't recognize the status, allow update

    current_priority = STATUS_PRIORITY.get(current, 0)
    new_priority = STATUS_PRIORITY.get(new, 0)

    # Update if: new has higher priority, or is rejection and there is no offer
    return new_priority > current_priority or (new == Status.REJECTED and current != Status.OFFER)


# ── Bronze Layer: Raw email ingestion ─────────────────────────

def insert_raw_email(client: Client, email: EmailMetadata) -> bool:
    """
    Inserts a raw email into the Bronze layer (raw_emails table).
    Idempotent: skips if email_id already exists (uses upsert).
    """
    try:
        record = RawEmailRecord(
            email_id=email.email_id,
            thread_id=email.thread_id,
            subject=email.subject[:200],
            sender=email.sender[:200],
            sender_email=email.sender_email[:200],
            body_preview=email.body[:800],  # GDPR: only store first 800 chars
            email_date=email.date,
            gmail_link=email.gmail_link,
        )

        client.table("raw_emails").upsert(
            record.model_dump(mode="json"),
            on_conflict="email_id",
        ).execute()
        return True
    except Exception as error:
        logger.bind(email_id=email.email_id, error=str(error)).warning("Failed to insert raw email")
        return False


def mark_raw_emails_processed(client: Client, email_ids: list[str]) -> int:
    """Marks raw emails as processed after classification."""
    if not email_ids:
        return 0
    try:
        result = (
            client.table("raw_emails")
            .update({"is_processed": True})
            .in_("email_id", email_ids)
            .execute()
        )
        return len(result.data) if result.data else 0
    except Exception as error:
        logger.bind(error=str(error)).warning("Failed to mark raw emails as processed")
        return 0


# ── Silver Layer: Classified applications ─────────────────────

def get_last_checkpoint(client: Client) -> date:
    """
    Gets the date of the last processed email from Supabase.
    If no records exist, returns the backfill date from config.
    """
    try:
        result = (
            client.table("applications")
            .select("processed_at")
            .order("processed_at", desc=True)
            .limit(1)
            .execute()
        )

        if result.data:
            last_processed = result.data[0]["processed_at"]
            if last_processed:
                return datetime.fromisoformat(last_processed.replace("Z", "+00:00")).date()
    except Exception as error:
        logger.bind(error=str(error)).warning("Could not fetch last checkpoint")

    # Fallback: use the backfill date from config
    return date.fromisoformat(settings.backfill_start_date)


def get_existing_thread_ids(client: Client) -> set[str]:
    """
    Gets all existing thread_ids from the database.
    Used to deduplicate emails before processing with Gemini.
    """
    try:
        result = client.table("applications").select("thread_id").execute()
        return {row["thread_id"] for row in result.data if row.get("thread_id")}
    except Exception as error:
        logger.bind(error=str(error)).warning("Could not fetch existing thread IDs")
        return set()


def upsert_application(
    client: Client,
    email: EmailMetadata,
    classification: EmailClassification,
) -> str:
    """
    Inserts or updates an application in Supabase (Silver layer).
    Returns the action performed: "added", "updated", or "skipped".

    v2.0: Includes new fields (location, job_listing_url, salary_range, gmail_link).
    """
    status_enum = CLASSIFICATION_TO_STATUS.get(classification.classification)
    if status_enum is None:
        return "skipped"

    status = status_enum.value
    company = _clean_company_name(classification.company_name, email.sender_email)
    platform = _detect_platform(email.sender_email, classification.platform)

    # Check if a record with this thread_id already exists
    existing = (
        client.table("applications")
        .select("*")
        .eq("thread_id", email.thread_id)
        .execute()
    )

    if existing.data:
        # Already exists - evaluate if status should be updated
        current = existing.data[0]
        current_status = current.get("status", "Applied")

        if current_status == status:
            logger.bind(company=company, status=status).debug("Skipping - same status")
            return "skipped"

        if not _should_update_status(current_status, status):
            logger.bind(
                company=company,
                current=current_status,
                new=status
            ).debug("Status protected")
            return "skipped"

        # Update title if existing one is generic
        updated_title = classification.job_title
        if current.get("job_title") not in ("Not Specified", None, ""):
            if classification.job_title in ("Not Specified", ""):
                updated_title = current["job_title"]

        # Execute UPDATE with v2.0 fields
        client.table("applications").update({
            "status": status,
            "job_title": updated_title,
            "last_updated": datetime.utcnow().isoformat(),
            "notes": f"{current_status} -> {status} | {email.subject[:100]}",
            "location": classification.location or current.get("location", ""),
            "salary_range": classification.salary_range or current.get("salary_range", ""),
        }).eq("thread_id", email.thread_id).execute()

        logger.bind(
            company=company,
            from_status=current_status,
            to_status=status
        ).info("Application status updated")
        return "updated"

    else:
        # Check fuzzy match by company_name + job_title
        fuzzy_match = _find_fuzzy_match(client, company, classification.job_title)

        if fuzzy_match:
            current_status = fuzzy_match.get("status", "Applied")
            if current_status == status:
                return "skipped"
            if not _should_update_status(current_status, status):
                return "skipped"

            # Update existing record found by fuzzy match
            client.table("applications").update({
                "status": status,
                "last_updated": datetime.utcnow().isoformat(),
                "notes": f"Fuzzy match: {current_status} -> {status} | {email.subject[:100]}",
                "location": classification.location or fuzzy_match.get("location", ""),
                "salary_range": classification.salary_range or fuzzy_match.get("salary_range", ""),
            }).eq("id", fuzzy_match["id"]).execute()

            logger.bind(
                company=company,
                fuzzy_matched=fuzzy_match.get("company_name"),
                to_status=status
            ).info("Fuzzy match updated")
            return "updated"

        # Skip records with generic company name — no value
        if company.lower() in {"unknown", "not specified", "n/a", "none", ""}:
            logger.bind(company=company, subject=email.subject[:60]).debug(
                "Skipping insert — generic company name"
            )
            return "skipped"

        # Insert new record with v2.0 fields
        record = ApplicationRecord(
            thread_id=email.thread_id,
            company_name=company,
            job_title=classification.job_title or "Not Specified",
            platform=platform,
            status=status,
            confidence=classification.confidence,
            email_subject=email.subject[:150],
            email_from=email.sender[:100],
            date_applied=email.date,
            last_updated=datetime.utcnow(),
            notes=classification.reasoning[:150],
            # v2.0 new fields
            gmail_link=email.gmail_link,
            job_listing_url=classification.job_listing_url,
            location=classification.location,
            salary_range=classification.salary_range,
            source_email_id=email.email_id,
        )

        _insert_with_retry(client, record)

        logger.bind(
            company=company,
            title=classification.job_title,
            status=status,
            platform=platform,
            location=classification.location or "N/A",
        ).info("New application added")
        return "added"


# ── Fuzzy matching with stopwords ─────────────────────────────

# Generic words that inflate similarity scores
_FUZZY_STOPWORDS: set[str] = {
    "gmbh", "ag", "se", "kg", "co", "inc", "ltd", "llc", "corp",
    "deutschland", "germany", "europe", "international",
    "logistik", "logistics", "services", "solutions", "group",
    "consulting", "engineering", "digital", "systems", "technology",
    "management", "partners", "holding", "und", "and", "the",
    "mbh", "ohg", "e.v.", "ev", "eg", "e.g.",
}


def _strip_stopwords(name: str) -> str:
    """Removes generic words from a name to improve fuzzy matching."""
    words = name.lower().split()
    filtered = [w for w in words if w not in _FUZZY_STOPWORDS]
    return " ".join(filtered) if filtered else name.lower()


def _find_fuzzy_match(client: Client, company_name: str, job_title: str) -> dict | None:
    """
    Searches for an existing record by similar company name.
    Uses thefuzz with stopwords to avoid false positives.

    Minimum threshold: 0.75 (was 0.4, which caused incorrect matches).
    """
    try:
        all_records = client.table("applications").select("*").execute()
    except Exception:
        return None

    best_match = None
    best_score = 0.0

    cleaned_input = _strip_stopwords(company_name)

    # Very short name after cleaning — too risky for false positives
    if len(cleaned_input) < 3:
        return None

    for record in all_records.data:
        existing_company = record.get("company_name", "")
        cleaned_existing = _strip_stopwords(existing_company)

        if len(cleaned_existing) < 3:
            continue

        # Strict comparison: fuzz.ratio (order matters) instead of token_sort_ratio
        company_score = fuzz.ratio(cleaned_input, cleaned_existing) / 100.0

        if company_score < 0.80:  # Increased from 0.70
            continue

        # Calculate title similarity if both are specific
        score = company_score
        existing_title = record.get("job_title", "")
        
        has_specific_input_title = job_title and job_title != "Not Specified"
        has_specific_existing_title = existing_title and existing_title != "Not Specified"

        if has_specific_input_title and has_specific_existing_title:
            title_score = fuzz.token_sort_ratio(
                job_title.lower(), existing_title.lower()
            ) / 100.0
            
            # If titles are very different, they are different jobs
            if title_score < 0.85: # Stricter threshold for different jobs at same company
                continue
            score = company_score * 0.4 + title_score * 0.6
        elif has_specific_input_title or has_specific_existing_title:
            # One has a title, the other doesn't -> likely different jobs or new info
            # We avoid fuzzy matching here to encourage creating a new record for the one with the title
            continue
        else:
            # Both are "Not Specified" -> only match if company name is almost exact
            if company_score < 0.95:
                continue
            score = company_score * 0.90

        if score > best_score and score >= 0.85: # Increased overall threshold from 0.75
            best_score = score
            best_match = record

    if best_match:
        logger.bind(
            input_company=company_name,
            matched=best_match.get("company_name"),
            score=f"{best_score:.2f}"
        ).debug("Fuzzy match found")

    return best_match


# ── Retry and logging helpers ─────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    reraise=False,
)
def _insert_with_retry(client: Client, record: ApplicationRecord) -> None:
    """Inserts a record with automatic retries."""
    client.table("applications").insert(record.model_dump(mode="json")).execute()


def log_processing(client: Client, log: ProcessingLog) -> None:
    """Writes a processing log entry to Supabase for auditing."""
    try:
        client.table("ai_processing_logs").insert(log.model_dump(mode="json")).execute()
    except Exception as error:
        logger.bind(error=str(error)).warning("Failed to write processing log")
