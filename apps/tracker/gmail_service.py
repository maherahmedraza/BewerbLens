# ╔══════════════════════════════════════════════════════════════╗
# ║  Gmail Service - Multi-User Support                         ║
# ║                                                             ║
# ║  Fetches Gmail credentials from user_profiles table         ║
# ║  Falls back to .env for backward compatibility              ║
# ╚══════════════════════════════════════════════════════════════╝

import os
import json
import pickle
from typing import Optional, Dict
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from loguru import logger
from cryptography.fernet import Fernet

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def _get_cipher():
    """Get Fernet cipher using ENCRYPTION_KEY from environment."""
    key = os.getenv('ENCRYPTION_KEY')
    if not key:
        logger.warning("ENCRYPTION_KEY not found in environment. Credentials will be stored in PLAIN TEXT!")
        return None
    try:
        return Fernet(key.encode())
    except Exception as e:
        logger.error(f"Invalid ENCRYPTION_KEY: {e}")
        return None

def _encrypt_data(data: dict) -> str:
    """Encrypt dictionary to base64 string."""
    cipher = _get_cipher()
    if not cipher:
        return json.dumps(data)

    json_data = json.dumps(data).encode()
    encrypted = cipher.encrypt(json_data)
    return encrypted.decode()

def _decrypt_data(encrypted_str: str) -> dict:
    """Decrypt base64 string to dictionary."""
    if not encrypted_str:
        return {}

    # Check if it looks like JSON (not encrypted)
    if encrypted_str.strip().startswith('{'):
        try:
            return json.loads(encrypted_str)
        except:
            pass

    cipher = _get_cipher()
    if not cipher:
        # Fallback: maybe it's plain JSON
        try:
            return json.loads(encrypted_str)
        except:
            logger.error("Data seems encrypted but no cipher available.")
            return {}

    try:
        decrypted = cipher.decrypt(encrypted_str.encode())
        return json.loads(decrypted.decode())
    except Exception as e:
        logger.error(f"Decryption failed: {e}. Trying plain JSON fallback.")
        try:
            return json.loads(encrypted_str)
        except:
            return {}


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
            return build('gmail', 'v1', credentials=creds)
        except Exception as e:
            logger.error(f"Failed to load database credentials: {e}")
            # Fall through to fallback

    # ═══ Strategy 2: Environment Variable (Single-User Fallback) ═══
    if os.getenv('GMAIL_TOKEN'):
        logger.warning("Using .env GMAIL_TOKEN (single-user mode)")
        try:
            token_path = os.getenv('GMAIL_TOKEN', 'token.json')
            if os.path.exists(token_path):
                with open(token_path, 'r') as f:
                    token_data = json.load(f)
                creds = _load_credentials_from_json(token_data)
                return build('gmail', 'v1', credentials=creds)
        except Exception as e:
            logger.error(f"Failed to load .env credentials: {e}")
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

    Requires credentials.json in project root.
    """
    creds_file = 'credentials.json'
    if not os.path.exists(creds_file):
        logger.error(f"Missing {creds_file}. Download from Google Cloud Console.")
        return None

    try:
        flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
        creds = flow.run_local_server(port=0)

        # Save to token.json for reuse
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

        logger.success("OAuth flow complete. Token saved to token.json")
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
        "gmail_credentials": encrypted_creds
    }).eq("id", user_id).execute()

    logger.success(f"Saved Gmail credentials for user {user_id}")


# ══════════════════════════════════════════════════════════════
# Email Fetching (User-Scoped)
# ══════════════════════════════════════════════════════════════

def fetch_emails_for_user(service, user_id: str, since_date=None, existing_ids=None):
    """
    Fetch emails for specific user.

    Args:
        service: Gmail API service object
        user_id: User UUID (for logging/tracking)
        since_date: Fetch emails from this date onwards
        existing_ids: Set of email IDs already in database

    Returns:
        List of Email objects
    """
    from gmail_service import fetch_emails  # Import original function

    # Reuse existing fetch_emails logic
    # Just add user_id to logs for multi-tenant tracking
    logger.info(f"Fetching emails for user {user_id}")

    emails = fetch_emails(service, since_date, existing_ids)

    logger.info(f"Fetched {len(emails)} emails for user {user_id}")
    return emails


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
            'credentials.json',
            scopes=SCOPES,
            redirect_uri=os.getenv('GMAIL_OAUTH_REDIRECT_URI', 'http://localhost:3000/auth/gmail/callback')
        )

        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Save to database
        save_gmail_credentials_to_db(client, user_id, credentials)

        return True

    except Exception as e:
        logger.error(f"OAuth callback failed: {e}")
        return False
