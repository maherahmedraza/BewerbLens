# Environment Variables

## Dashboard public runtime

| Variable | Required | Purpose |
| --- | --- | --- |
| `NEXT_PUBLIC_SUPABASE_URL` | Yes | Supabase project URL used by browser and server clients |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Yes | Supabase anon key used for authenticated dashboard access |
| `NEXT_PUBLIC_ORCHESTRATOR_URL` | Yes | FastAPI orchestrator base URL |
| `ORCHESTRATOR_URL` | Recommended | Server-only override used by the dashboard proxy in Docker/dev networks |

## Dashboard server-only routes

| Variable | Required | Purpose |
| --- | --- | --- |
| `GOOGLE_CLIENT_ID` | Yes | Google OAuth client ID used for Gmail authorization |
| `GOOGLE_CLIENT_SECRET` | Yes | Google OAuth client secret used for token exchange |
| `GOOGLE_OAUTH_REDIRECT_URI` | Yes | Redirect URI for `/api/integrations/google/callback` |
| `SUPABASE_KEY` | Yes | Service-role key used only by server-side completion routes |
| `ORCHESTRATOR_API_KEY` | Yes | Shared secret injected into the dashboard's server-side orchestrator proxy |
| `ENCRYPTION_SECRET` | Recommended | Primary secret for AES-256-GCM credential encryption |
| `ENCRYPTION_KEY` | Optional | Legacy fallback for older encrypted payloads |
| `TELEGRAM_BOT_USERNAME` | Optional | Lets the dashboard deep-link users to the bot |
| `TELEGRAM_LINK_SECRET` | Recommended | Shared secret validated by the Telegram link completion route |

## Shared backend runtime

| Variable | Required | Purpose |
| --- | --- | --- |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_KEY` | Yes | Service-role key for tracker/orchestrator DB access |
| `GEMINI_API_KEY` | Yes | Gemini API key |
| `GEMINI_MODEL` | No | Gemini model name |
| `USER_EMAIL` | Optional | Excludes self-sent emails from ingestion |
| `GMAIL_DAILY_QUOTA_UNITS` | No | Quota baseline used for Gmail usage estimates |
| `GEMINI_INPUT_COST_PER_MILLION` | No | Estimated input token pricing |
| `GEMINI_OUTPUT_COST_PER_MILLION` | No | Estimated output token pricing |
| `BATCH_SIZE` | No | Classification batch size |
| `MIN_CONFIDENCE` | No | Minimum classifier confidence |
| `BACKFILL_START_DATE` | No | Legacy fallback for first-run ingestion date |
| `PROMPT_BODY_MAX_CHARS` | No | Max email body size sent into prompts |
| `CLASSIFIER_MAX_BATCH_TOKENS` | No | Token cap for batching |
| `FOLLOW_UP_REMINDER_DAYS` | No | Minimum age for `Applied` applications before Telegram reminder jobs include them |
| `FOLLOW_UP_REMINDER_REPEAT_DAYS` | No | Cooldown between repeated Telegram reminder nudges for the same application |

## Optional legacy Gmail bootstrap

| Variable | Required | Purpose |
| --- | --- | --- |
| `GMAIL_CREDENTIALS_JSON` | Optional | Single-user/local bootstrap credentials |
| `GMAIL_TOKEN_JSON` | Optional | Single-user/local bootstrap token |
| `GMAIL_OAUTH_REDIRECT_URI` | Optional | Legacy redirect URI used by tracker fallback flow |

## Optional Telegram delivery

| Variable | Required | Purpose |
| --- | --- | --- |
| `TELEGRAM_ENABLED` | Required for current tracker sender path | Global notification gate used by the tracker before sending run reports |
| `TELEGRAM_BOT_TOKEN` | Required for linked-user delivery | Bot token used by the tracker sender |
| `TELEGRAM_CHAT_ID` | Optional | Legacy/default chat target for single-user runs |

## Current deployment note

- Production and preview DigitalOcean specs now expect `ORCHESTRATOR_API_KEY`, `ENCRYPTION_SECRET` (preferred), and the follow-up reminder cadence variables alongside the existing backend secrets.
