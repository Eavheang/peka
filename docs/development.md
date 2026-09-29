# Development and CI

## Local quality gates (Husky)

Hooks live in `.husky/`. **pre-commit** and **pre-push** share the same logic over staged paths (`git diff --cached`):

| Path match | Command |
|------------|---------|
| `*service/*` | `cd service && python -m pytest` |
| `*webclient/*` | `cd webclient && bun run lint-fix && bun run tsc && bun run format` |

## GitHub Actions

Both workflows run on `pull_request` to `main` with path filters. They are **CI only** (no image push / deploy).

### Backend — `.github/workflows/backend.yml`

- Paths: `service/**` (or the workflow file)
- Python 3.12, `pip install -r requirements.txt`, `python -m pytest`
- Working directory: `service`

### Frontend — `.github/workflows/frontend.yml`

- Paths: `webclient/**` (or the workflow file)
- Bun (`oven-sh/setup-bun@v2`), `bun ci`, `bun run tsc`, `bun run lint`
- Working directory: `webclient`

## Running tests locally

### Service

```bash
cd service
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest
python -m pytest tests/test_health.py::test_healthcheck
```

`pytest.ini` sets `pythonpath = .`. Tests use FastAPI `TestClient`; `conftest.py` supplies safe default env for imports.

### Webclient

```bash
cd webclient
bun install --frozen-lockfile   # or bun ci
bun run lint
bun run tsc                     # or bunx tsc --noEmit
bun run format-check
```

## Agent / contributor conventions

| Area | File |
|------|------|
| Service layout & commands | `service/AGENTS.md` |
| Webclient commands & structure | `webclient/AGENTS.md` |
| Webclient deep guidance | `webclient/.agents/*.md` |

Backend features: keep `routes → service → repository`. Register new routers in `app/__init__.py`. Document new env vars in `service/.env.example`. Never create tables from FastAPI startup—use Alembic.

Frontend: Bun lockfile only; thin `page.tsx`; route-local `_partials/`; `'use client'` only where needed.

## Database migrations

```bash
cd service
alembic revision --autogenerate -m "describe schema change"
# review alembic/versions/…

cd ../config
make migrate
```
