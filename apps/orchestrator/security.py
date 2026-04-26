from __future__ import annotations

import os
import secrets
import threading
from collections import defaultdict, deque
from time import monotonic

from fastapi import Header, HTTPException, Request, status
from pydantic import Field
from pydantic_settings import BaseSettings

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
ENV_FILE = os.path.join(ROOT_DIR, ".env")


class OrchestratorSecuritySettings(BaseSettings):
    dashboard_url: str = Field(default="http://localhost:3000")
    additional_cors_origins: str = Field(default="")
    orchestrator_api_key: str = Field(default="")
    api_rate_limit_requests: int = Field(default=20, ge=0)
    api_rate_limit_window_seconds: int = Field(default=60, ge=1)

    model_config = {
        "env_file": ENV_FILE,
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    @property
    def allowed_origins(self) -> list[str]:
        origins = ["http://localhost:3000", self.dashboard_url]
        if self.additional_cors_origins:
            origins.extend(
                origin.strip()
                for origin in self.additional_cors_origins.split(",")
                if origin.strip()
            )

        deduped: list[str] = []
        seen: set[str] = set()
        for origin in origins:
            if origin not in seen:
                deduped.append(origin)
                seen.add(origin)
        return deduped


security_settings = OrchestratorSecuritySettings()

_rate_limit_events: dict[str, deque[float]] = defaultdict(deque)
_rate_limit_lock = threading.Lock()


def ensure_orchestrator_security_settings() -> None:
    if not security_settings.orchestrator_api_key:
        raise RuntimeError(
            "Missing required environment variable: ORCHESTRATOR_API_KEY. "
            "Protected orchestrator routes will not start without it."
        )


async def verify_orchestrator_api_key(
    x_orchestrator_api_key: str | None = Header(default=None),
) -> None:
    expected_key = security_settings.orchestrator_api_key
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Orchestrator API key is not configured.",
        )

    if not x_orchestrator_api_key or not secrets.compare_digest(
        x_orchestrator_api_key,
        expected_key,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid orchestrator API key.",
        )


async def rate_limit_protected_route(request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return

    limit = security_settings.api_rate_limit_requests
    if limit <= 0:
        return

    window_seconds = security_settings.api_rate_limit_window_seconds
    identifier = (
        request.headers.get("x-bewerblens-user-id")
        or (request.client.host if request.client else None)
        or "unknown"
    )
    now = monotonic()
    earliest_allowed = now - window_seconds

    with _rate_limit_lock:
        events = _rate_limit_events[identifier]
        while events and events[0] < earliest_allowed:
            events.popleft()

        if len(events) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please wait before trying again.",
            )

        events.append(now)
