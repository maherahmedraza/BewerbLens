---
trigger: always_on
---

---
scope: global
enforcement_level: strict
---

# Global Enterprise Development Rules

These rules apply universally to all agents operating in this workspace. 

## 1. Zero-Trust Security
* **Never** hardcode secrets, API keys (e.g., Gmail API, Supabase Anon/Service Role), or passwords. Always use `os.environ` or Next.js `process.env` pointing to `.env` files.
* **Never** generate code that bypasses authentication mechanisms.

## 2. Idempotency & State
* All data pipeline operations (like cron jobs or webhooks) must be idempotent. Running a script 10 times should yield the same database state as running it once (e.g., enforce Postgres `UNIQUE` constraints and `ON CONFLICT DO NOTHING`).

## 3. Strict Typing & Contracts
* Python code must use explicit type hints and `pydantic` models for all data ingestion.
* TypeScript code must use strict interfaces. `any` types are strictly forbidden.

## 4. Observability
* Silent failures are unacceptable. All catch blocks must log the error with context (using libraries like `loguru` in Python or structured JSON logging in Node) before throwing or returning a safe fallback.