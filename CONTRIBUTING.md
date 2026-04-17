# Contributing to BewerbLens

Thank you for your interest in contributing! This project is structured as a monorepo containing a Python AI ingestion pipeline (`apps/tracker`), a FastAPI orchestrator (`apps/orchestrator`), and a Next.js dashboard (`apps/dashboard`).

## Getting Started

1. **Fork** the repository and clone it locally.
2. Initialize the environment:
   ```bash
   cp .env.example .env
   ```
3. Apply the database migrations in order:
   ```bash
   psql "$DATABASE_URL" -f db/migrations/001_multiuser_foundation.sql
   # ... run all numbered migrations in sequence
   ```
4. Install dependencies:
   ```bash
   cd apps/dashboard && npm install
   cd ../tracker && pip install -e ".[dev]"
   ```

## Branch Naming

Always branch off `main`. Use the following naming convention:

```
<type>/<short-description>
```

| Type | When to use | Example |
|------|-------------|---------|
| `fix/` | Bug fixes | `fix/application-thread-grouping` |
| `feat/` or `feature/` | New features | `feature/user-profile-page` |
| `docs/` | Documentation only | `docs/update-documentation` |
| `refactor/` | Code restructuring | `refactor/pipeline-resilience` |
| `chore/` | Tooling, deps, CI | `chore/upgrade-dependencies` |

## Commit Messages

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

```
<type>(<scope>): <short description>

<body — what changed and why>

<footer — closes issues, breaking changes>
```

**Types**: `fix`, `feat`, `docs`, `refactor`, `test`, `chore`  
**Scopes**: `threading`, `pipeline`, `dashboard`, `logs`, `profile`, `core`

Example:
```
fix(threading): separate applications into individual threads per job ID

- Fixed grouping logic to use unique job ID instead of company name
- Added German email template parser for application confirmations

Closes #42
```

## Development Guidelines

### Next.js Dashboard
- We strictly observe **Vanilla CSS Modules** (no Tailwind).
- Ensure all components are responsive and respect both **Light and Dark mode** toggles.
- Run `npm run lint` before committing anything.
- Use shared utilities from `src/lib/` (e.g., `status.ts` for status normalization, `env.ts` for environment variables).

### Python AI Engine
- We enforce strict typing using `Pydantic` models.
- All pipeline stage outputs must be persisted to `pipeline_run_steps.stats` for resumability.
- Ensure new LLM classification features gracefully fallback if Gemini's API throws a rate limit.
- Run `ruff check .` to auto-fix styling errors.
- Use `Status.APPLIED.value` (not `str(Status.APPLIED)`) to get human-readable enum values.

### Environment Variables
- All secrets and config strings live in a **single root `.env` file**.
- Never add `.env.local` or duplicate env files in subdirectories.
- The dashboard reads the root `.env` via `dotenv` in `next.config.ts`.

## Pull Requests

1. One feature/fix per branch — keep PRs focused.
2. Name your branch semantically (see above).
3. Ensure `npm run lint` passes for dashboard changes.
4. Ensure `ruff check .` and `python3 -c "import ast; ast.parse(open('file.py').read())"` pass for tracker changes.
5. Fill out the PR template entirely — we will not review PRs without proper testing evidence.
