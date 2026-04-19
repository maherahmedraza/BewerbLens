# Contributing to BewerbLens

Thank you for your interest in contributing! BewerbLens is a monorepo containing a Python AI pipeline (`apps/tracker`), a FastAPI orchestrator (`apps/orchestrator`), and a Next.js dashboard (`apps/dashboard`).

## Getting Started

1. **Fork** the repository and clone it locally.
2. Initialize the environment:
   ```bash
   cp .env.example .env
   pip install -r requirements.txt
   cd apps/dashboard && npm install
   ```
3. Apply database migrations — see [docs/deployment.md](docs/deployment.md#database-setup).

## Development Guidelines

### Branch Naming
- `feat/` — New features (e.g., `feat/add-analytics-chart`)
- `fix/` — Bug fixes (e.g., `fix/duplicate-applications`)
- `docs/` — Documentation updates
- Always branch off `main`.

### Next.js Dashboard
- We strictly observe **Vanilla CSS Modules** (no Tailwind).
- Ensure all components are responsive and respect both **Light and Dark mode** toggles.
- Run `npm run lint` before committing.
- All `NEXT_PUBLIC_*` environment variables are injected by the platform in production — never hardcode them.

### Python Backend
- We enforce strict typing using `Pydantic` models.
- All secrets must come from `os.environ` — never hardcode API keys.
- Run `ruff check apps/tracker apps/orchestrator` before committing.
- The root `requirements.txt` is the single source of truth for Python dependencies.

### Docker
- The `Dockerfile` at the project root builds the backend image.
- Test your changes locally with `docker build -t bewerblens .` before pushing.

## CI/CD

Every push triggers the CI pipeline (`.github/workflows/ci.yml`):
- **Backend**: Ruff lint + pytest
- **Dashboard**: ESLint + Next.js build
- **Security**: Gitleaks secret scan

Merges to `main` auto-deploy:
- Frontend → Vercel (path-filtered to `apps/dashboard/**`)
- Backend → DigitalOcean (path-filtered to `apps/tracker/**`, `apps/orchestrator/**`, `Dockerfile`, `requirements.txt`)

## Pull Requests

1. Always branch off `main`.
2. Name your branch semantically (e.g., `feat/add-new-chart`, `fix/resolve-infinite-loop`).
3. Ensure CI passes before requesting review.
4. Fill out the PR description with a summary of changes, screenshots for UI changes, and any breaking changes.
