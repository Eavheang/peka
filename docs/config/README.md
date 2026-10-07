# Config and Docker orchestration

All local stack commands run from `config/`. This directory owns Compose files, the Makefile, nginx, optional llama.cpp wiring, and model mounts.

## Files

| Path | Purpose |
|------|---------|
| `Makefile` | `setup`, `up`, `down`, `migrate`, `prod-up`, `prod-down` |
| `compose.yaml` | Base services (prod-style) |
| `compose.dev.yaml` | Hot-reload overlays (bind mounts, bun/uvicorn reload) |
| `.env.example` / `.env` | Postgres, pgAdmin, embedding defaults, `LLM_API_KEY` |
| `nginx.conf` | `/` → webclient, `/api/` → service |
| `llama/config.yaml` | llama.cpp generation / model settings |
| `llama/entrypoint.sh` | Maps YAML → `llama-server` flags |
| `model/` | GGUF weights (gitignored) |

Application secrets for the API/worker still live in `service/.env` (`env_file` in Compose).

## Makefile targets

```bash
make setup     # .env if missing; build/start core services; bun install; migrate
make up        # start compose.yaml + compose.dev.yaml
make migrate   # alembic upgrade head in service container
make down      # tear down the stack
make prod-up   # start compose.yaml only (built images, no hot reload)
make prod-down # tear down the prod-style stack
```

## Compose services

| Service | Image / build | Host ports | Role |
|---------|---------------|------------|------|
| `postgres` | `pgvector/pgvector:pg16` | 5432 | Primary DB + vectors |
| `pgadmin` | `dpage/pgadmin4` | 5050 | DB UI |
| `webclient` | `../webclient` Dockerfile | via proxy | Next.js UI |
| `service` | `../service` Dockerfile | 8000 | FastAPI |
| `okf-worker` | same service image | — | `python -m app.engine.okf.worker` |
| `embeddings` | TEI `cpu-1.9` | (internal 80) | BGE-small embeddings |
| `proxy` | `nginx:alpine` | `${WEBCLIENT_PORT:-3000}` | Public entry |
| `llama` | llama.cpp CUDA (profile `llama`) | 8080 | Optional local LLM |

Shared volume `file_storage` is mounted at `/app/storage` for `service` and `okf-worker`.

Service env overrides in Compose include `DATABASE_URL` → `postgres` and `EMBEDDING_BASE_URL` → `http://embeddings:80/v1`.

## Config `.env` variables

From `config/.env.example`:

```env
POSTGRES_DB=peka
POSTGRES_USER=peka
POSTGRES_PASSWORD=peka_dev_password
PGADMIN_DEFAULT_EMAIL=admin@example.com
PGADMIN_DEFAULT_PASSWORD=peka_admin_password
LLM_API_KEY=replace-with-a-random-secret
EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
EMBEDDING_DIMENSIONS=384
EMBEDDING_BATCH_SIZE=1
```

Optional: `WEBCLIENT_PORT`, `JWT_SECRET_KEY` (Compose default exists for service).

## nginx

- `/api/` → `http://service:8000/` (prefix stripped)
- `/` → `http://webclient:3000`
- Long read timeouts support chat SSE streams

Browser calls the API as `/api/...` when `NEXT_PUBLIC_API_URL=/api`.

## llama.cpp (optional)

1. Place GGUF files in `config/model/`
2. Set `model:` in `config/llama/config.yaml` to the filename
3. Start: `docker compose --profile llama up -d llama`

Key `config.yaml` settings (mapped by entrypoint):

| YAML key | Server flag |
|----------|-------------|
| `model` | `--model /models/<name>` |
| `context_size` | `--ctx-size` |
| `gpu_layers` | `--n-gpu-layers` |
| `batch_size` / `ubatch_size` | batch flags |
| `temperature`, `top_p`, `min_p`, `repeat_penalty` | sampling |

Current default model name in repo config: `gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf` (an alternate MiniCPM GGUF may also be present on disk).

Endpoint: `http://localhost:8080/v1/chat/completions`  
In-network from worker: `http://llama:8080/v1`

## Development vs deployment

| Mode | Command |
|------|---------|
| Dev (hot reload) | `make up` → both compose files |
| Prod-style | `make prod-up` → `compose.yaml` only |

Dev overlays typically bind-mount source and run `uvicorn --reload` / `bun run dev`.

## Note on embeddings docs

Some older prose in `config/README.md` still mentions BGE-M3 / 1024-d / GPU TEI. **Current Compose and service config use** `BAAI/bge-small-en-v1.5` at **384** dimensions on the **cpu-1.9** TEI image. Prefer this documentation and the Compose file as source of truth.
