# ╔══════════════════════════════════════════════════════════════╗
# ║  Gmail Service — Connection and email extraction            ║
# ║  Replaces the "Build Gmail Queries" and                     ║
# ║  "Fetch Emails (Per Month)" nodes from the n8n workflow.    ║
# ║                                                             ║
# ║  Key difference: uses an incremental checkpoint instead of  ║
# ║  refetching all historical emails every time.               ║
# ║  v2.0: Uses BatchHttpRequest for 5x faster fetching.        ║
# ╚══════════════════════════════════════════════════════════════╝

import json
import base64
import re
from collections.abc import Callable
from datetime import date, datetime
from itertools import islice
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import BatchHttpRequest
from loguru import logger

from config import settings
from models import EmailMetadata

# Required scopes — read-only Gmail access
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Batch size for Gmail API (10 is conservative to avoid 429 rate limits)
GMAIL_BATCH_SIZE = 10

# Senders to exclude directly in the Gmail query (server-side filtering)
QUERY_EXCLUDED_SENDERS = [
    "jobalerts-noreply@linkedin.com",
    "info@jobagent.stepstone.de",
    "jobalert@indeed.com",
    "alert@indeed.com",
    "noreply@indeed.com",
    "news@mail.xing.com",
]

# Keywords to search for job application emails
JOB_KEYWORDS = [
    "bewerbung", "application", "absage", "rejection",
    "einladung", "interview", "eingangsbestätigung",
    "eingangsbestaetigung", "angebot", "offer",
    '"thank you for applying"', '"we received"',
    '"ihre bewerbung"', '"deine bewerbung"',
]

def _authenticate() -> Credentials:
    """
    Authenticates with Google OAuth2.
    Prioritizes JSON strings from environment variables (Settings),
    falling back to local files if necessary.
    """
    creds = None
    
    # 1. Try to load token from environment variable (JSON string)
    if settings.gmail_token_json:
        logger.info("Loading Gmail token from environment variable")
        try:
            token_info = json.loads(settings.gmail_token_json)
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
        except Exception as e:
            logger.error(f"Failed to load GMAIL_TOKEN_JSON: {e}")

    # 2. Fallback to local token file
    if not creds:
        token_path = Path(settings.gmail_token_path)
        if token_path.exists():
            logger.info(f"Loading Gmail token from {token_path}")
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    # 3. If no valid token, refresh or generate a new one
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            logger.info("Refreshing expired Gmail token")
            creds.refresh(Request())
        else:
            # Load Client Secrets
            client_config = None
            if settings.gmail_credentials_json:
                logger.info("Loading client secrets from environment variable")
                try:
                    client_config = json.loads(settings.gmail_credentials_json)
                except Exception as e:
                    logger.error(f"Failed to parse GMAIL_CREDENTIALS_JSON: {e}")
            
            if not client_config:
                creds_path = Path(settings.gmail_credentials_path)
                if not creds_path.exists():
                    raise FileNotFoundError(
                        f"Could not find credentials in environment or at {creds_path}. "
                        "Download credentials.json from Google Cloud Console."
                    )
                logger.info(f"Loading client secrets from {creds_path}")
                with open(creds_path) as f:
                    client_config = json.load(f)

            logger.info("Starting OAuth flow for Gmail")
            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=8080, open_browser=False)

        # 4. Handle token persistence
        # We don't write to file if we are using environment-based secrets
        new_token_json = creds.to_json()
        if settings.gmail_token_json:
            logger.warning("Gmail token was refreshed/generated. PLEASE UPDATE YOUR GMAIL_TOKEN_JSON ENV VAR WITH:")
            logger.info(new_token_json)
        else:
            token_path = Path(settings.gmail_token_path)
            token_path.write_text(new_token_json)
            logger.info(f"Gmail token saved to {token_path}")

    return creds


def _build_query(after_date: date) -> str:
    """
    Builds the Gmail search query.
    Uses only `after:` with the last checkpoint date,
    eliminating the need for monthly chunks.
    """
    keywords_clause = " OR ".join(JOB_KEYWORDS)
    exclusions = " ".join(f"-from:{s}" for s in QUERY_EXCLUDED_SENDERS)
    after_str = after_date.strftime("%Y/%m/%d")

    query = f"({keywords_clause}) {exclusions} after:{after_str}"
    logger.info(f"Gmail query built with after:{after_str}")
    return query


def _extract_body(payload: dict) -> str:
    """
    Extracts the plain text body from a Gmail message.
    Recursively navigates MIME parts to find text/plain.
    """
    max_length = 800

    # Simple case: body directly in payload
    if payload.get("body", {}).get("data"):
        try:
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")[:max_length]
        except Exception:
            pass

    # Complex case: search in MIME parts
    parts = payload.get("parts", [])
    for part in parts:
        mime_type = part.get("mimeType", "")

        if mime_type == "text/plain" and part.get("body", {}).get("data"):
            try:
                return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")[:max_length]
            except Exception:
                continue

        # Nested parts (multipart/alternative, etc.)
        if part.get("parts"):
            nested_body = _extract_body(part)
            if nested_body:
                return nested_body

    return ""


def _extract_sender_email(from_header: str) -> str:
    """Extracts just the email address from a From header."""
    match = re.search(r"<([^>]+)>", from_header)
    return (match.group(1) if match else from_header).lower().strip()


def _parse_email_date(headers: list[dict]) -> date:
    """Parses the email date from headers."""
    date_str = None
    for header in headers:
        if header.get("name", "").lower() == "date":
            date_str = header["value"]
            break

    if not date_str:
        return date.today()

    try:
        # Try parsing RFC 2822 format
        parsed = datetime.strptime(date_str[:31].strip(), "%a, %d %b %Y %H:%M:%S %z")
        return parsed.date()
    except (ValueError, IndexError):
        try:
            # Fallback without timezone
            parsed = datetime.strptime(date_str[:25].strip(), "%a, %d %b %Y %H:%M:%S")
            return parsed.date()
        except (ValueError, IndexError):
            pass
    return date.today()


def _parse_message(msg: dict) -> EmailMetadata | None:
    """Parses a single Gmail message dict into EmailMetadata."""
    try:
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])
        header_map = {h["name"].lower(): h["value"] for h in headers}

        from_raw = header_map.get("from", "")
        sender_email = _extract_sender_email(from_raw)
        subject = header_map.get("subject", "")
        body = _extract_body(payload)
        email_date = _parse_email_date(headers)

        return EmailMetadata(
            email_id=msg["id"],
            thread_id=msg.get("threadId", msg["id"]),
            subject=subject,
            sender=from_raw,
            sender_email=sender_email,
            date=email_date,
            body=body,
        )
    except Exception as error:
        logger.bind(email_id=msg.get("id", "unknown"), error=str(error)).error("Failed to parse message")
        return None


def _batch_callback(request_id: str, response: Any, error: Exception) -> None:
    """Callback for BatchHttpRequest responses."""
    # This callback is intentionally minimal — results are collected
    # via the shared _batch_results list in fetch_emails
    pass


def get_gmail_service():
    """Returns a Gmail API service instance."""
    try:
        creds = _authenticate()
        return build("gmail", "v1", credentials=creds)
    except Exception as e:
        logger.error(f"Failed to build Gmail service: {e}")
        return None


def fetch_emails(service: Any, since_date: date) -> list[EmailMetadata]:
    """
    Fetches emails from Gmail since a specific date.
    Returns a list of EmailMetadata with extracted data.

    v2.0: Uses BatchHttpRequest to fetch 50 messages per HTTP request
    instead of sequential calls.
    """
    query = _build_query(since_date)

    # Get list of message IDs (automatic pagination)
    all_message_ids: list[str] = []
    page_token = None

    while True:
        response = (
            service.users()
            .messages()
            .list(userId="me", q=query, pageToken=page_token, maxResults=500)
            .execute()
        )

        messages = response.get("messages", [])
        all_message_ids.extend(m["id"] for m in messages)

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    logger.info(f"Found {len(all_message_ids)} email IDs matching query")

    if not all_message_ids:
        return []

    # ── Batch fetch email details ──────────────────────────────
    # Instead of N sequential calls, we batch them into groups of 50.
    # Each batch is a single HTTP request with multiple sub-requests.
    emails: list[EmailMetadata] = []

    def _make_batch_callback(results_list: list, email_id: str) -> Callable:
        """Creates a closure to collect batch results."""
        def callback(_request_id: str, response: Any, error: Exception) -> None:
            if error:
                logger.bind(email_id=email_id, error=str(error)).error("Failed to fetch email in batch")
            elif response:
                email = _parse_message(response)
                if email:
                    results_list.append(email)
        return callback

    # Process in batches of GMAIL_BATCH_SIZE
    msg_iter = iter(all_message_ids)
    batch_num = 0

    while True:
        batch_ids = list(islice(msg_iter, GMAIL_BATCH_SIZE))
        if not batch_ids:
            break

        batch_num += 1
        batch_results: list[EmailMetadata] = []
        batch = service.new_batch_http_request()

        for msg_id in batch_ids:
            batch.add(
                service.users().messages().get(userId="me", id=msg_id, format="full"),
                callback=_make_batch_callback(batch_results, msg_id),
            )

        batch.execute()
        emails.extend(batch_results)
        logger.info(f"Batch {batch_num}: fetched {len(batch_results)}/{len(batch_ids)} emails")

    logger.info(
        f"Successfully extracted {len(emails)} emails with full metadata "
        f"({batch_num} batches)"
    )
    return emails
