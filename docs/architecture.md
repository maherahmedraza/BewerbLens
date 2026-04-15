# System Architecture

BewerbLens is built as a modular system consisting of three main applications working together with Supabase as the central data and coordination hub.

## High-Level Components

### 1. Orchestrator Service (`apps/orchestrator`)
A FastAPI-based service that acts as the Brain of the system.
- **Scheduler**: Uses `APScheduler` to trigger periodic synchronization tasks.
- **REST API**: Provides endpoints for the dashboard to trigger manual runs, fetch history, and update configuration.
- **Worker Management**: Spawns a background thread that listens for tasks in the `pipeline_tasks` queue and executes them.

### 2. AI Tracker Pipeline (`apps/tracker`)
The core processing engine written in Python.
- **Ingestion**: Connects to the Gmail API using incremental checkpointing (only fetching emails since the last run).
- **Classification**: Uses Google Gemini 1.5 Flash to analyze email content and classify it (Application, Rejection, Interview, etc.).
- **Fuzzy Matching**: A dedicated service that resolves naming inconsistencies between job portals and email senders.
- **Notifications**: Sends real-time alerts via Telegram.

### 3. Dashboard Frontend (`apps/dashboard`)
A modern Next.js 16 application.
- **Real-time Monitoring**: Connects to Orchestrator logs to show live execution progress.
- **Analytics**: Visualizes job search trends, platform success rates, and response times.
- **Management**: Allows users to manage their profile, credentials, and pipeline settings.

## Data Flow (The "Medallion" Pipeline)

BewerbLens follows a simplified "Medallion" data architecture:

1. **Bronze (Raw Emails)**: 
   - Raw email metadata and previews are stored in the `raw_emails` table.
   - This serves as an audit trail and allows for re-processing if AI logic improves.

2. **Silver (Classified Applications)**:
   - The AI processes the Bronze data.
   - Structured records are created in the `applications` table.
   - Updates are handled via **Status Priority Logic** (e.g., an "Interview" status cannot be overwritten by a late "Application Confirmation").

3. **Gold (Analytics & UI)**:
   - Data is aggregated and served via Supabase views and the Dashboard.
   - User-specific views ensure data isolation in multi-user environments.

## Task Queue Workflow

The system uses a database-driven task queue for coordination:

1. **Trigger**: An event (scheduler or manual) inserts a record into `pipeline_tasks`.
2. **Claim**: The background worker calls a Supabase RPC `claim_next_task` to atomically lock and claim the task.
3. **Execute**: The worker runs the Tracker Pipeline logic.
4. **Heartbeat**: While running, the worker updates a `heartbeat_at` timestamp in `pipeline_runs` to prevent zombie processes.
5. **Log Sink**: Logs generated during execution are sent in real-time to the `pipeline_run_logs` table for dashboard viewing.
