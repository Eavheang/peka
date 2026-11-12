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

1. Create `config/.env` from `config/.env.example` if it is missing, and generate `POSTGRES_PASSWORD` and `PGADMIN_DEFAULT_PASSWORD`
2. Build and start `postgres`, `embeddings`, and `reranker`
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

Dev ports listen on `127.0.0.1`. To publish one on the LAN, edit the bind address in `config/compose.dev.yaml` (for example `"127.0.0.1:5432:5432"` to `"5432:5432"`). Postgres is protected only by its password, and llama has no authentication. See [Security](security.md).

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

OpenAI-compatible endpoint, listening on localhost only: `http://127.0.0.1:8080/v1/...`

Point the service at it via `LLM_BASE_URL`, `LLM_API_KEY`, and `LLM_MODEL` in `service/.env` (in Compose, the worker can use `http://llama:8080/v1`).

## Default database / pgAdmin

| Setting | Default |
|---------|---------|
| Postgres host (from pgAdmin container) | `postgres` |
| Port | `5432` (localhost only in development) |
| Database | `peka` |
| User / password | `peka` / from `config/.env` (`POSTGRES_PASSWORD`) |
| pgAdmin login | from `config/.env` (`PGADMIN_*`) |

Override with `POSTGRES_*` and `PGADMIN_*` in `config/.env`. pgAdmin is not started by `make setup` or `make up`. Set `PGADMIN_DEFAULT_EMAIL` and `PGADMIN_DEFAULT_PASSWORD` in `config/.env`, then start it with:

```bash
docker compose -f compose.yaml -f compose.dev.yaml --profile pgadmin up -d pgadmin
```

## Existing install

A database volume created with the old default still has the password `peka_dev_password`. Set a new password, then put that same value in `POSTGRES_PASSWORD` in `config/.env`:

```bash
docker compose -f compose.yaml -f compose.dev.yaml exec postgres psql -U peka -d peka -c "ALTER USER peka PASSWORD '<new>';"
```

Or remove the volumes and start over. This deletes the database data and other named volumes:

```bash
docker compose -f compose.yaml -f compose.dev.yaml down -v
```

If `PGADMIN_DEFAULT_PASSWORD` is still `peka_admin_password`, replace it in `config/.env` as well. pgAdmin keeps its own login in the `pgadmin_data` volume, so also change that password in pgAdmin, or delete the volume.

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
