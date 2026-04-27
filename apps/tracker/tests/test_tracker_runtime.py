from datetime import date

import pytest

import tracker
from gmail_service import _decrypt_data, _encrypt_data
from models import EmailMetadata, FollowUpReminderItem
from telegram_notifier import _build_follow_up_message
from tracker import _select_emails_for_current_run


def _email(email_id: str) -> EmailMetadata:
    return EmailMetadata(
        email_id=email_id,
        thread_id=f"thread-{email_id}",
        subject=f"Subject {email_id}",
        sender="Recruiter",
        sender_email="jobs@example.com",
        date=date(2025, 1, 1),
        body="Hello",
    )


def test_select_emails_for_current_run_prioritizes_recovered_items():
    emails = [_email("fresh-1"), _email("recovered-1"), _email("fresh-2"), _email("recovered-2")]

    selected, deferred = _select_emails_for_current_run(
        emails,
        recovered_email_ids={"recovered-1", "recovered-2"},
        max_emails_per_run=2,
    )

    assert [email.email_id for email in selected] == ["recovered-1", "recovered-2"]
    assert deferred == ["fresh-1", "fresh-2"]


def test_build_follow_up_message_includes_summary_and_escapes_names():
    message = _build_follow_up_message(
        [
            FollowUpReminderItem(
                application_id="app-1",
                company_name="ACME_[Labs]",
                job_title="Data Scientist",
                date_applied=date(2025, 1, 10),
            )
        ],
        reminder_days=14,
    )

    assert "14 days" in message
    assert "ACME\\_\\[Labs\\]" in message
    assert "Data Scientist" in message


def test_run_ingestion_stage_surfaces_underlying_gmail_error(monkeypatch):
    monkeypatch.setattr(tracker, "update_pipeline_step", lambda *args, **kwargs: None)
    monkeypatch.setattr(tracker, "log_to_db", lambda *args, **kwargs: None)
    monkeypatch.setattr(tracker, "get_existing_email_ids_for_user", lambda *args, **kwargs: set())

    def raise_gmail_error(*args, **kwargs):
        raise RuntimeError(
            "Stored Gmail credentials for user test@example.com could not be loaded: "
            "Decrypted credentials data is empty. Decryption may have failed due to a mismatched ENCRYPTION_SECRET."
        )

    monkeypatch.setattr(tracker, "get_gmail_service_for_user", raise_gmail_error)

    with pytest.raises(RuntimeError, match="mismatched ENCRYPTION_SECRET"):
        tracker._run_ingestion_stage(
            client=object(),
            user={"id": "user-1", "email": "test@example.com"},
            user_id="user-1",
            since_date=None,
            run_id="run-1",
            internal_id=None,
            sync_mode="backfill",
        )


def test_decrypt_data_accepts_unpadded_base64url(monkeypatch):
    monkeypatch.setattr("gmail_service.settings.encryption_secret", "shared-secret")
    monkeypatch.setattr("gmail_service.settings.encryption_key", "")

    encrypted = _encrypt_data(
        {
            "token": "token-value",
            "refresh_token": "refresh-token",
            "client_id": "client-id",
            "client_secret": "client-secret",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    )
    prefix, iv_b64, payload_b64 = encrypted.split(":", 2)
    unpadded = f"{prefix}:{iv_b64.rstrip('=')}:{payload_b64.rstrip('=')}"

    decrypted = _decrypt_data(unpadded)

    assert decrypted["refresh_token"] == "refresh-token"
    assert decrypted["client_secret"] == "client-secret"
