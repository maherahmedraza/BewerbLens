import os
import json
import subprocess
import sys

# Define the secrets we want to sync
# (Must match the env variables passed from GitHub Actions)
SECRETS_TO_SYNC = [
    "GEMINI_API_KEY",
    "GEMINI_MODEL",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "TELEGRAM_ENABLED",
    "TELEGRAM_BOT_TOKEN",
    "BATCH_SIZE",
    "MIN_CONFIDENCE",
    "ORCHESTRATOR_API_KEY",
    "ENCRYPTION_SECRET",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_OAUTH_REDIRECT_URI",
    "NEXT_PUBLIC_SUPABASE_URL",
    "NEXT_PUBLIC_SUPABASE_ANON_KEY",
    "NEXT_PUBLIC_ORCHESTRATOR_URL",
]

# Only backend needs some secrets, while Vercel needs frontend/both
DO_ONLY_SECRETS = {
    "GEMINI_API_KEY", "GEMINI_MODEL", "TELEGRAM_ENABLED", 
    "TELEGRAM_BOT_TOKEN", "BATCH_SIZE", "MIN_CONFIDENCE", "ENCRYPTION_SECRET"
}

VERCEL_ONLY_SECRETS = {
    "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_OAUTH_REDIRECT_URI",
    "NEXT_PUBLIC_SUPABASE_URL", "NEXT_PUBLIC_SUPABASE_ANON_KEY", "NEXT_PUBLIC_ORCHESTRATOR_URL"
}

def run_command(cmd, input_data=None):
    process = subprocess.Popen(
        cmd, shell=True, text=True,
        stdin=subprocess.PIPE if input_data else None,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    stdout, stderr = process.communicate(input=input_data)
    if process.returncode != 0:
        print(f"Command failed: {cmd}\nError: {stderr}")
        return False, stdout, stderr
    return True, stdout, stderr

def sync_to_vercel(key, value):
    if key in DO_ONLY_SECRETS:
        return
    print(f"Syncing {key} to Vercel...")
    # First try to remove it if it exists (ignore errors if it doesn't)
    run_command(f"npx vercel env rm {key} production,preview,development -y --token $VERCEL_TOKEN")
    
    # Add the new secret
    cmd = f"npx vercel env add {key} production,preview,development --token $VERCEL_TOKEN"
    success, _, _ = run_command(cmd, input_data=value)
    if success:
        print(f"✅ Successfully synced {key} to Vercel")
    else:
        print(f"❌ Failed to sync {key} to Vercel")

def sync_to_digitalocean(secrets_dict):
    print("\nSyncing secrets to DigitalOcean App Platform...")
    app_id = os.environ.get("DIGITALOCEAN_APP_ID")
    if not app_id:
        print("❌ DIGITALOCEAN_APP_ID not found in environment")
        return

    # Get current app spec
    print("Fetching current DigitalOcean app spec...")
    success, stdout, stderr = run_command(f"doctl app get {app_id} -o json")
    if not success:
        return

    try:
        app_data = json.loads(stdout)
        spec = app_data[0].get("spec", {})
    except Exception as e:
        print(f"❌ Failed to parse DigitalOcean app spec: {e}")
        return

    # Update global envs
    if "envs" not in spec:
        spec["envs"] = []

    # Map existing envs by key
    existing_envs = {env["key"]: env for env in spec["envs"]}

    updated = False
    for key, value in secrets_dict.items():
        if key in VERCEL_ONLY_SECRETS:
            continue
            
        is_secret = key not in ["GEMINI_MODEL", "TELEGRAM_ENABLED", "BATCH_SIZE", "MIN_CONFIDENCE"]
        
        env_obj = {
            "key": key,
            "value": value,
            "scope": "RUN_AND_BUILD_TIME"
        }
        if is_secret:
            env_obj["type"] = "SECRET"

        if key in existing_envs:
            existing_envs[key].update(env_obj)
        else:
            spec["envs"].append(env_obj)
        updated = True

    if not updated:
        print("No updates required for DigitalOcean.")
        return

    # Save the updated spec to a temporary file
    temp_spec_path = "temp_do_spec.json"
    with open(temp_spec_path, "w") as f:
        json.dump(spec, f)

    # Apply the update
    print("Applying updated spec to DigitalOcean (this will trigger a new deployment)...")
    success, _, _ = run_command(f"doctl app update {app_id} --spec {temp_spec_path}")
    
    if os.path.exists(temp_spec_path):
        os.remove(temp_spec_path)

    if success:
        print("✅ Successfully updated DigitalOcean app spec")
    else:
        print("❌ Failed to update DigitalOcean app spec")


def main():
    print("Starting Secrets Sync...")
    
    secrets_dict = {}
    for key in SECRETS_TO_SYNC:
        val = os.environ.get(key)
        if val:
            secrets_dict[key] = val
        else:
            print(f"⚠️ Warning: {key} is missing from environment variables")

    # Sync to Vercel
    for key, value in secrets_dict.items():
        sync_to_vercel(key, value)

    # Sync to DO
    sync_to_digitalocean(secrets_dict)
    
    print("\n🎉 Secret sync complete!")

if __name__ == "__main__":
    main()
