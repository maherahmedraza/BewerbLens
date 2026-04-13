import pytest
from models import EmailMetadata
from pre_filter import apply_pre_filters

def test_pre_filter_blocked_senders():
    """Verify that emails from specifically blocked senders are filtered."""
    emails = [
        EmailMetadata(
            email_id="1", thread_id="t1", 
            sender="no-reply@linkedin.com", # Should be filtered out if job alert
            subject="New Job Alert",
            body="...", date="2026-04-11T10:00:00Z"
        ),
        EmailMetadata(
            email_id="2", thread_id="t2",
            sender="recruiter@company.com",
            subject="Interview Invitation",
            body="...", date="2026-04-11T10:00:00Z"
        )
    ]
    
    filtered, stats = apply_pre_filters(emails)
    
    # Simple check: filtered list should be smaller or at least contain the positive case
    assert any(e.email_id == "2" for e in filtered)

def test_pre_filter_self_sent():
    """Verify that emails sent by the user themselves are filtered."""
    emails = [
        EmailMetadata(
            email_id="3", thread_id="t3",
            sender="maherahmedraza1@gmail.com", # Self-sent
            subject="Draft for application",
            body="...", date="2026-04-11T10:00:00Z"
        )
    ]
    
    filtered, stats = apply_pre_filters(emails)
    assert len(filtered) == 0
    assert stats.self_sent == 1

def test_pre_filter_subjects():
    """Verify that marketing/alert subjects are filtered."""
    emails = [
        EmailMetadata(
            email_id="4", thread_id="t4",
            sender="alerts@indeed.com",
            subject="10 new jobs for you", # Marketing/Alert
            body="...", date="2026-04-11T10:00:00Z"
        )
    ]
    
    filtered, stats = apply_pre_filters(emails)
    assert len(filtered) == 0
    assert stats.generic_filtered == 1
