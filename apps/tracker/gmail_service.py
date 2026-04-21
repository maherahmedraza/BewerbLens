# ╔══════════════════════════════════════════════════════════════╗
# ║  Gmail Service - Multi-User Support                         ║
# ║                                                             ║
# ║  Fetches Gmail credentials from user_profiles table         ║
# ║  Falls back to .env for backward compatibility              ║
# ║  v2.0: Uses BatchHttpRequest for 5x faster fetching.        ║
# ╚══════════════════════════════════════════════════════════════╝

import base64
import hashlib
import json
import os
import re
from collections.abc import Callable
from datetime import date, datetime, timezone
from itertools import islice
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from loguru import logger

from config import settings
from models import EmailMetadata

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

GMAIL_BATCH_SIZE = 10

QUERY_EXCLUDED_SENDERS = [
    "jobalerts-noreply@linkedin.com",
    "info@jobagent.stepstone.de",
    "jobalert@indeed.com",
    "alert@indeed.com",
    "noreply@indeed.com",
    "news@mail.xing.com",
]

JOB_KEYWORDS = [
    "bewerbung", "application", "absage", "rejection",
    "einladung", "interview", "eingangsbestätigung",
    "eingangsbestaetigung", "angebot", "offer",
    "karriere", "career", "recruitment", "hiring",
    "status", "update", "assessment", "talent",
    '"thank you for applying"', '"we received"',
    '"ihre bewerbung"', '"deine bewerbung"',
    '"next steps"', '"nächste schritte"',
]

def _get_cipher():
    """Get legacy Fernet cipher for backwards-compatible decryption."""
    key = settings.encryption_key
    if not key:
        return None
    try:
        return Fernet(key.encode())
    except Exception as e:
        logger.debug(f"Legacy Fernet key unavailable: {e}")
        return None


def _get_aes_key() -> bytes | None:
    secret = settings.encryption_secret or settings.encryption_key
    if not secret:
        logger.warning("No encryption secret configured. Credentials will be stored in plain JSON.")
        return None
    return hashlib.sha256(secret.encode()).digest()

def _encrypt_data(data: dict) -> str:
    """Encrypt dictionary using AES-256-GCM, with JSON fallback if no secret exists."""
    aes_key = _get_aes_key()
    if not aes_key:
        return json.dumps(data)

    json_data = json.dumps(data).encode()
    iv = os.urandom(12)
    encrypted = AESGCM(aes_key).encrypt(iv, json_data, None)
    return (
        "aes256gcm:"
        f"{base64.urlsafe_b64encode(iv).decode()}:"
        f"{base64.urlsafe_b64encode(encrypted).decode()}"
    )

def _decrypt_data(encrypted_str: str) -> dict:
    """Decrypt AES-256-GCM or legacy Fernet payloads into a dictionary."""
    if not encrypted_str:
        return {}

    # Check if it looks like JSON (not encrypted)
    if encrypted_str.strip().startswith('{'):
        try:
            return json.loads(encrypted_str)
        except Exception:
            pass

    if encrypted_str.startswith("aes256gcm:"):
        try:
            _prefix, iv_b64, payload_b64 = encrypted_str.split(":", 2)
            aes_key = _get_aes_key()
            if not aes_key:
                return {}
            iv = base64.urlsafe_b64decode(iv_b64.encode())
            payload = base64.urlsafe_b64decode(payload_b64.encode())
            decrypted = AESGCM(aes_key).decrypt(iv, payload, None)
            return json.loads(decrypted.decode())
        except Exception as e:
            logger.error(f"AES decryption failed: {e}")
            return {}

    cipher = _get_cipher()
    if not cipher:
        try:
            return json.loads(encrypted_str)
        except Exception:
            logger.error("Data seems encrypted but no compatible cipher is available.")
            return {}

    try:
        decrypted = cipher.decrypt(encrypted_str.encode())
        return json.loads(decrypted.decode())
    except Exception as e:
        logger.error(f"Decryption failed: {e}. Trying plain JSON fallback.")
        try:
            return json.loads(encrypted_str)
        except Exception:
            return {}


def _update_gmail_connection_state(
    client,
    user_id: str | None,
    connected_via: str,
    *,
    set_connected_at: bool = False,
) -> None:
    if not client or not user_id:
        return

    payload: dict[str, Any] = {
        "gmail_connected_via": connected_via,
    }
    if set_connected_at:
        payload["gmail_connected_at"] = datetime.now(timezone.utc).isoformat()

    try:
        client.table("user_profiles").update(payload).eq("id", user_id).execute()
    except Exception as error:
        logger.warning(f"Failed to persist Gmail connection state for user {user_id}: {error}")


def get_gmail_service_for_user(user_profile: Dict, db_client=None):
    """
    Get Gmail service for specific user.

    Args:
        user_profile: User profile dict from user_profiles table
        db_client: Optional Supabase client for persisting refreshed tokens

    Returns:
        Gmail service object or None

    Credential Priority:
    1. user_profile['gmail_credentials'] (database)
    2. .env GMAIL_TOKEN (fallback for single-user setups)
    3. Interactive OAuth flow (development only)
    """

    user_id = user_profile.get('id')

    # ═══ Strategy 1: Database Credentials (Multi-User) ═══
    if user_profile.get('gmail_credentials'):
        logger.info(f"Using database Gmail credentials for user {user_profile['email']}")
        try:
            # Handle both encrypted string and legacy dict
            creds_data = user_profile['gmail_credentials']
            if isinstance(creds_data, str):
                creds_data = _decrypt_data(creds_data)

            creds = _load_credentials_from_json(creds_data, client=db_client, user_id=user_id)
            _update_gmail_connection_state(db_client, user_id, "oauth")
            return build('gmail', 'v1', credentials=creds)
        except Exception as e:
            logger.error(f"Failed to load database credentials: {e}")
            # Fall through to fallback

    # ═══ Strategy 2: Environment Variable (Single-User Fallback) ═══
    gmail_token_env = settings.gmail_token_json
    if gmail_token_env:
        logger.warning("Using env Gmail token (single-user mode)")
        try:
            # Support inline JSON or file path
            token_value = gmail_token_env.strip().strip("'\"")
            if token_value.startswith('{'):
                token_data = json.loads(token_value)
            elif os.path.exists(token_value):
                with open(token_value, 'r') as f:
                    token_data = json.load(f)
            else:
                raise ValueError("GMAIL_TOKEN_JSON is neither JSON nor a valid file path")

            creds = _load_credentials_from_json(token_data, client=db_client, user_id=user_id)
            _update_gmail_connection_state(db_client, user_id, "env_fallback", set_connected_at=True)
            return build('gmail', 'v1', credentials=creds)
        except Exception as e:
            logger.error(f"Failed to load env credentials: {e}")
            # Fall through to OAuth flow

    # ═══ Strategy 3: Interactive OAuth (Development Only) ═══
    logger.warning("No credentials found. Starting OAuth flow (dev mode only)")
    creds = _run_oauth_flow()
    if creds:
        return build('gmail', 'v1', credentials=creds)

    return None


def _load_credentials_from_json(creds_json: Dict, client=None, user_id: str = None) -> Credentials:
    """
    Load Google credentials from JSON dict.

    Handles token refresh if expired.
    If client and user_id are provided, persists refreshed tokens to DB.
    """
    creds = Credentials(
        token=creds_json.get('token'),
        refresh_token=creds_json.get('refresh_token'),
        token_uri=creds_json.get('token_uri', 'https://oauth2.googleapis.com/token'),
        client_id=creds_json.get('client_id'),
        client_secret=creds_json.get('client_secret'),
        scopes=creds_json.get('scopes', SCOPES)
    )

    # Refresh if expired
    if not creds.valid and creds.expired and creds.refresh_token:
        logger.info("Refreshing expired Gmail token")
        creds.refresh(Request())

        # Persist refreshed token back to DB for this user
        if user_id and client:
            try:
                save_gmail_credentials_to_db(client, user_id, creds)
                logger.info(f"Persisted refreshed Gmail token for user {user_id}")
            except Exception as e:
                logger.warning(f"Failed to persist refreshed token: {e}")

    return creds


def _run_oauth_flow() -> Optional[Credentials]:
    """
    Run interactive OAuth flow (development only).

    Supports GMAIL_CREDENTIALS_JSON env var (inline JSON) or credentials.json file.
    """
    creds_env = (settings.gmail_credentials_json or "").strip().strip("'\"")
    creds_file = settings.gmail_credentials_path

    try:
        if creds_env and creds_env.startswith('{'):
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
                f.write(creds_env)
                creds_file = f.name
        elif not os.path.exists(creds_file):
            logger.error("Missing credentials file and GMAIL_CREDENTIALS_JSON env var.")
            return None

        flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
        creds = flow.run_local_server(port=0)

        with open(settings.gmail_token_path, 'w') as token:
            token.write(creds.to_json())

        logger.success(f"OAuth flow complete. Token saved to {settings.gmail_token_path}")
        return creds

    except Exception as e:
        logger.error(f"OAuth flow failed: {e}")
        return None


def save_gmail_credentials_to_db(client, user_id: str, credentials: Credentials):
    """
    Save Gmail credentials to user_profiles table.

    Encrypts sensitive fields before storage.
    """
    creds_dict = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

    # Encrypt before storing
    encrypted_creds = _encrypt_data(creds_dict)

    client.table("user_profiles").update({
        "gmail_credentials": encrypted_creds,
        "gmail_connected_via": "oauth",
        "gmail_connected_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", user_id).execute()

    logger.success(f"Saved Gmail credentials for user {user_id}")


# ══════════════════════════════════════════════════════════════
# Email Fetching (User-Scoped)
# ══════════════════════════════════════════════════════════════

def _build_query(after_date: date, only_unread: bool = False) -> str:
    keywords_clause = " OR ".join(JOB_KEYWORDS)
    exclusions = " ".join(f"-from:{s}" for s in QUERY_EXCLUDED_SENDERS)
    after_str = after_date.strftime("%Y/%m/%d")
    unread_clause = " is:unread" if only_unread else ""
    query = f"({keywords_clause}) {exclusions} after:{after_str}{unread_clause}"
    logger.info(f"Gmail query built with after:{after_str}")
    return query


def _extract_body(payload: dict) -> str:
    max_length = 800
    if payload.get("body", {}).get("data"):
        try:
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")[:max_length]
        except Exception:
            pass
    for part in payload.get("parts", []):
        mime_type = part.get("mimeType", "")
        if mime_type == "text/plain" and part.get("body", {}).get("data"):
            try:
                return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")[:max_length]
            except Exception:
                continue
        if part.get("parts"):
            nested_body = _extract_body(part)
            if nested_body:
                return nested_body
    return ""


def _extract_sender_email(from_header: str) -> str:
    match = re.search(r"<([^>]+)>", from_header)
    return (match.group(1) if match else from_header).lower().strip()


def _parse_email_date(headers: list[dict]) -> date:
    date_str = None
    for header in headers:
        if header.get("name", "").lower() == "date":
            date_str = header["value"]
            break
    if not date_str:
        return date.today()
    try:
        parsed = datetime.strptime(date_str[:31].strip(), "%a, %d %b %Y %H:%M:%S %z")
        return parsed.date()
    except (ValueError, IndexError):
        try:
            parsed = datetime.strptime(date_str[:25].strip(), "%a, %d %b %Y %H:%M:%S")
            return parsed.date()
        except (ValueError, IndexError):
            pass
    return date.today()


def _parse_message(msg: dict) -> EmailMetadata | None:
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
        logger.bind(email_id=msg.get("id", "unknown")).error(f"Failed to parse message: {error}")
        return None


def fetch_emails_for_user(service, user_id: str, since_date=None, existing_ids=None, only_unread: bool = False):
    """
    Fetch emails for a specific user via Gmail API.

    Uses batch requests for efficiency (groups of GMAIL_BATCH_SIZE).
    Filters out already-known email IDs if existing_ids is provided.
    """
    if since_date is None:
        since_date = date.today()

    logger.info(f"Fetching emails for user {user_id} since {since_date}")
    query = _build_query(since_date, only_unread=only_unread)

    all_message_ids: list[str] = []
    page_token = None
    list_calls = 0

    while True:
        list_calls += 1
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

    # Filter out already-known emails
    if existing_ids:
        all_message_ids = [mid for mid in all_message_ids if mid not in existing_ids]
        logger.info(f"{len(all_message_ids)} new emails after filtering existing")

    gmail_api_calls = list_calls + len(all_message_ids)
    usage = {
        "gmail_api_calls": gmail_api_calls,
        "gmail_remaining_quota_estimate": max(settings.gmail_daily_quota_units - gmail_api_calls, 0),
    }

    if not all_message_ids:
        return [], usage

    # Batch fetch email details
    emails: list[EmailMetadata] = []

    def _make_batch_callback(results_list: list, email_id: str) -> Callable:
        def callback(_request_id: str, response: Any, error: Exception) -> None:
            if error:
                logger.bind(email_id=email_id).error(f"Failed to fetch email in batch: {error}")
            elif response:
                email = _parse_message(response)
                if email:
                    results_list.append(email)
        return callback

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

    logger.info(f"Fetched {len(emails)} emails for user {user_id} ({batch_num} batches)")
    return emails, usage


# ══════════════════════════════════════════════════════════════
# OAuth Callback Handler (for web-based OAuth)
# ══════════════════════════════════════════════════════════════

def handle_gmail_oauth_callback(code: str, user_id: str, client):
    """
    Handle OAuth callback from Gmail authorization.

    Args:
        code: Authorization code from Google
        user_id: User UUID
        client: Supabase client

    Returns:
        True if successful, False otherwise

    Usage:
        # In your FastAPI/Next.js callback route:
        handle_gmail_oauth_callback(request.query.code, user.id, supabase)
    """
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            settings.gmail_credentials_path,
            scopes=SCOPES,
            redirect_uri=settings.gmail_oauth_redirect_uri,
        )

        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Save to database
        save_gmail_credentials_to_db(client, user_id, credentials)

        return True

    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        return False
