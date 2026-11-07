# Config and Docker orchestration

All local stack commands run from `config/`. This directory owns Compose files, the Makefile, nginx, optional llama.cpp wiring, and model mounts.

## Files

| Path | Purpose |
|------|---------|
| `Makefile` | `setup`, `up`, `down`, `migrate`, `prod-up`, `prod-down` |
| `compose.yaml` | Base services (prod-style) |
| `compose.dev.yaml` | Hot-reload overlays (bind mounts, bun/uvicorn reload) |
| `.env.example` / `.env` | Postgres, pgAdmin |
| `nginx.conf` | `/` → webclient, `/api/` → service |
| `llama/config.yaml` | llama.cpp generation / model settings |
| `llama/entrypoint.sh` | Maps YAML → `llama-server` flags |
| `model/` | GGUF weights (gitignored) |

Application secrets for the API/worker still live in `service/.env` (`env_file` in Compose).

## Makefile targets

```bash
make setup     # .env if missing; postgres/embeddings; migrate; then API + webclient
make up        # start compose.yaml + compose.dev.yaml
make migrate   # alembic upgrade head (one-shot service container)
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
| `index-worker` | same service image | — | `python -m app.engine.indexing.worker` |
| `embeddings` | TEI `cpu-1.9` | (internal 80) | BGE-small embeddings |
| `reranker` | TEI `cpu-1.9` | (internal 80) | Cross-encoder that reranks search hits, on CPU |
| `proxy` | `nginx:alpine` | `${WEBCLIENT_PORT:-3000}` | Public entry |
| `llama` | llama.cpp CUDA (profile `llama`) | 8080 | Optional local LLM |

Shared volume `file_storage` is mounted at `/app/storage` for `service` and `index-worker`.

Service env overrides in Compose include `DATABASE_URL` → `postgres` and `EMBEDDING_BASE_URL` → `http://embeddings:80/v1` and `RERANK_BASE_URL` → `http://reranker:80`.

## Config `.env` variables

From `config/.env.example`:

```env
POSTGRES_DB=peka
POSTGRES_USER=peka
POSTGRES_PASSWORD=peka_dev_password
PGADMIN_DEFAULT_EMAIL=admin@example.com
PGADMIN_DEFAULT_PASSWORD=peka_admin_password
```

Optional, with defaults in `compose.yaml`: `WEBCLIENT_PORT`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`, `EMBEDDING_BATCH_SIZE`, `RERANK_MODEL`. `JWT_SECRET_KEY` is read from `service/.env` only.

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
