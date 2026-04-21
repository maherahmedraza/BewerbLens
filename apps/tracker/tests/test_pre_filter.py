from datetime import date
from unittest.mock import MagicMock

from models import EmailMetadata
from pre_filter import apply_user_filters


def _make_mock_client(filters=None):
    """Create a mock Supabase client that returns the given filters."""
    client = MagicMock()
    mock_result = MagicMock()
    mock_result.data = filters or []
    (
        client.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .order.return_value
        .execute.return_value
    ) = mock_result
    return client


def test_no_filters_allows_all():
    """When user has no active filters, all emails pass through."""
    client = _make_mock_client(filters=[])
    emails = [
        EmailMetadata(
            email_id="1", thread_id="t1",
            sender="recruiter@company.com",
            subject="Interview Invitation",
            body="...", date=date(2026, 4, 11)
        )
    ]

    filtered, stats = apply_user_filters(client, "test-user-id", emails)
    assert len(filtered) == 1
    assert stats.filtered == 0


def test_exclude_filter_blocks_matching_emails():
    """Emails matching an EXCLUDE filter should be removed."""
    client = _make_mock_client(filters=[
        {
            "filter_type": "EXCLUDE",
            "field": "sender",
            "pattern": "no-reply@linkedin.com",
            "is_active": True,
            "priority": 1,
        }
    ])
    emails = [
        EmailMetadata(
            email_id="1", thread_id="t1",
            sender="no-reply@linkedin.com",
            subject="New Job Alert",
            body="...", date=date(2026, 4, 11)
        ),
        EmailMetadata(
            email_id="2", thread_id="t2",
            sender="recruiter@company.com",
            subject="Interview Invitation",
            body="...", date=date(2026, 4, 11)
        )
    ]

    filtered, stats = apply_user_filters(client, "test-user-id", emails)
    assert any(e.email_id == "2" for e in filtered)
    assert stats.filtered >= 1


def test_platform_allowlist_bypasses_include_and_exclude_filters():
    client = _make_mock_client(filters=[
        {
            "filter_type": "INCLUDE",
            "field": "subject",
            "pattern": "interview",
            "is_active": True,
            "priority": 1,
        },
        {
            "filter_type": "EXCLUDE",
            "field": "sender",
            "pattern": "linkedin.com",
            "is_active": True,
            "priority": 10,
        },
        {
            "filter_type": "platform_allowlist",
            "field": "sender",
            "pattern": "jobs-noreply@linkedin.com",
            "is_active": True,
            "priority": -100,
        },
    ])
    emails = [
        EmailMetadata(
            email_id="1",
            thread_id="t1",
            sender="jobs-noreply@linkedin.com",
            sender_email="jobs-noreply@linkedin.com",
            subject="Your application was sent to Example GmbH",
            body="...",
            date=date(2026, 4, 11),
        )
    ]

    filtered, stats = apply_user_filters(client, "test-user-id", emails)

    assert len(filtered) == 1
    assert stats.filtered == 0
