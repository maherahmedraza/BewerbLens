from datetime import date

from gmail_service import _build_query


def test_build_query_uses_broad_job_terms_without_sender_exclusions():
    query = _build_query(date(2026, 4, 1))

    assert "after:2026/04/01" in query
    assert '"your application"' in query
    assert "bewerbung" in query
    assert '"thank you for your interest"' in query
    assert '"moving forward"' in query
    assert "-from:" not in query
    assert "is:unread" not in query


def test_build_query_adds_unread_clause_only_when_requested():
    query = _build_query(date(2026, 4, 1), only_unread=True)

    assert "after:2026/04/01" in query
    assert "is:unread" in query
