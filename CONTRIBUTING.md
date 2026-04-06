# Contributing to BewerbLens

Thank you for your interest in contributing! This project is structured as a monorepo containing a Python AI ingestion pipeline (`apps/tracker`) and a Next.js dashboard (`apps/dashboard`).

## Getting Started

1. **Fork** the repository and clone it locally.
2. Initialize the environment:
   ```bash
   cp .env.example .env
   ```
3. Set up the local databases and run the schema migrations in `apps/tracker/schema.sql`.

## Development Guidelines

### Next.js Dashboard
- We strictly observe **Vanilla CSS Modules** (no Tailwind).
- Ensure all components are responsive and respect both **Light and Dark mode** toggles.
- Run `npm run lint` before committing anything.

### Python AI Engine
- We enforce strict typing using `Pydantic`.
- Ensure new LLM classification features gracefully fallback if Gemini's API throws a rate limit.
- Run `ruff check .` to auto-fix styling errors.

## Pull Requests

1. Always branch off `main`.
2. Name your branch semantically (e.g., `feat/add-new-chart`, `fix/resolve-infinite-loop`).
3. Fill out the PR template entirely. We will not review PRs without proper visual testing evidence.
