import pytest
from models import EmailMetadata
from typing import List

@pytest.fixture
def mock_emails() -> List[EmailMetadata]:
    return [
        EmailMetadata(
            email_id="1",
            thread_id="t1",
            subject="Job Application - Software Engineer",
            sender="Example Corp <hr@example.com>",
            sender_email="hr@example.com",
            body="Thank you for applying..."
        ),
        EmailMetadata(
            email_id="2",
            thread_id="t2",
            subject="Automated message",
            sender="No Reply <noreply@notajob.com>",
            sender_email="noreply@notajob.com",
            body="Your request was received."
        ),
        EmailMetadata(
            email_id="3",
            thread_id="t3",
            subject="Application remote role",
            sender="ATS <app@greenhouse.io>",
            sender_email="app@greenhouse.io",
            body="We have your resume."
        )
    ]
