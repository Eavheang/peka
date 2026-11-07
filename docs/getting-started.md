# Getting started

Run all Compose commands from `config/` unless noted otherwise.

## Prerequisites

- Docker and Docker Compose
- For optional CUDA llama.cpp / GPU embeddings: NVIDIA Container Toolkit and a compatible driver
- For host-side development without Compose: Python 3.12, Bun, Postgres with `pgvector`

## One-time setup

```bash
cd config
make setup
```

`make setup` will:

1. Copy `config/.env.example` → `config/.env` if missing
2. Build and start `postgres`, `pgadmin`, `embeddings`
3. Run `alembic upgrade head` (so tables exist before the API boots)
4. Build and start `service`, `index-worker`
5. Install webclient dependencies with Bun and start `webclient` + `proxy`

Also copy and fill **service** env before first useful run:

```bash
cp service/.env.example service/.env
# edit JWT_SECRET_KEY, LLM_*, ADMIN_* as needed
```

Webclient (local Bun outside Docker):

```bash
cp webclient/.env.example webclient/.env.local
# NEXT_PUBLIC_API_URL=http://localhost:8000
```

Inside Compose, the UI uses `NEXT_PUBLIC_API_URL=/api` (nginx proxies `/api/` to the API).

## Daily development

```bash
cd config
make up      # hot-reload stack (compose.yaml + compose.dev.yaml)
make down    # stop
make migrate # apply pending Alembic migrations
```

Re-run `make setup` when Dockerfiles or dependency lockfiles change. Source edits hot-reload in development containers.

## First admin user

If both are set in `service/.env`, the API bootstraps the first admin on startup (only when no admin exists yet):

- `ADMIN_EMAIL`
- `ADMIN_PASSWORD` (12–1024 characters)

Then open http://localhost:3000/sign-in and sign in.

## Optional local LLM (llama.cpp)

GGUF weights live under `config/model/` (gitignored). Settings are in `config/llama/config.yaml`.

```bash
cd config
docker compose --profile llama up -d llama
```

OpenAI-compatible endpoint: `http://localhost:8080/v1/...`

Point the service at it via `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` in `service/.env` (in Compose, the worker can use `http://llama:8080/v1`).

## Default database / pgAdmin

| Setting | Default |
|---------|---------|
| Postgres host (from pgAdmin container) | `postgres` |
| Port | `5432` |
| Database | `peka` |
| User / password | `peka` / `peka_dev_password` |
| pgAdmin login | from `config/.env` (`PGADMIN_*`) |

Override with `POSTGRES_*` and `PGADMIN_*` in `config/.env`.

## Production-style Compose

```bash
cd config
make prod-up    # compose.yaml only (built images, no hot reload)
make prod-down
```

## Next reading

- [Architecture](architecture/overview.md)
- [Config & Docker](config/README.md)
- [Security](security.md)
