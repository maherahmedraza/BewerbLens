# ╔══════════════════════════════════════════════════════════════╗
# ║  Pydantic Models — Structured data schema                   ║
# ║  Replaces the fragile JSON strings from the n8n workflow.   ║
# ║  Gemini MUST return data that matches this schema.          ║
# ║  v2.0: Added location, job_listing_url, salary_range fields ║
# ╚══════════════════════════════════════════════════════════════╝

from datetime import date as DateType, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Classification(str, Enum):
    """Possible classification types for an email."""
    APPLICATION_CONFIRMATION = "application_confirmation"
    REJECTION = "rejection"
    POSITIVE_RESPONSE = "positive_response"
    NOT_JOB_RELATED = "not_job_related"


class Status(str, Enum):
    """Possible statuses for a job application."""
    APPLIED = "Applied"
    REJECTED = "Rejected"
    POSITIVE_RESPONSE = "Positive Response"
    INTERVIEW = "Interview"
    OFFER = "Offer"


# Mapping of classification -> status
CLASSIFICATION_TO_STATUS: dict[Classification, Optional[Status]] = {
    Classification.APPLICATION_CONFIRMATION: Status.APPLIED,
    Classification.REJECTION: Status.REJECTED,
    Classification.POSITIVE_RESPONSE: Status.POSITIVE_RESPONSE,
    Classification.NOT_JOB_RELATED: None,
}

# Status priority for update logic
# Rejected=99: can overwrite everything except Offer
STATUS_PRIORITY: dict[Status, int] = {
    Status.APPLIED: 1,
    Status.POSITIVE_RESPONSE: 2,
    Status.INTERVIEW: 3,
    Status.OFFER: 100,
    Status.REJECTED: 99,
}


class EmailClassification(BaseModel):
    """
    Classification result for a single email by Gemini.
    This is the schema Gemini must return for each email.
    v2.0: Added location, job_listing_url, salary_range fields.
    """
    email_index: int = Field(description="Index of the email in the batch (1-based)")
    classification: Classification = Field(
        description="Email type: application_confirmation, rejection, positive_response, or not_job_related"
    )
    company_name: str = Field(
        description="Name of the hiring company. NEVER use ATS names like Personio or SmartRecruiters."
    )
    job_title: str = Field(
        default="Not Specified",
        description="Exact job title"
    )
    platform: str = Field(
        default="Direct",
        description="Source platform: SmartRecruiters, LinkedIn, Personio, Direct, etc."
    )
    location: str = Field(
        default="",
        description="City or region of the job (e.g., 'Stuttgart', 'Remote', 'München'). Empty if not mentioned."
    )
    job_listing_url: str = Field(
        default="",
        description="URL to the job posting if found in the email body. Empty if not found."
    )
    salary_range: str = Field(
        default="",
        description="Salary range if mentioned (e.g., '60k-75k', 'EUR 50,000'). Empty if not found."
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence level: 0.9+ very clear, 0.7-0.89 likely, 0.55-0.69 uncertain"
    )
    reasoning: str = Field(
        default="",
        description="Brief justification for the classification"
    )


class GeminiBatchResponse(BaseModel):
    """Complete Gemini response for a batch of emails."""
    results: list[EmailClassification]


class EmailMetadata(BaseModel):
    """Metadata extracted from a Gmail email."""
    email_id: str
    thread_id: str
    subject: str = ""
    sender: str = ""
    sender_email: str = ""
    date: DateType = Field(default_factory=DateType.today)
    body: str = ""

    @property
    def gmail_link(self) -> str:
        """Generates a direct link to this email in Gmail."""
        return f"https://mail.google.com/mail/u/0/#inbox/{self.email_id}"


class ApplicationRecord(BaseModel):
    """Job application record for Supabase (Silver layer)."""
    thread_id: str
    company_name: str
    job_title: str = "Not Specified"
    platform: str = "Direct"
    status: str
    confidence: float = 0.0
    email_subject: str = ""
    email_from: str = ""
    date_applied: DateType = Field(default_factory=DateType.today)
    last_updated: Optional[datetime] = None
    notes: str = ""
    # v2.0 new fields
    gmail_link: str = ""
    job_listing_url: str = ""
    location: str = ""
    salary_range: str = ""
    source_email_id: str = ""


class ProcessingLog(BaseModel):
    """Processing log entry for audit trail."""
    thread_id: str = ""
    email_subject: str = ""
    classification_result: str = ""
    error_message: str = ""


class RawEmailRecord(BaseModel):
    """Raw email record for Bronze layer storage."""
    email_id: str
    thread_id: str
    subject: str = ""
    sender: str = ""
    sender_email: str = ""
    body_preview: str = ""
    email_date: DateType = Field(default_factory=DateType.today)
    gmail_link: str = ""
