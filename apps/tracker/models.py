# ╔══════════════════════════════════════════════════════════════╗
# ║  Pydantic Models — Structured data schema                   ║
# ║  v2.1: Added NotificationAction enum (fixes stringly-typed  ║
# ║  action parameter in telegram_notifier.py)                  ║
# ╚══════════════════════════════════════════════════════════════╝

from datetime import date as DateType, datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Classification(str, Enum):
    APPLICATION_CONFIRMATION = "application_confirmation"
    REJECTION = "rejection"
    POSITIVE_RESPONSE = "positive_response"
    NOT_JOB_RELATED = "not_job_related"


class Status(str, Enum):
    APPLIED = "Applied"
    REJECTED = "Rejected"
    POSITIVE_RESPONSE = "Positive Response"
    INTERVIEW = "Interview"
    OFFER = "Offer"


class NotificationAction(str, Enum):
    """
    Typed action enum for telegram_notifier.send_notification().
    Replaces the stringly-typed action: str parameter.
    Fixes: review issue #16.
    """
    ADDED = "added"
    UPDATED = "updated"
    ERROR = "error"


class PipelineStage(str, Enum):
    INGESTION = "ingestion"
    ANALYSIS = "analysis"
    PERSISTENCE = "persistence"


PIPELINE_STAGE_ORDER: tuple[PipelineStage, ...] = (
    PipelineStage.INGESTION,
    PipelineStage.ANALYSIS,
    PipelineStage.PERSISTENCE,
)


CLASSIFICATION_TO_STATUS: dict[Classification, Optional[Status]] = {
    Classification.APPLICATION_CONFIRMATION: Status.APPLIED,
    Classification.REJECTION: Status.REJECTED,
    Classification.POSITIVE_RESPONSE: Status.POSITIVE_RESPONSE,
    Classification.NOT_JOB_RELATED: None,
}

# Status priority for update logic.
# OFFER(100) is the terminal positive state — nothing overwrites it.
# REJECTED(99) can overwrite all non-terminal states.
# INTERVIEW(3) > POSITIVE_RESPONSE(2) > APPLIED(1).
STATUS_PRIORITY: dict[Status, int] = {
    Status.APPLIED: 1,
    Status.POSITIVE_RESPONSE: 2,
    Status.INTERVIEW: 3,
    Status.OFFER: 100,
    Status.REJECTED: 99,
}


class EmailClassification(BaseModel):
    email_index: int = Field(description="Index of the email in the batch (1-based)")
    classification: Classification
    company_name: str
    job_title: str = Field(default="Not Specified")
    platform: str = Field(default="Direct")
    location: str = Field(default="")
    job_listing_url: str = Field(default="")
    salary_range: str = Field(default="")
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(default="")


class GeminiBatchResponse(BaseModel):
    results: list[EmailClassification]


class IngestionStageStats(BaseModel):
    email_ids: list[str] = Field(default_factory=list)
    total_fetched: int = 0
    total_recovered: int = 0
    total_after_filters: int = 0


class AnalysisStageStats(BaseModel):
    email_ids: list[str] = Field(default_factory=list)
    classifications: list[EmailClassification] = Field(default_factory=list)
    total_classified: int = 0


class PersistenceStageStats(BaseModel):
    email_ids: list[str] = Field(default_factory=list)
    added: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    report: Optional["PipelineRunReport"] = Field(default=None, exclude=True)


class PipelineRunReport(BaseModel):
    """Consolidated report data for Telegram notification."""
    added: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    added_companies: list[str] = Field(default_factory=list)
    updated_companies: list[str] = Field(default_factory=list)
    status_counts: dict[str, int] = Field(default_factory=dict)
    error_messages: list[str] = Field(default_factory=list)
    run_label: str = ""
    user_email: str = ""
    duration_seconds: float = 0.0


class EmailMetadata(BaseModel):
    email_id: str
    thread_id: str
    subject: str = ""
    sender: str = ""
    sender_email: str = ""
    date: DateType = Field(default_factory=DateType.today)
    body: str = ""

    @property
    def gmail_link(self) -> str:
        return f"https://mail.google.com/mail/u/0/#inbox/{self.email_id}"


class ApplicationRecord(BaseModel):
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
    gmail_link: str = ""
    job_listing_url: str = ""
    location: str = ""
    salary_range: str = ""
    source_email_id: str = ""
    status_history: list[dict] = Field(default_factory=list)


class ProcessingLog(BaseModel):
    thread_id: str = ""
    email_subject: str = ""
    classification_result: str = ""
    error_message: str = ""


class RawEmailRecord(BaseModel):
    email_id: str
    thread_id: str
    subject: str = ""
    sender: str = ""
    sender_email: str = ""
    body_preview: str = ""
    email_date: DateType = Field(default_factory=DateType.today)
    gmail_link: str = ""
