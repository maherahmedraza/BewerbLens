# ╔══════════════════════════════════════════════════════════════╗
# ║  Gmail Service — Connection and email extraction            ║
# ║  Replaces the "Build Gmail Queries" and                     ║
# ║  "Fetch Emails (Per Month)" nodes from the n8n workflow.    ║
# ║                                                             ║
# ║  v3.0: Uses two-pass fetching (metadata first, then full)   ║
# ║  and optimized batch sizes (50) to minimize API usage.      ║
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
from loguru import logger

from config import settings
from models import EmailMetadata

# Required scopes — read-only Gmail access
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Batch size for Gmail API (50 is optimal for speed vs rate limits)
GMAIL_BATCH_SIZE = 50

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
    "einladung", "interview", "eingangsbestatigung",
    "angebot", "offer",
    '"thank you for applying"', '"we received"',
    '"ihre bewerbung"', '"deine bewerbung"',
]

def _authenticate() -> Credentials:
    """Autenticación OAuth2 priorizando variables de entorno."""
    creds = None
    if settings.gmail_token_json:
        try:
            token_info = json.loads(settings.gmail_token_json)
            creds = Credentials.from_authorized_user_info(token_info, SCOPES)
        except Exception as e:
            logger.error(f"Failed to load GMAIL_TOKEN_JSON: {e}")

    if not creds:
        token_path = Path(settings.gmail_token_path)
        if token_path.exists():
            creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            client_config = None
            if settings.gmail_credentials_json:
                try:
                    client_config = json.loads(settings.gmail_credentials_json)
                except Exception: pass
            
            if not client_config:
                creds_path = Path(settings.gmail_credentials_path)
                with open(creds_path) as f:
                    client_config = json.load(f)

            flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
            creds = flow.run_local_server(port=8080, open_browser=False)

        if settings.gmail_token_json:
            logger.warning("Gmail token was refreshed/generated. Please update your GMAIL_TOKEN_JSON environment variable with the new credentials.")
            # Do NOT log the actual token to avoid secret leaks
        else:
            token_path = Path(settings.gmail_token_path)
            token_path.write_text(new_token_json)

    return creds


def _build_query(after_date: date) -> str:
    """Construye la query de búsqueda de Gmail."""
    keywords_clause = " OR ".join(JOB_KEYWORDS)
    exclusions = " ".join(f"-from:{s}" for s in QUERY_EXCLUDED_SENDERS)
    after_str = after_date.strftime("%Y/%m/%d")
    return f"({keywords_clause}) {exclusions} after:{after_str}"


def _extract_body(payload: dict) -> str:
    """Extrae el cuerpo del email (truncado para eficiencia)."""
    max_length = settings.prompt_body_max_chars
    
    if payload.get("body", {}).get("data"):
        try:
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")[:max_length]
        except Exception: pass

    parts = payload.get("parts", [])
    for part in parts:
        mime_type = part.get("mimeType", "")
        if mime_type == "text/plain" and part.get("body", {}).get("data"):
            try:
                return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")[:max_length]
            except Exception: continue
        if part.get("parts"):
            nested = _extract_body(part)
            if nested: return nested
    return ""


def _parse_message(msg: dict) -> EmailMetadata | None:
    """Parsea el mensaje de Gmail a EmailMetadata."""
    try:
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])
        header_map = {h["name"].lower(): h["value"] for h in headers}

        from_raw = header_map.get("from", "")
        match = re.search(r"<([^>]+)>", from_raw)
        sender_email = (match.group(1) if match else from_raw).lower().strip()
        
        # Parseo simple de fecha
        date_str = header_map.get("date", "")
        try:
            email_date = datetime.strptime(date_str[:31].strip(), "%a, %d %b %Y %H:%M:%S %z").date()
        except Exception:
            email_date = date.today()

        return EmailMetadata(
            email_id=msg["id"],
            thread_id=msg.get("threadId", msg["id"]),
            subject=header_map.get("subject", ""),
            sender=from_raw,
            sender_email=sender_email,
            date=email_date,
            body=_extract_body(payload),
        )
    except Exception as e:
        logger.error(f"Fallo al parsear mensaje {msg.get('id')}: {e}")
        return None


def get_gmail_service():
    """Retorna instancia del servicio Gmail API."""
    try:
        creds = _authenticate()
        return build("gmail", "v1", credentials=creds)
    except Exception as e:
        logger.error(f"Fallo al construir servicio Gmail: {e}")
        return None


def fetch_emails(service: Any, since_date: date, existing_ids: set[str] = None) -> list[EmailMetadata]:
    """
    Obtiene emails desde Gmail de forma optimizada.
    Filtra por existing_ids ANTES de descargar el contenido completo.
    """
    query = _build_query(since_date)
    all_message_ids: list[str] = []
    page_token = None

    # 1. Listar IDs (pestaña mínima)
    while True:
        response = service.users().messages().list(userId="me", q=query, pageToken=page_token, maxResults=500).execute()
        messages = response.get("messages", [])
        all_message_ids.extend(m["id"] for m in messages)
        page_token = response.get("nextPageToken")
        if not page_token: break

    logger.info(f"Gmail query found {len(all_message_ids)} total candidates")

    # 2. Filtrar IDs que ya conocemos para no descargar sus cuerpos
    target_ids = [mid for mid in all_message_ids if mid not in (existing_ids or set())]
    
    if not target_ids:
        logger.info("No new emails found after ID filtering")
        return []

    logger.info(f"Fetching full metadata for {len(target_ids)} new emails using batches of {GMAIL_BATCH_SIZE}")

    # 3. Descarga masiva (Batch) de los cuerpos completos solo para los nuevos
    emails: list[EmailMetadata] = []
    
    def _make_callback(results_list: list):
        def callback(rid, response, error):
            if not error and response:
                email = _parse_message(response)
                if email: results_list.append(email)
        return callback

    msg_iter = iter(target_ids)
    while True:
        batch_ids = list(islice(msg_iter, GMAIL_BATCH_SIZE))
        if not batch_ids: break

        batch_results = []
        batch = service.new_batch_http_request()
        for mid in batch_ids:
            batch.add(service.users().messages().get(userId="me", id=mid, format="full"), callback=_make_callback(batch_results))
        
        batch.execute()
        emails.extend(batch_results)

    logger.info(f"Successfully extracted {len(emails)} new emails")
    return emails
