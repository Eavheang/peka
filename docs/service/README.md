# Service (backend)

FastAPI application that powers PEKA: authentication, document ingestion, vector search, chat (sync + SSE), and admin provider settings. A sibling process (`index-worker`) converts uploads into the Open Knowledge Format knowledge base and indexes embeddings.

Package entrypoint: `app.main:app`  
Interactive OpenAPI: http://localhost:8000/docs  
Health: `GET /health` → `{"status":"ok"}`

## Tech stack

| Piece | Detail |
|-------|--------|
| Runtime | Python 3.12 |
| Framework | FastAPI `0.115.4` |
| ASGI | uvicorn |
| Settings | pydantic-settings |
| DB access | psycopg 3 (runtime SQL) + SQLAlchemy models (Alembic) |
| Migrations | Alembic |
| Vectors | pgvector, 384 dimensions |
| Auth | PyJWT + pwdlib Argon2 |
| LLM SDK | `ai[openai]` (Vercel AI Python SDK) |
| Extraction | PyMuPDF, python-docx, python-pptx, openpyxl |
| Dependencies | `service/requirements.txt` (no `pyproject.toml`) |

## Directory map

```text
service/
├── app/
│   ├── main.py                 # FastAPI app, lifespan, /health
│   ├── config.py               # Settings from env
│   ├── database.py             # Base, get_connection()
│   ├── workspace_settings.py   # Admin provider settings router
│   ├── auth/                   # login, users, JWT
│   ├── audit/                  # FR10 audit log: routes → service → repository
│   ├── files/                  # upload, list, download, index status
│   ├── chat/                   # chat, stream, conversations, preview
│   └── engine/
│       ├── ai_runtime.py       # structured generate / stream
│       ├── source_extractor.py
│       ├── indexing/           # indexing worker, jobs
│       ├── chunks/             # chunker, embeddings, models
│       ├── search/             # vector search API
│       └── web_search/         # Exa client
├── alembic/versions/           # 002…018
├── storage/                    # uploads, extracted JSON, knowledge_base
├── tests/
├── Dockerfile
├── requirements.txt
└── .env.example
```

## Running

### Via Docker (recommended)

See [Config & Docker](../config/README.md) and [Getting started](../getting-started.md).

### On the host

```bash
cd service
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env   # fill required values
uvicorn app.main:app --reload

# separate terminal — indexing worker
python -m app.engine.indexing.worker
```

Requires reachable Postgres (with `vector`), embedding server, and LLM endpoint.

## Environment variables

`service/.env.example` holds only what an install has to decide. Every other option below has a default in `app/config.py` and can still be set in `service/.env`. Field names map to `app/config.py` (case-insensitive).

| Variable | Required | Notes |
|----------|----------|-------|
| `APP_NAME` | no | Default `PEKA Service` |
| `DEBUG` | no | |
| `DATABASE_URL` | yes | Postgres URL |
| `FILE_STORAGE_DIR` | no | Default `storage` |
| `LLM_BASE_URL` | yes | OpenAI-compatible base |
| `LLM_API_KEY` | no | Default `local`, which llama.cpp ignores. A hosted model needs its own key |
| `LLM_MODEL` | yes | |
| `LLM_MAX_TOKENS` | no | Default 2048; longest answer. An existing `.env` with 8192 keeps the old limit and can overflow a shared local context |
| `LLM_MAX_CONCURRENT_CHATS` | no | Default 2; chats answered at once, the others wait. Raise it only with a larger context |
| `EMBEDDING_BASE_URL` | no | Default `http://localhost:8081/v1` |
| `EMBEDDING_MODEL` | no | `BAAI/bge-small-en-v1.5` |
| `EMBEDDING_DIMENSIONS` | no | `384` |
| `EMBEDDING_BATCH_SIZE` | no | `1` |
| `SEARCH_TOP_K` | no | `10`; results from `POST /search` |
| `RERANK_BASE_URL` | no | Default `http://localhost:8082` |
| `RERANK_CANDIDATES` | no | `20` |
| `RERANK_TOP_K` | no | `5`; sources sent to the chat model |
| `SEARCH_EVIDENCE_FLOOR` | no | `0.1`; below this top rerank score, chat keeps an answer to a question for a specific fact only if it cites a source, and otherwise refuses. `0` turns it off. Retune it if the rerank model changes |
| `CITATION_MATCH_FLOOR` | no | `0.5`; when the model cites none of the sources it used, the server cites those scoring at least this against an answer block. Retune it if the rerank model changes |
| `SEARCH_SIMILARITY_FLOOR` | no | `0.3` |
| `EXA_API_KEY` | no | Empty disables web search |
| `EXA_BASE_URL` | no | Default Exa API |
| `WEB_SEARCH_TOP_K` | no | `5` |
| `WEB_SEARCH_TIMEOUT` | no | `20` |
| `JWT_SECRET_KEY` | yes | ≥32 chars |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | no | 1–60 |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | no | Default 30 (not in example file) |
| `JWT_ISSUER` / `JWT_AUDIENCE` | no | Defaults `peka-service` / `peka-api` |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | both or neither | First-admin bootstrap |
| `MAX_UPLOAD_BYTES` | no | Default 25×1024×1024 |
| `APP_BASE_URL` | no | Default `http://localhost:3000`. Fallback base for invitation links. Normally the link uses the admin's own browser address (the request `Origin`), so it matches localhost, a LAN address or a tunnel without any switching; this value is used only when a request carries no valid `Origin` (e.g. curl) |
| `INVITATION_EXPIRE_DAYS` | no | 1–30, default 7 |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` / `SMTP_FROM` | no | Invitation email over STARTTLS (default port 587). Gmail: `smtp.gmail.com` plus an app password. Empty host disables sending; admins can still copy the invite link |

`LLAMA_*` env names are **not** supported; use `LLM_*`.

## Feature modules

### Auth (`app/auth/`)

Login, refresh, logout, profile, password change, admin user CRUD/role/activation. See [API reference](api-reference.md) and [Security](../security.md).

### Files (`app/files/`)

Multipart upload, listing (ACL-filtered), download, delete, index status, retry, access-level patch (admin).

### Search (`app/engine/search/`)

`POST /search` — embed query, cosine similarity over **active** chunk sets, ACL + similarity floor.

### Chat (`app/chat/`)

Retrieval planning, KB and/or Exa grounding, structured answers with citations, conversation CRUD, source preview, SSE stream.

### Engine indexing (`app/engine/indexing/`)

- `worker.py` — claim jobs with `FOR UPDATE … SKIP LOCKED`, reset stuck `processing`, index source text
- Max **3** attempts per job

### Chunks & embeddings (`app/engine/chunks/`)

Structure-aware chunking of original text, TEI embeddings, `chunk_sets` versioning (`building` → `active`, old → `superseded`).

### Workspace settings (`app/workspace_settings.py`)

Admin LLM/Exa runtime overrides in `provider_settings`.

## Dockerfile

Image installs `requirements.txt`, copies `app/`, `alembic/`, `alembic.ini`, `storage/`, exposes `8000`, default CMD uvicorn. Compose overrides command for `index-worker`.

## Further reading

- [API reference](api-reference.md)
- [Data model](data-model.md)
- [Key flows](../architecture/flows.md)
- `service/AGENTS.md`
