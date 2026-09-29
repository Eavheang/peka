# Architecture overview

PEKA is a three-tier stack: a Next.js UI, a FastAPI service with a sibling OKF worker, and supporting infrastructure (Postgres/pgvector, TEI embeddings, optional llama.cpp, nginx).

## Component diagram

```text
┌─────────────────────────────────────────────────────────────┐
│  Browser                                                    │
└───────────────────────────┬─────────────────────────────────┘
                            │
                    ┌───────▼───────┐
                    │  nginx proxy  │  :3000 (host)
                    │  / → UI       │
                    │  /api/ → API  │
                    └───┬───────┬───┘
                        │       │
            ┌───────────▼─┐   ┌─▼──────────────┐
            │  webclient  │   │  service       │  :8000
            │  Next.js 16 │   │  FastAPI       │
            └─────────────┘   │  uvicorn        │
                              └─┬──────────┬───┘
                                │          │
                     ┌──────────▼──┐  ┌────▼────────────┐
                     │  postgres   │  │  okf-worker     │
                     │  + pgvector │  │  same image     │
                     └─────────────┘  └────┬────────────┘
                                           │
                              ┌────────────▼────────────┐
                              │  embeddings (TEI)       │
                              │  BAAI/bge-small-en-v1.5 │
                              │  384-d vectors          │
                              └─────────────────────────┘

                    optional profile: llama (CUDA llama.cpp :8080)
```

## Responsibilities

| Component | Role |
|-----------|------|
| **webclient** | Auth UI, chat (SSE), knowledge library, admin user/provider settings |
| **service** | REST + SSE API: auth, files, search, chat, admin provider settings |
| **okf-worker** | Polls `okf_jobs`, LLM conversion to OKF markdown, chunk + embed, activate chunk sets |
| **postgres** | Users, files, jobs, chunks (vector), conversations, provider settings |
| **embeddings** | Hugging Face Text Embeddings Inference (OpenAI-compatible `/v1/embeddings`) |
| **llama** (optional) | Local OpenAI-compatible chat completions for OKF + chat |
| **nginx** | Single entry: UI + `/api` strip-proxy; long timeouts for streams |

## Backend layering

Feature modules under `service/app/<feature>/` follow:

```text
routes → service → repository
```

- **Routes**: FastAPI routers, auth deps, status codes
- **Schemas**: Pydantic request/response models
- **Services**: Business logic, RAG/LLM orchestration
- **Repositories**: SQL via `psycopg` (`dict_row`)
- **Models**: SQLAlchemy declarative models primarily for Alembic metadata

Routers are registered explicitly in `service/app/__init__.py` and mounted from `app.main:app`.

## Frontend layering

```text
app/ (thin pages)
  → _partials/ (route-local UI)
  → components/ (shared Theme + ui)
  → services/ (React Query + axios / fetch)
  → utils/ (auth storage, HTTP client)
  → interface/ (TS types)
```

Workspace routes are gated by Next.js 16 `proxy.ts` (cookie presence) and further by client-side `/auth/me` and role checks.

## External integrations

| Integration | Config | Use |
|-------------|--------|-----|
| OpenAI-compatible LLM | `LLM_*` env + optional DB overrides | Chat answers, OKF conversion, retrieval planning |
| TEI embeddings | `EMBEDDING_*` | Query and chunk vectors |
| Exa | `EXA_*` (optional) | Web search when user enables it |

Admin can override LLM/Exa URL, key, and model at runtime via `/admin/settings/providers` (stored in `provider_settings`). Embedding settings remain environment-only.

## What is not in the stack

- No Redis/Celery — OKF uses a Postgres job table and a single polling worker
- No FastAPI CORS middleware in code (browser hits same origin via nginx `/api` in Compose)
- No message broker for chat history — conversations live in Postgres

## Related docs

- [Key flows](flows.md)
- [Service](../service/README.md)
- [Web client](../webclient/README.md)
- [Config](../config/README.md)
