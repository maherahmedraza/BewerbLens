from __future__ import annotations

import json
import os
import subprocess
import tempfile
from dataclasses import dataclass


VERCEL_ENVIRONMENTS = ("production", "preview", "development")
VERCEL_RUNTIME_KEYS = {
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_OAUTH_REDIRECT_URI",
    "NEXT_PUBLIC_SUPABASE_URL",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    "NEXT_PUBLIC_ORCHESTRATOR_URL",
    "ORCHESTRATOR_URL",
    "SUPABASE_KEY",
    "ORCHESTRATOR_API_KEY",
    "ENCRYPTION_SECRET",
    "ENCRYPTION_KEY",
    "TELEGRAM_BOT_USERNAME",
    "TELEGRAM_LINK_SECRET",
}
DIGITALOCEAN_RUNTIME_KEYS = {
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "TELEGRAM_ENABLED",
    "TELEGRAM_BOT_TOKEN",
    "BATCH_SIZE",
    "MIN_CONFIDENCE",
    "ORCHESTRATOR_API_KEY",
    "ENCRYPTION_SECRET",
    "ENCRYPTION_KEY",
    "FOLLOW_UP_REMINDER_DAYS",
    "FOLLOW_UP_REMINDER_REPEAT_DAYS",
}
NON_SECRET_KEYS = {
    "GEMINI_MODEL",
    "TELEGRAM_ENABLED",
    "BATCH_SIZE",
    "MIN_CONFIDENCE",
    "FOLLOW_UP_REMINDER_DAYS",
    "FOLLOW_UP_REMINDER_REPEAT_DAYS",
    "NEXT_PUBLIC_SUPABASE_URL",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    "NEXT_PUBLIC_ORCHESTRATOR_URL",
    "ORCHESTRATOR_URL",
    "TELEGRAM_BOT_USERNAME",
}


@dataclass(frozen=True)
class AppTarget:
    env_var: str
    label: str


APP_TARGETS = (
    AppTarget("DIGITALOCEAN_APP_ID", "production"),
    AppTarget("DIGITALOCEAN_DEV_APP_ID", "preview"),
)


def run_command(args: list[str], input_data: str | None = None, allow_failure: bool = False):
    process = subprocess.run(
        args,
        input=input_data,
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0 and not allow_failure:
        raise RuntimeError(
            f"Command failed: {' '.join(args)}\nSTDOUT: {process.stdout}\nSTDERR: {process.stderr}"
        )
    return process


def load_sync_values() -> dict[str, str]:
    keys = sorted(VERCEL_RUNTIME_KEYS | DIGITALOCEAN_RUNTIME_KEYS)
    values: dict[str, str] = {}
    for key in keys:
        value = os.environ.get(key)
        if value:
            values[key] = value
        else:
            print(f"⚠️  {key} is not set in GitHub secrets; skipping.")
    return values


def sync_to_vercel(values: dict[str, str]) -> None:
    if not values:
        return

    print("\nSyncing environment variables to Vercel...")
    for key in sorted(VERCEL_RUNTIME_KEYS):
        value = values.get(key)
        if value is None:
            continue

        for environment in VERCEL_ENVIRONMENTS:
            print(f"  • {key} → Vercel ({environment})")
            run_command(
                ["vercel", "env", "rm", key, environment, "-y", "--token", os.environ["VERCEL_TOKEN"]],
                allow_failure=True,
            )
            run_command(
                ["vercel", "env", "add", key, environment, "--token", os.environ["VERCEL_TOKEN"]],
                input_data=value,
            )


def _merge_envs(existing_envs: list[dict], values: dict[str, str]) -> list[dict]:
    merged: dict[str, dict] = {env["key"]: dict(env) for env in existing_envs}
    for key in sorted(DIGITALOCEAN_RUNTIME_KEYS):
        value = values.get(key)
        if value is None:
            continue

        env_obj = {
            "key": key,
            "value": value,
            "scope": "RUN_AND_BUILD_TIME",
        }
        if key not in NON_SECRET_KEYS:
            env_obj["type"] = "SECRET"

        merged[key] = {**merged.get(key, {}), **env_obj}

    return list(merged.values())


def sync_to_digitalocean(values: dict[str, str], target: AppTarget) -> None:
    app_id = os.environ.get(target.env_var)
    if not app_id:
        print(f"\nSkipping DigitalOcean {target.label} sync: {target.env_var} is not configured.")
        return

    print(f"\nSyncing environment variables to DigitalOcean ({target.label})...")
    result = run_command(["doctl", "apps", "get", app_id, "-o", "json"])
    app_data = json.loads(result.stdout)
    spec = app_data[0]["spec"]
    spec["envs"] = _merge_envs(spec.get("envs", []), values)

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as handle:
        json.dump(spec, handle)
        temp_path = handle.name

    try:
        run_command(["doctl", "apps", "update", app_id, "--spec", temp_path])
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def main() -> int:
    values = load_sync_values()
    sync_to_vercel(values)
    for target in APP_TARGETS:
        sync_to_digitalocean(values, target)
    print("\n✅ Secret sync complete. Redeploy Vercel/DO apps if you need existing deployments to pick up new values.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
