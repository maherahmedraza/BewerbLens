# BewerbLens Tracker

A code-first, production-ready **BewerbLens Tracker** that replaces the 30-node n8n workflow with a clean Python pipeline.

## Architecture

```
Gmail API --> Pre-Filter --> Gemini AI --> Supabase (Postgres) --> Telegram
   |              |              |                |                    |
  Fetch       Rule-based     Classify         Deduplicate          Notify
  emails      filtering      emails           & store
```

### Why Python over n8n?

| Problem in n8n | Solution in Python |
|---|---|
| 4 monthly Gmail API calls every run | Single incremental `after:` query |
| In-memory cache lost on restart | Supabase `UNIQUE` constraint on `thread_id` |
| ~255 Gemini batches on first run | Same batching, but with `tenacity` retries |
| Fragile JSON parsing in Code nodes | Pydantic enforced schemas |
| Visual debugging nightmare | Structured logging with `loguru` |
| No persistent state | Postgres checkpoint (last processed date) |

## Project Structure

```
apps/tracker/
├── tracker.py            # Main pipeline orchestrator
├── config.py             # Pydantic Settings (env vars)
├── models.py             # Data models & enums
├── gmail_service.py      # Gmail API connection
├── pre_filter.py         # Rule-based email filtering
├── gemini_classifier.py  # Gemini AI classification
├── supabase_service.py   # Database operations & dedup
├── telegram_notifier.py  # Notification service
├── schema.sql            # Supabase database schema
├── pyproject.toml        # Dependencies
├── .env.example          # Env var template
└── .github/workflows/
    └── tracker.yml       # GitHub Actions cron job
```

## Setup

### 1. Create Supabase Database

1. Go to [supabase.com](https://supabase.com) and create a new project
2. Open the **SQL Editor** and paste the contents of `schema.sql`
3. Click **Run** to create the tables
4. Go to **Settings -> API** and copy your `Project URL` and `service_role` key

### 2. Configure Gmail API

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project -> Enable Gmail API
3. Create OAuth 2.0 credentials -> Download as `credentials.json`
4. Place `credentials.json` in the project root

### 3. Get Gemini API Key

1. Go to [Google AI Studio](https://aistudio.google.com/apikey)
2. Create an API key
3. Add it to your `.env` file

### 4. Install & Run Locally

```bash
cd apps/tracker
cp .env.example .env
# Edit .env with your actual credentials

python -m venv .venv
source .venv/bin/activate
pip install -e .

# First run will open browser for Gmail OAuth
python tracker.py
```

### 5. Deploy to GitHub Actions (Free)

1. Push to a **private** GitHub repository
2. Go to **Settings -> Secrets and variables -> Actions**
3. Add these secrets:

| Secret | Value |
|--------|-------|
| `GMAIL_CREDENTIALS_JSON` | `base64 -w 0 credentials.json` |
| `GMAIL_TOKEN_JSON` | `base64 -w 0 token.json` |
| `GEMINI_API_KEY` | Your Gemini API key |
| `SUPABASE_URL` | Your Supabase project URL |
| `SUPABASE_KEY` | Your Supabase service_role key |
| `TELEGRAM_BOT_TOKEN` | _(optional)_ |
| `TELEGRAM_CHAT_ID` | _(optional)_ |

The workflow runs every 4 hours automatically. You can also click **"Run workflow"** manually.

## How It Works

1. **Checkpoint**: Reads last processed date from Supabase (not volatile memory)
2. **Fetch**: Single Gmail API query for emails since checkpoint
3. **Pre-filter**: Rule-based filtering (blocked senders, subjects, patterns)
4. **Classify**: Gemini AI classifies emails as application/rejection/interview/etc.
5. **Deduplicate**: Postgres `UNIQUE` constraint prevents duplicates natively
6. **Store**: Upsert to Supabase with status priority logic
7. **Notify**: Telegram alerts for new applications and status changes

## License

MIT
