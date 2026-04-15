# ╔══════════════════════════════════════════════════════════════╗
# ║  FIXED Fuzzy Matcher — Strict Job Title Matching            ║
# ║                                                             ║
# ║  CRITICAL FIX: Körber should create 3 separate applications ║
# ║  - Support Consultant WCS (thread 19d368b866be2f61)         ║
# ║  - Absolventen SAP (thread 19d392ac+19d393be)              ║
# ║  - Karriere SAP (thread 19d62fc9+19d62fc8+19d62fca)        ║
# ║                                                             ║
# ║  Strategy: Match on company_name + job_title BOTH high     ║
# ║  Thread_id is unreliable (Gmail threads by sender)         ║
# ╚══════════════════════════════════════════════════════════════╝

from typing import Optional, List, Dict
from difflib import SequenceMatcher
from loguru import logger
from models import CLASSIFICATION_TO_STATUS


class ApplicationMatcher:
    """
    FIXED: Strict matcher that creates separate apps for different job titles.
    
    Key Principle:
    - Same company + DIFFERENT job = SEPARATE applications
    - Same company + SAME job = SINGLE application with history
    """
    
    def __init__(
        self,
        company_threshold: float = 0.85,
        job_threshold: float = 0.75,  # Stricter for job titles
        composite_threshold: float = 0.80  # Both must be high
    ):
        self.company_threshold = company_threshold
        self.job_threshold = job_threshold
        self.composite_threshold = composite_threshold
    
    def find_existing_application(
        self,
        company_name: str,
        job_title: str,
        thread_id: str,
        apps_cache: List[Dict]
    ) -> Optional[Dict]:
        """
        Find existing application using STRICT matching.
        
        Matching Priority:
        1. Exact company + job match (highest confidence)
        2. Fuzzy company + fuzzy job (BOTH must pass thresholds)
        3. Thread_id hint (only if job titles are similar)
        
        Returns application or None.
        """
        
        # Strategy 1: Exact Match (100% confidence)
        exact_match = self._match_exact(company_name, job_title, apps_cache)
        if exact_match:
            logger.debug(f"✓ Exact match: {exact_match['id']}")
            return exact_match
        
        # Strategy 2: Fuzzy Match (STRICT - both company AND job must match)
        fuzzy_match = self._match_fuzzy_strict(company_name, job_title, apps_cache)
        if fuzzy_match:
            logger.debug(f"✓ Fuzzy match: {fuzzy_match['id']}")
            return fuzzy_match
        
        # Strategy 3: Thread ID (only as weak hint)
        # NOTE: Gmail uses same thread_id for different jobs from same sender!
        # So we MUST verify job_title similarity before trusting thread_id
        thread_match = self._match_thread_with_job_check(
            company_name,
            job_title, 
            thread_id, 
            apps_cache
        )
        if thread_match:
            logger.debug(f"✓ Thread match (job verified): {thread_match['id']}")
            return thread_match
        
        logger.debug(f"✗ No match for: {company_name} / {job_title}")
        return None
    
    def _match_exact(
        self, 
        company_name: str, 
        job_title: str, 
        apps_cache: List[Dict]
    ) -> Optional[Dict]:
        """Exact string matching (case-insensitive)."""
        company_lower = company_name.lower().strip()
        job_lower = job_title.lower().strip()
        
        for app in apps_cache:
            if not app.get('is_active'):
                continue
            
            app_company = app.get('company_name', '').lower().strip()
            app_job = app.get('job_title', '').lower().strip()
            
            if company_lower == app_company and job_lower == app_job:
                return app
        
        return None
    
    def _match_fuzzy_strict(
        self,
        company_name: str,
        job_title: str,
        apps_cache: List[Dict]
    ) -> Optional[Dict]:
        """
        FIXED: Fuzzy matching with STRICT job title requirement.
        
        OLD (WRONG):
        composite = (company * 0.7) + (job * 0.3)
        Problem: Different jobs can still match if company is perfect
        
        NEW (CORRECT):
        - company_similarity >= 0.85 AND
        - job_similarity >= 0.75 AND  
        - composite >= 0.80
        
        This ensures:
        - "Support Consultant WCS" != "Absolventen SAP" (different jobs)
        - "Software Engineer" == "Software Engineer (Senior)" (same job, variant)
        """
        company_clean = self._normalize_company_name(company_name)
        job_clean = self._normalize_job_title(job_title)
        
        best_match = None
        best_score = 0.0
        
        for app in apps_cache:
            if not app.get('is_active'):
                continue
            
            app_company = self._normalize_company_name(app.get('company_name', ''))
            app_job = self._normalize_job_title(app.get('job_title', ''))
            
            company_sim = self._similarity(company_clean, app_company)
            job_sim = self._similarity(job_clean, app_job)
            
            # CRITICAL: BOTH thresholds must pass
            if company_sim < self.company_threshold:
                continue
            if job_sim < self.job_threshold:
                continue
            
            # Composite score (equal weighting now)
            composite_score = (company_sim * 0.5) + (job_sim * 0.5)
            
            if composite_score >= self.composite_threshold and composite_score > best_score:
                best_score = composite_score
                best_match = app
                logger.debug(
                    f"Candidate: {app['company_name']} / {app['job_title']} | "
                    f"Company: {company_sim:.2f}, Job: {job_sim:.2f}, "
                    f"Composite: {composite_score:.2f}"
                )
        
        if best_match:
            logger.info(
                f"✓ Fuzzy match: '{company_name}' + '{job_title}' → "
                f"'{best_match['company_name']}' + '{best_match['job_title']}' "
                f"(score: {best_score:.2f})"
            )
        
        return best_match
    
    def _match_thread_with_job_check(
        self,
        company_name: str,
        job_title: str,
        thread_id: str,
        apps_cache: List[Dict]
    ) -> Optional[Dict]:
        """
        Thread ID matching with MANDATORY job title verification.
        
        Problem: Gmail uses same thread_id for different jobs from same sender:
        - Körber Job 1 (thread A)
        - Körber Job 2 (thread A)  ← Same thread!
        
        Solution: Only trust thread_id if job titles are similar (>0.75)
        """
        for app in apps_cache:
            if not app.get('is_active'):
                continue
            
            if app.get('thread_id') == thread_id:
                # Found thread match - but verify it's the SAME job
                app_job = self._normalize_job_title(app.get('job_title', ''))
                email_job = self._normalize_job_title(job_title)
                
                job_sim = self._similarity(app_job, email_job)
                
                if job_sim >= self.job_threshold:
                    logger.info(
                        f"Thread match accepted: jobs similar enough "
                        f"(similarity: {job_sim:.2f})"
                    )
                    return app
                else:
                    logger.warning(
                        f"Thread match REJECTED: different jobs detected\n"
                        f"  Existing: {app.get('job_title')}\n"
                        f"  Email: {job_title}\n"
                        f"  Similarity: {job_sim:.2f} < {self.job_threshold}"
                    )
                    # Don't return - continue searching for actual match
        
        return None
    
    def _normalize_company_name(self, name: str) -> str:
        """Normalize company names for matching."""
        suffixes = [
            ' gmbh', ' ag', ' inc', ' ltd', ' llc', 
            ' corporation', ' corp', ' group', ' se'
        ]
        name_lower = name.lower().strip()
        
        for suffix in suffixes:
            if name_lower.endswith(suffix):
                name_lower = name_lower[:-len(suffix)].strip()
        
        # German umlauts
        replacements = {
            'ä': 'a', 'ö': 'o', 'ü': 'u', 'ß': 'ss',
            '&': 'and', '-': ' ', '_': ' '
        }
        for old, new in replacements.items():
            name_lower = name_lower.replace(old, new)
        
        return ' '.join(name_lower.split())
    
    def _normalize_job_title(self, title: str) -> str:
        """
        Normalize job titles for matching.
        
        IMPORTANT: Do NOT over-normalize!
        "Support Consultant WCS" should NOT match "SAP Logistik"
        
        Only remove:
        - Seniority markers (Senior, Junior, Lead)
        - Gendered markers (m/w/d in German)
        - Extra whitespace
        """
        title_lower = title.lower().strip()
        
        # Remove seniority prefixes (but keep core title intact)
        seniority = ['senior', 'junior', 'lead', 'principal', 'staff']
        words = title_lower.split()
        words = [w for w in words if w not in seniority]
        
        # Remove German gender markers
        title_lower = ' '.join(words)
        title_lower = title_lower.replace('(m/w/d)', '').replace('m/w/d', '')
        
        return ' '.join(title_lower.split())
    
    def _similarity(self, a: str, b: str) -> float:
        """Calculate similarity ratio."""
        return SequenceMatcher(None, a, b).ratio()


# ══════════════════════════════════════════════════════════════
# Integration with tracker.py
# ══════════════════════════════════════════════════════════════

def upsert_application_fixed(
    client,
    user_id: str,
    email,
    classification,
    apps_cache: List[Dict],
    matcher: ApplicationMatcher
) -> str:
    """
    FIXED upsert logic with strict job title matching.
    
    Returns: 'added' or 'updated'
    """
    
    existing_app = matcher.find_existing_application(
        company_name=classification.company_name,
        job_title=classification.job_title,
        thread_id=email.thread_id,
        apps_cache=apps_cache
    )
    
    if existing_app:
        # ═══ UPDATE: Same job, append to history ═══
        display_status = CLASSIFICATION_TO_STATUS.get(classification.classification)
        if display_status is None:
            display_status = str(classification.classification)

        status_update = {
            "timestamp": str(email.date),
            "status": str(display_status),
            "email_subject": email.subject,
            "source_email_id": email.email_id,
            "confidence": classification.confidence
        }
        
        # Get current history
        current_history = existing_app.get('status_history', [])
        if isinstance(current_history, str):
            import json
            current_history = json.loads(current_history)
        
        current_history.append(status_update)
        
        # Update application
        client.table("applications").update({
            "status": str(display_status),
            "status_history": current_history,
            "email_count": len(current_history),
            "last_updated": "now()",
            "email_subject": email.subject,  # Latest email subject
            "source_email_id": email.email_id  # Latest email ID
        }).eq("id", existing_app['id']).execute()
        
        logger.info(
            f"✓ UPDATED: {classification.company_name} / {classification.job_title} "
            f"(now {len(current_history)} emails)"
        )
        return "updated"
    
    else:
        # ═══ CREATE: New job application ═══
        display_status = CLASSIFICATION_TO_STATUS.get(classification.classification)
        if display_status is None:
            display_status = str(classification.classification)

        initial_status = {
            "timestamp": str(email.date),
            "status": str(display_status),
            "email_subject": email.subject,
            "source_email_id": email.email_id,
            "confidence": classification.confidence
        }
        
        client.table("applications").insert({
            "user_id": user_id,
            "thread_id": email.thread_id,
            "company_name": classification.company_name,
            "job_title": classification.job_title,
            "platform": classification.platform,
            "status": str(display_status),
            "confidence": classification.confidence,
            "email_subject": email.subject,
            "email_from": email.sender_email,
            "date_applied": str(email.date),
            "gmail_link": email.gmail_link,
            "source_email_id": email.email_id,
            "status_history": [initial_status],
            "email_count": 1,
            "is_active": True
        }).execute()
        
        logger.info(
            f"✓ ADDED: {classification.company_name} / {classification.job_title}"
        )
        return "added"


# ══════════════════════════════════════════════════════════════
# Test Cases (for validation)
# ══════════════════════════════════════════════════════════════

"""
Test Case 1: Körber - 3 Different Jobs
-----------------------------------
Email 1: Support Consultant WCS (thread 19d368b)
Email 2: Absolventen SAP (thread 19d392ac)  
Email 3: Karriere SAP (thread 19d393be)

Expected Result: 3 separate applications

Email 4: Rejection for Support WCS (different thread!)
Expected: UPDATE application 1 (job title matches)

Email 5: Rejection for Absolventen SAP
Expected: UPDATE application 2

Email 6: Rejection for Karriere SAP  
Expected: UPDATE application 3

Final State:
- App 1: Support WCS, email_count=2 (confirm + reject)
- App 2: Absolventen SAP, email_count=2 (confirm + reject)
- App 3: Karriere SAP, email_count=2 (confirm + reject)
"""
