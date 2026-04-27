import json
import os

# Ensure correct path resolution
import sys

from google.oauth2.credentials import Credentials
from loguru import logger

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from supabase import create_client

from config import settings
from gmail_service import save_gmail_credentials_to_db


def migrate_token():
    user_email = settings.user_email
    token_json_str = settings.gmail_token_json

    if not token_json_str:
        logger.error("No GMAIL_TOKEN_JSON found in .env.")
        return

    # Try parsing token
    try:
        token_data = json.loads(token_json_str.strip("'\""))
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse GMAIL_TOKEN_JSON: {e}")
        return

    # Initialize Supabase client
    supabase = create_client(settings.supabase_url, settings.supabase_key)

    # Find the user by email
    res = supabase.table("user_profiles").select("id").eq("email", user_email).execute()
    if not res.data:
        logger.error(f"User with email {user_email} not found.")
        return

    user_id = res.data[0]["id"]

    logger.info(f"Migrating Gmail token for user: {user_email} (ID: {user_id})")

    # Construct the Credentials object
    creds = Credentials(
        token=token_data.get('token'),
        refresh_token=token_data.get('refresh_token'),
        token_uri=token_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
        client_id=token_data.get('client_id'),
        client_secret=token_data.get('client_secret'),
        scopes=token_data.get('scopes', ['https://www.googleapis.com/auth/gmail.readonly'])
    )

    # Save to db using the service method (which handles AES encryption and updates gmail_connected_via)
    try:
        save_gmail_credentials_to_db(supabase, user_id, creds)
        logger.success("Successfully migrated Gmail token to user_profiles table.")
    except Exception as e:
        logger.error(f"Failed to save credentials to db: {e}")

if __name__ == "__main__":
    migrate_token()
