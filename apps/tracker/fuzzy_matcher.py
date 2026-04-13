# ╔══════════════════════════════════════════════════════════════╗
# ║  Enhanced Fuzzy Matcher — Application Threading             ║
# ║                                                             ║
# ║  Ensures emails from the same company/job are grouped       ║
# ║  into a single application record with status_history.      ║
# ║  Solves the "Körber duplicate" problem.                     ║
# ╚══════════════════════════════════════════════════════════════╝

from typing import Optional, List, Dict
from difflib import SequenceMatcher
from loguru import logger


class ApplicationMatcher:
    """
    Intelligent matcher that groups related emails into single applications.
    Uses multi-field fuzzy matching to handle company name variations.
    """

    def __init__(self, similarity_threshold: float = 0.85):
        self.similarity_threshold = similarity_threshold

    def find_existing_application(
        self, company_name: str, job_title: str, thread_id: str, apps_cache: List[Dict]
    ) -> Optional[Dict]:
        """
        Find an existing application using multiple matching strategies.

        Strategy Priority:
        1. Exact thread_id match (highest confidence)
        2. Fuzzy company + job match (handles typos/variations)
        3. Company-only match if job_title is generic

        Returns the best matching application or None.
        """

        # Strategy 1: Thread ID match (Gmail groups related emails)
        thread_match = self._match_by_thread(thread_id, job_title, apps_cache)
        if thread_match:
            logger.debug(f"Thread match found: {thread_match['id']}")
            return thread_match

        # Strategy 2: Fuzzy company + job matching
        fuzzy_match = self._match_by_fuzzy_fields(company_name, job_title, apps_cache)
        if fuzzy_match:
            logger.debug(f"Fuzzy match found: {fuzzy_match['id']}")
            return fuzzy_match

        logger.debug(f"No match found for {company_name} / {job_title}")
        return None

    def _match_by_thread(self, thread_id: str, job_title: str, apps_cache: List[Dict]) -> Optional[Dict]:
        """Exact thread ID matching with a safety check for drastically different jobs."""
        job_clean = self._normalize_job_title(job_title)

        for app in apps_cache:
            if app.get("thread_id") == thread_id and app.get("is_active"):
                app_job_clean = self._normalize_job_title(app.get("job_title", ""))

                # If they both have job titles and they are absolutely distinct, refuse to merge
                if job_clean and app_job_clean:
                    if self._similarity(job_clean, app_job_clean) < 0.25:
                        logger.debug(
                            f"Thread matched, but job titles '{job_title}' and '{app.get('job_title')}' are completely different. Refusing thread merge."
                        )
                        continue

                return app
        return None

    def _match_by_fuzzy_fields(self, company_name: str, job_title: str, apps_cache: List[Dict]) -> Optional[Dict]:
        """
        Fuzzy matching on company name and job title.
        Handles variations like:
        - "Körber AG" vs "Koerber"
        - "Senior Software Engineer" vs "Software Engineer (Senior)"
        """
        best_match = None
        best_score = 0.0

        company_clean = self._normalize_company_name(company_name)
        job_clean = self._normalize_job_title(job_title)

        for app in apps_cache:
            if not app.get("is_active"):
                continue

            app_company = self._normalize_company_name(app.get("company_name", ""))
            app_job = self._normalize_job_title(app.get("job_title", ""))

            # Calculate similarity scores
            company_sim = self._similarity(company_clean, app_company)
            job_sim = self._similarity(job_clean, app_job)

            # ANTI-MERGE GUARD: If the company is identical but the job is vastly different,
            # they applied to a distinct role at the same firm. Do not merge!
            if company_sim > 0.8 and job_clean and app_job:
                if job_sim < 0.65:
                    continue

            # Weighted scoring: company is more important than job title
            composite_score = (company_sim * 0.70) + (job_sim * 0.30)

            if composite_score > best_score and composite_score >= self.similarity_threshold:
                best_score = composite_score
                best_match = app

        if best_match:
            logger.info(f"Fuzzy match: '{company_name}' → '{best_match['company_name']}' (score: {best_score:.2f})")

        return best_match

    def _normalize_company_name(self, name: str) -> str:
        """Normalize company names for better matching."""
        # Remove common suffixes and legal entities
        suffixes = [" gmbh", " ag", " inc", " ltd", " llc", " corporation", " corp"]
        name_lower = name.lower().strip()

        for suffix in suffixes:
            if name_lower.endswith(suffix):
                name_lower = name_lower[: -len(suffix)].strip()

        # Replace special characters
        replacements = {"ä": "a", "ö": "o", "ü": "u", "ß": "ss", "&": "and", "-": " ", "_": " "}
        for old, new in replacements.items():
            name_lower = name_lower.replace(old, new)

        # Remove extra whitespace
        return " ".join(name_lower.split())

    def _normalize_job_title(self, title: str) -> str:
        """Normalize job titles for better matching."""
        title_lower = title.lower().strip()

        # Remove common prefixes/suffixes
        prefixes = ["senior", "junior", "lead", "principal"]
        words = title_lower.split()
        words = [w for w in words if w not in prefixes]

        return " ".join(words)

    def _similarity(self, a: str, b: str) -> float:
        """Calculate similarity ratio between two strings."""
        return SequenceMatcher(None, a, b).ratio()


# ── Usage in tracker.py ────────────────────────────────────────


def create_or_update_application(
    client, email, classification, apps_cache: List[Dict], matcher: ApplicationMatcher
) -> str:
    """
    Smart upsert: either creates new application or appends to existing one.
    Returns: 'added' or 'updated'
    """

    existing_app = matcher.find_existing_application(
        company_name=classification.company_name,
        job_title=classification.job_title,
        thread_id=email.thread_id,
        apps_cache=apps_cache,
    )

    if existing_app:
        # UPDATE: Append to status_history
        status_update = {
            "timestamp": email.date.isoformat(),
            "status": classification.classification,
            "email_subject": email.subject,
            "source_email_id": email.email_id,
            "confidence": classification.confidence,
        }

        # Get current history
        current_history = existing_app.get("status_history", [])
        if isinstance(current_history, str):
            import json

            current_history = json.loads(current_history)

        current_history.append(status_update)

        # Update the application
        client.table("applications").update(
            {
                "status": classification.classification,
                "status_history": current_history,
                "email_count": len(current_history),
                "last_updated": "now()",
            }
        ).eq("id", existing_app["id"]).execute()

        logger.info(
            f"Updated application {existing_app['id']}: {classification.company_name} → {classification.classification}"
        )
        return "updated"

    else:
        # CREATE: New application
        initial_status = {
            "timestamp": email.date.isoformat(),
            "status": classification.classification,
            "email_subject": email.subject,
            "source_email_id": email.email_id,
            "confidence": classification.confidence,
        }

        client.table("applications").insert(
            {
                "thread_id": email.thread_id,
                "company_name": classification.company_name,
                "job_title": classification.job_title,
                "platform": classification.platform,
                "status": classification.classification,
                "confidence": classification.confidence,
                "email_subject": email.subject,
                "email_from": email.sender_email,
                "date_applied": email.date.isoformat(),
                "gmail_link": email.gmail_link,
                "source_email_id": email.email_id,
                "status_history": [initial_status],
                "email_count": 1,
                "is_active": True,
            }
        ).execute()

        logger.info(f"Created new application: {classification.company_name}")
        return "added"
