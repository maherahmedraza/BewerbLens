from __future__ import annotations

import os
from pydantic import Field
from pydantic_settings import BaseSettings

# Absolute path to the .env file in project root
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENV_FILE = os.path.join(ROOT_DIR, ".env")


class Settings(BaseSettings):
    """
    Application-wide configuration.
    Reads values from .env or system environment variables.
    """

    # ── Gmail ──────────────────────────────────────────────
    gmail_credentials_path: str = Field(default="credentials.json")
    gmail_token_path: str = Field(default="token.json")
    # JSON strings para autenticación sin archivos locales
    gmail_credentials_json: str | None = Field(default=None)
    gmail_token_json: str | None = Field(default=None)
    user_email: str = Field(default="")
    gmail_oauth_redirect_uri: str = Field(default="http://localhost:3000/auth/gmail/callback")
    encryption_key: str = Field(default="")
    encryption_secret: str = Field(default="")
    gmail_daily_quota_units: int = Field(default=1_000_000_000, ge=1)

    # ── Gemini AI ──────────────────────────────────────────
    gemini_api_key: str = Field(default="")
    gemini_model: str = Field(default="gemini-3.1-flash-lite-preview")
    gemini_input_cost_per_million: float = Field(default=0.075, ge=0.0)
    gemini_output_cost_per_million: float = Field(default=0.30, ge=0.0)

    # ── Supabase ───────────────────────────────────────────
    supabase_url: str = Field(default="")
    supabase_key: str = Field(default="")

    # ── Telegram ───────────────────────────────────────────
    telegram_enabled: bool = Field(default=False)
    telegram_bot_token: str = Field(default="")
    telegram_chat_id: str = Field(default="")

    # ── Pipeline ───────────────────────────────────────────
    batch_size: int = Field(default=50, ge=1, le=100)
    min_confidence: float = Field(default=0.55, ge=0.0, le=1.0)
    backfill_start_date: str = Field(default="2025-10-01")
    prompt_body_max_chars: int = Field(default=400, ge=100)
    classifier_max_batch_tokens: int = Field(default=3000, ge=500)

    # ── Classifier ────────────────────────────────────────
    classifier_provider: str = Field(default="gemini") # "gemini" | "openai"

    model_config = {
        "env_file": ENV_FILE,
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


# Global instance — imported as `from config import settings`
settings = Settings()
