# ╔══════════════════════════════════════════════════════════════╗
# ║  Pre-Filter (Multi-User) — Database-Driven Filters          ║
# ║                                                             ║
# ║  Queries email_filters table per user_id                    ║
# ║  Replaces hardcoded filter logic                            ║
# ╚══════════════════════════════════════════════════════════════╝

import re
from typing import List, Tuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class FilterStats:
    """Statistics from filtering operation."""
    total: int
    passed: int
    filtered: int
    details: List[dict]


def apply_user_filters(client, user_id: str, emails: List) -> Tuple[List, FilterStats]:
    """
    Apply user-specific email filters from database.
    
    Args:
        client: Supabase client
        user_id: User UUID
        emails: List of Email objects
    
    Returns:
        (filtered_emails, stats)
    
    Filter Logic:
    1. Fetch user's active filters from email_filters table
    2. Apply INCLUDE filters first (whitelist)
    3. Apply EXCLUDE filters second (blacklist)
    4. Filters are processed by priority (lower number = higher priority)
    """
    
    # Fetch user's filters
    filters_result = client.table("email_filters").select("*").eq(
        "user_id", user_id
    ).eq(
        "is_active", True
    ).order("priority", desc=False).execute()
    
    filters = filters_result.data
    
    if not filters:
        logger.warning(f"No active filters for user {user_id}. Allowing all emails.")
        return emails, FilterStats(
            total=len(emails),
            passed=len(emails),
            filtered=0,
            details=[]
        )
    
    logger.info(f"Applying {len(filters)} filters for user {user_id}")
    
    # Separate INCLUDE and EXCLUDE filters
    include_filters = [f for f in filters if f['filter_type'] == 'include']
    exclude_filters = [f for f in filters if f['filter_type'] == 'exclude']
    
    passed = []
    details = []
    
    for email in emails:
        # Step 1: Check INCLUDE filters (whitelist)
        if include_filters:
            if not _matches_any_filter(email, include_filters):
                details.append({
                    "subject": email.subject,
                    "from": email.sender_email,
                    "reason": "No INCLUDE filter matched"
                })
                continue  # Skip this email
        
        # Step 2: Check EXCLUDE filters (blacklist)
        if exclude_filters:
            if _matches_any_filter(email, exclude_filters):
                details.append({
                    "subject": email.subject,
                    "from": email.sender_email,
                    "reason": "EXCLUDE filter matched"
                })
                continue  # Skip this email
        
        # Passed all filters
        passed.append(email)
    
    stats = FilterStats(
        total=len(emails),
        passed=len(passed),
        filtered=len(emails) - len(passed),
        details=details
    )
    
    logger.info(
        f"Filter results: {stats.passed}/{stats.total} passed "
        f"({stats.filtered} filtered out)"
    )
    
    return passed, stats


def _matches_any_filter(email, filters: List[dict]) -> bool:
    """
    Check if email matches ANY filter in the list.
    
    Args:
        email: Email object
        filters: List of filter dicts from database
    
    Returns:
        True if email matches at least one filter
    """
    for filter_rule in filters:
        if _matches_filter(email, filter_rule):
            logger.debug(
                f"Email '{email.subject}' matched filter: "
                f"{filter_rule['field']} {filter_rule['pattern']}"
            )
            return True
    
    return False


def _matches_filter(email, filter_rule: dict) -> bool:
    """
    Check if email matches a single filter rule.
    
    Args:
        email: Email object
        filter_rule: Filter dict with keys: field, pattern, is_regex
    
    Returns:
        True if email matches the filter
    """
    field = filter_rule['field']
    pattern = filter_rule['pattern']
    is_regex = filter_rule.get('is_regex', False)
    
    # Get email field value
    if field == 'subject':
        text = email.subject
    elif field == 'sender':
        text = email.sender_email or email.sender
    elif field == 'body':
        text = email.body
    else:
        logger.warning(f"Unknown filter field: {field}")
        return False
    
    # Case-insensitive matching
    text = text.lower()
    pattern = pattern.lower()
    
    # Apply pattern matching
    if is_regex:
        try:
            return bool(re.search(pattern, text))
        except re.error as e:
            logger.error(f"Invalid regex pattern '{pattern}': {e}")
            return False
    else:
        # Simple substring matching
        return pattern in text


# ══════════════════════════════════════════════════════════════
# Filter Management Helpers
# ══════════════════════════════════════════════════════════════

def get_user_filters(client, user_id: str) -> List[dict]:
    """
    Get all active filters for a user.
    
    Returns:
        List of filter dicts
    """
    result = client.table("email_filters").select("*").eq(
        "user_id", user_id
    ).eq(
        "is_active", True
    ).order("priority").execute()
    
    return result.data


def create_default_filters_for_user(client, user_id: str, region: str = 'en'):
    """
    Create default email filters for a new user.
    
    Args:
        client: Supabase client
        user_id: User UUID
        region: User's region (en, de, fr, es)
    
    This is called automatically when:
    1. User signs up
    2. User changes region in settings
    """
    
    # Delete existing filters
    client.table("email_filters").delete().eq("user_id", user_id).execute()
    
    # English defaults
    if region == 'en':
        filters = [
            # INCLUDE patterns
            {'filter_type': 'include', 'field': 'subject', 'pattern': 'application', 'priority': 1},
            {'filter_type': 'include', 'field': 'subject', 'pattern': 'applied', 'priority': 1},
            {'filter_type': 'include', 'field': 'subject', 'pattern': 'confirmation', 'priority': 1},
            {'filter_type': 'include', 'field': 'subject', 'pattern': 'thank you for applying', 'priority': 1},
            {'filter_type': 'include', 'field': 'subject', 'pattern': 'interview', 'priority': 2},
            {'filter_type': 'include', 'field': 'subject', 'pattern': 'offer', 'priority': 2},
            {'filter_type': 'include', 'field': 'subject', 'pattern': 'rejection', 'priority': 3},
            {'filter_type': 'include', 'field': 'subject', 'pattern': 'unfortunately', 'priority': 3},
            
            # EXCLUDE patterns
            {'filter_type': 'exclude', 'field': 'sender', 'pattern': 'noreply@linkedin.com', 'priority': 10},
            {'filter_type': 'exclude', 'field': 'subject', 'pattern': 'job alert', 'priority': 10},
            {'filter_type': 'exclude', 'field': 'subject', 'pattern': 'recommended for you', 'priority': 10},
        ]
    
    # German defaults
    elif region == 'de':
        filters = [
            # INCLUDE patterns
            {'filter_type': 'include', 'field': 'subject', 'pattern': 'bewerbung', 'priority': 1},
            {'filter_type': 'include', 'field': 'subject', 'pattern': 'beworben', 'priority': 1},
            {'filter_type': 'include', 'field': 'subject', 'pattern': 'eingangsbestätigung', 'priority': 1},
            {'filter_type': 'include', 'field': 'subject', 'pattern': 'bestätigung', 'priority': 1},
            {'filter_type': 'include', 'field': 'subject', 'pattern': 'interview', 'priority': 2},
            {'filter_type': 'include', 'field': 'subject', 'pattern': 'gespräch', 'priority': 2},
            {'filter_type': 'include', 'field': 'subject', 'pattern': 'absage', 'priority': 3},
            {'filter_type': 'include', 'field': 'subject', 'pattern': 'leider', 'priority': 3},
            {'filter_type': 'include', 'field': 'subject', 'pattern': 'rückmeldung', 'priority': 3},
            
            # EXCLUDE patterns
            {'filter_type': 'exclude', 'field': 'sender', 'pattern': 'noreply@linkedin.com', 'priority': 10},
            {'filter_type': 'exclude', 'field': 'subject', 'pattern': 'jobalarm', 'priority': 10},
        ]
    
    else:
        logger.warning(f"Unknown region '{region}'. Using empty filters.")
        filters = []
    
    # Insert filters
    for filter_data in filters:
        client.table("email_filters").insert({
            "user_id": user_id,
            **filter_data,
            "is_regex": False,
            "is_active": True
        }).execute()
    
    logger.success(f"Created {len(filters)} default filters for user {user_id} (region: {region})")


# ══════════════════════════════════════════════════════════════
# Testing Utility
# ══════════════════════════════════════════════════════════════

def test_filter_against_email(filter_rule: dict, email_subject: str, email_sender: str) -> bool:
    """
    Test a filter rule against sample email data.
    
    Args:
        filter_rule: Filter dict with field, pattern, is_regex
        email_subject: Test subject line
        email_sender: Test sender email
    
    Returns:
        True if email matches the filter
    
    Usage:
        # In your UI, let users preview filter matches
        filter = {"field": "subject", "pattern": "bewerbung", "is_regex": False}
        matches = test_filter_against_email(filter, "Ihre Bewerbung", "hr@company.com")
    """
    from models import EmailMetadata
    
    # Create mock email object
    mock_email = EmailMetadata(
        email_id="test",
        thread_id="test",
        subject=email_subject,
        sender=email_sender,
        sender_email=email_sender,
        body="",
        date=None,
        raw_headers={}
    )
    
    return _matches_filter(mock_email, filter_rule)
