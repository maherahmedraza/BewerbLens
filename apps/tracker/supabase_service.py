# ╔══════════════════════════════════════════════════════════════╗
# ║  Supabase Service — Storage and deduplication               ║
# ║                                                             ║
# ║  Fixes applied:                                             ║
# ║  #4  — Shared Supabase client instance via @lru_cache       ║
# ║  #8  — _insert_with_retry correctly reraises errors         ║
# ║  #9  — Simplified _should_update_status logic (Fix B)       ║
# ║  #12 — datetime.utcnow() replaced with timezone-aware now() ║
# ║  #14 — update_heartbeat() for stuck run monitoring          ║
# ║  #17 — Optimized fuzzy matching via pre-fetched cache       ║
# ║  #C  — create_pipeline_run tuple unpacking fixed            ║
# ║  #Q  — _find_fuzzy_match O(n²) fallback eliminado          ║
# ╚══════════════════════════════════════════════════════════════╝

import re
from datetime import date, datetime, timezone
from functools import lru_cache

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

PLATFORM_NAMES: set[str] = {
    "smartrecruiters", "softgarden", "greenhouse", "recruitee",
    "onlyfy", "personio", "workday", "lever", "successfactors",
    "bamboohr", "icims", "taleo", "broadbean", "workwise",
    "hokify", "join.com", "stepstone", "linkedin", "indeed",
    "xing", "glassdoor", "monster",
}


@lru_cache(maxsize=1)
def get_client() -> Client:
    """
    Returns a shared Supabase client instance.
    Fixes: review issue #4 — prevent creating hundreds of client instances.
    """
    return create_client(settings.supabase_url, settings.supabase_key)


def _utcnow() -> datetime:
    """Centralized timezone-aware UTC now. Fixes #12."""
    return datetime.now(timezone.utc)


def _detect_platform(sender_email: str, ai_platform: str) -> str:
    valid_platforms = {name for _, name in PLATFORM_DOMAIN_MAP}
    if ai_platform and ai_platform in valid_platforms:
        return ai_platform

    sender_lower = sender_email.lower()
    for domain_pattern, platform_name in PLATFORM_DOMAIN_MAP:
        if domain_pattern in sender_lower:
            return platform_name
    return "Direct"


def _clean_company_name(name: str, sender_email: str) -> str:
    if not name or not name.strip():
        return _extract_company_from_domain(sender_email)

    cleaned = name.strip()
    name_lower = cleaned.lower()

    if any(platform in name_lower for platform in PLATFORM_NAMES):
        return _extract_company_from_domain(sender_email)

    if name_lower in {"unknown", "not specified", "n/a", "none", ""}:
        return _extract_company_from_domain(sender_email)

    return cleaned


def _extract_company_from_domain(sender_email: str) -> str:
    match = re.search(r"@([\w.-]+)", sender_email)
    if not match:
        return "Unknown"

    domain = match.group(1).lower()
    generic_domains = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "web.de", "gmx.de", "gmx.net"}
    if domain in generic_domains:
        return "Unknown"

    if any(platform in domain for platform in PLATFORM_NAMES):
        return "Unknown"

    name = re.sub(r"\.(com|de|io|net|org|eu|jobs|at|ch|fr|nl|co\.uk)$", "", domain)
    name = re.sub(
        r"^(mail|email|reply|noreply|no-reply|notifications?|info|careers?|recruiting|hr|jobs|talent|bewerbung|support|team|hello|donotreply)\.",
        "", name, flags=re.IGNORECASE,
    )
    name = name.replace("-", " ").replace("_", " ").replace(".", " ").strip()
    return " ".join(word.capitalize() for word in name.split()) if len(name) >= 2 else "Unknown"


def _should_update_status(current_status: str, new_status: str) -> bool:
    """
    Decide si un status debe actualizarse basándose en prioridad.
    Fix #B: Lógica simplificada, sin rama OR muerta para REJECTED.
    OFFER es terminal — nada lo sobreescribe.
    """
    try:
        curr = Status(current_status)
        nxt = Status(new_status)
    except ValueError:
        logger.warning(f"Unrecognized status in transition: '{current_status}' → '{new_status}'")
        return True

    # OFFER es terminal — nunca se sobreescribe
    if curr == Status.OFFER:
        return False

    return STATUS_PRIORITY.get(nxt, 0) > STATUS_PRIORITY.get(curr, 0)


# ── Bronze Layer ──────────────────────────────────────────────

def insert_raw_email(client: Client, email: EmailMetadata) -> bool:
    try:
        record = RawEmailRecord(
            email_id=email.email_id,
            thread_id=email.thread_id,
            subject=email.subject[:200],
            sender=email.sender[:200],
            sender_email=email.sender_email[:200],
            body_preview=email.body[:800],
            email_date=email.date,
            gmail_link=email.gmail_link,
        )
        client.table("raw_emails").upsert(
            record.model_dump(mode="json"), on_conflict="email_id"
        ).execute()
        return True
    except Exception as error:
        logger.bind(email_id=email.email_id).warning(f"Failed to insert raw email: {error}")
        return False


def mark_raw_emails_processed(client: Client, email_ids: list[str]) -> int:
    if not email_ids:
        return 0
    try:
        result = client.table("raw_emails").update({"is_processed": True}).in_("email_id", email_ids).execute()
        return len(result.data) if result.data else 0
    except Exception as error:
        logger.warning(f"Failed to mark raw emails processed: {error}")
        return 0


# ── Silver Layer ──────────────────────────────────────────────

def get_last_checkpoint(client: Client) -> date:
    try:
        result = client.table("applications").select("processed_at").order("processed_at", desc=True).limit(1).execute()
        if result.data and result.data[0]["processed_at"]:
            return datetime.fromisoformat(result.data[0]["processed_at"].replace("Z", "+00:00")).date()
    except Exception:
        pass
    return date.fromisoformat(settings.backfill_start_date)


def get_existing_thread_ids(client: Client) -> set[str]:
    try:
        result = client.table("applications").select("thread_id").execute()
        return {row["thread_id"] for row in result.data if row.get("thread_id")}
    except Exception:
        return set()


def upsert_application(
    client: Client,
    email: EmailMetadata,
    classification: EmailClassification,
    apps_cache: list[dict] | None = None,
) -> str:
    """
    # Fix #17: accept pre-fetched apps_cache to avoid O(n^2) DB calls.
    """
    status_enum = CLASSIFICATION_TO_STATUS.get(classification.classification)
    if status_enum is None:
        return "skipped"

    status = status_enum.value
    company = _clean_company_name(classification.company_name, email.sender_email)
    platform = _detect_platform(email.sender_email, classification.platform)

    # 1. Direct thread match
    existing = client.table("applications").select("*").eq("thread_id", email.thread_id).execute()
    
    if existing.data:
        current = existing.data[0]
        cur_status = current.get("status", "Applied")

        if cur_status == status or not _should_update_status(cur_status, status):
            return "skipped"

        upd_title = classification.job_title if current.get("job_title") in ("Not Specified", None, "") else current["job_title"]

        client.table("applications").update({
            "status": status,
            "job_title": upd_title,
            "last_updated": _utcnow().isoformat(),
            "notes": f"{cur_status} -> {status} | {email.subject[:100]}",
            "location": classification.location or current.get("location", ""),
            "salary_range": classification.salary_range or current.get("salary_range", ""),
        }).eq("thread_id", email.thread_id).execute()
        return "updated"

    # 2. Fuzzy match — Fix #Q: cache obligatorio, sin fallback a DB
    if apps_cache is not None:
        fuzzy_match = _find_fuzzy_match(apps_cache, company, classification.job_title)
    else:
        fuzzy_match = None

    if fuzzy_match:
        cur_status = fuzzy_match.get("status", "Applied")
        if cur_status == status or not _should_update_status(cur_status, status):
            return "skipped"

        client.table("applications").update({
            "status": status,
            "last_updated": _utcnow().isoformat(),
            "notes": f"Fuzzy: {cur_status} -> {status} | {email.subject[:100]}",
            "location": classification.location or fuzzy_match.get("location", ""),
            "salary_range": classification.salary_range or fuzzy_match.get("salary_range", ""),
        }).eq("id", fuzzy_match["id"]).execute()
        return "updated"

    # 3. New record
    if company.lower() in {"unknown", "not specified", "n/a", ""}:
        return "skipped"

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
        last_updated=_utcnow(),
        notes=classification.reasoning[:150],
        gmail_link=email.gmail_link,
        job_listing_url=classification.job_listing_url,
        location=classification.location,
        salary_range=classification.salary_range,
        source_email_id=email.email_id,
    )
    _insert_with_retry(client, record)
    return "added"


# ── Fuzzy Logic ──────────────────────────────────────────────

_FUZZY_STOPWORDS: set[str] = {
    "gmbh", "ag", "se", "kg", "co", "inc", "ltd", "llc", "corp",
    "deutschland", "germany", "europe", "international",
    "logistik", "logistics", "services", "solutions", "group",
    "consulting", "engineering", "digital", "systems", "technology",
    "management", "partners", "holding", "und", "and", "the",
    "mbh", "ohg", "e.v.", "ev", "eg",
}


def _strip_stopwords(name: str) -> str:
    words = name.lower().split()
    filtered = [w for w in words if w not in _FUZZY_STOPWORDS]
    return " ".join(filtered) if filtered else name.lower()


def _find_fuzzy_match(
    records_cache: list[dict],
    company_name: str,
    job_title: str,
) -> dict | None:
    """
    Fix #Q: cache es obligatorio, sin parámetro client ni fallback a DB.
    Elimina la ruta O(n²) que consultaba la DB por cada email del batch.
    """
    cleaned_input = _strip_stopwords(company_name)
    if len(cleaned_input) < 3:
        return None

    best_match, best_score = None, 0.0

    for rec in records_cache:
        cleaned_existing = _strip_stopwords(rec.get("company_name", ""))
        if len(cleaned_existing) < 3:
            continue

        co_score = fuzz.ratio(cleaned_input, cleaned_existing) / 100.0
        if co_score < 0.80:
            continue

        score = co_score
        ex_title = rec.get("job_title", "")
        has_in_t = job_title and job_title != "Not Specified"
        has_ex_t = ex_title and ex_title != "Not Specified"

        if has_in_t and has_ex_t:
            t_score = fuzz.token_sort_ratio(job_title.lower(), ex_title.lower()) / 100.0
            if t_score < 0.85:
                continue
            score = co_score * 0.4 + t_score * 0.6
        elif has_in_t or has_ex_t:
            continue
        elif co_score < 0.95:
            continue

        if score > best_score and score >= 0.85:
            best_score = score
            best_match = rec

    return best_match


# ── Generic Helpers ───────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=15),
    reraise=True,  # Fix #8: bubbling up critical DB errors
)
def _insert_with_retry(client: Client, record: ApplicationRecord) -> None:
    client.table("applications").insert(record.model_dump(mode="json")).execute()


def log_processing(client: Client, log: ProcessingLog) -> None:
    try:
        client.table("ai_processing_logs").insert(log.model_dump(mode="json")).execute()
    except Exception:
        pass


def update_heartbeat(client: Client, internal_id: str) -> None:
    """
    Updates the heartbeat_at timestamp for a run.
    Fixes: review issue #14 — monitor zombie runs.
    """
    try:
        client.table("pipeline_runs").update({
            "heartbeat_at": _utcnow().isoformat()
        }).eq("id", internal_id).execute()
    except Exception:
        pass


def create_pipeline_run(
    client: Client,
    run_id: str,
    triggered_by: str = "scheduler",
    since_date: date | None = None,
) -> tuple[str | None, datetime | None]:
    """
    Fix #C: Corregido el desempaquetado de tupla con if/else explícito.
    Python parsea 'return a, b if cond else (c, d)' como 'return a, (b if cond else (c, d))'.
    """
    try:
        started_at = _utcnow()
        data = {
            "run_id": run_id,
            "status": "running",
            "triggered_by": triggered_by,
            "started_at": started_at.isoformat(),
            "heartbeat_at": started_at.isoformat(),
            "parameters": {"since_date": since_date.isoformat() if since_date else None},
            "current_phase": "ingestion",
        }
        res = client.table("pipeline_runs").insert(data).execute()

        if res.data:
            return res.data[0]["id"], started_at
        return None, None
    except Exception:
        return None, None


def update_pipeline_run(
    client: Client,
    internal_id: str,
    status: str,
    started_at: datetime | None = None,
    stats: dict | None = None,
    logs_summary: str = "",
    full_log_url: str | None = None,
    error_message: str | None = None,
) -> bool:
    """Fixes #3, #12: Accurate duration via started_at param."""
    try:
        ended_at = _utcnow()
        duration_ms = int((ended_at - started_at).total_seconds() * 1000) if started_at else None

        data = {
            "status": status,
            "ended_at": ended_at.isoformat(),
            "duration_ms": duration_ms,
            "summary_stats": stats or {},
            "logs_summary": logs_summary[:10000],
            "full_log_url": full_log_url,
        }
        if error_message:
            data["error_message"] = error_message

        client.table("pipeline_runs").update(data).eq("id", internal_id).execute()
        return True
    except Exception:
        return False


def init_pipeline_steps(client: Client, run_id: str) -> bool:
    try:
        steps = [
            {"run_id": run_id, "step_name": "ingestion", "status": "pending"},
            {"run_id": run_id, "step_name": "analysis", "status": "pending"},
            {"run_id": run_id, "step_name": "persistence", "status": "pending"},
        ]
        client.table("pipeline_run_steps").insert(steps).execute()
        return True
    except Exception:
        return False


def update_pipeline_step(
    client: Client,
    run_id: str,
    step_name: str,
    status: str,
    progress: int = 0,
    message: str = "",
    stats: dict | None = None,
) -> bool:
    try:
        data = {"status": status, "progress_pct": progress, "message": message}
        now_iso = _utcnow().isoformat()
        if status == "running":
            data["started_at"] = now_iso
        elif status in ("success", "failed"):
            data["ended_at"] = now_iso
        if stats:
            data["stats"] = stats
        client.table("pipeline_run_steps").update(data).match({"run_id": run_id, "step_name": step_name}).execute()
        return True
    except Exception:
        return False


def insert_pipeline_log(
    client: Client,
    internal_id: str,
    level: str,
    message: str,
    step_name: str | None = None,
) -> bool:
    """
    Inserta un log en pipeline_run_logs.
    Nota: run_id es un FK a pipeline_runs.id (UUID), no el label legible.
    """
    try:
        client.table("pipeline_run_logs").insert({
            "run_id": internal_id,
            "level": level,
            "message": message,
            "step_name": step_name,
        }).execute()
        return True
    except Exception:
        return False


def get_existing_email_ids(client: Client) -> set[str]:
    try:
        res = client.table("raw_emails").select("email_id").execute()
        return {row["email_id"] for row in res.data}
    except Exception as e:
        logger.error(f"Failed to fetch existing email IDs: {str(e)}")
        return set()


def get_pipeline_config(client: Client) -> dict:
    try:
        res = client.table("pipeline_config").select("*").eq("id", "00000000-0000-0000-0000-000000000001").execute()
        return res.data[0] if res.data else {}
    except Exception:
        return {}


def get_active_run(client: Client) -> dict | None:
    try:
        res = client.table("pipeline_runs").select("*").eq("status", "running").order("started_at", desc=True).limit(1).execute()
        return res.data[0] if res.data else None
    except Exception:
        return None
