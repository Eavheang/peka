# PEKA Documentation

**PEKA** (Personal Knowledge Base) is an organization-private RAG assistant. Users upload documents, the system converts them into a structured knowledge base, embeds them for retrieval, and answers questions with citations—optionally augmented by web search.

## Start here (understand the product)

Read these first if you want to know **what PEKA does** and **how it works**:

| # | Document | Why |
|---|----------|-----|
| 1 | [What is PEKA?](what-is-peka.md) | Problem, audience, what it is / isn’t |
| 2 | [How it works](how-it-works.md) | End-to-end: upload → index → cited answer |
| 3 | [User guide](user-guide.md) | Screens and tasks by role |
| 4 | [OKF & indexing](architecture/okf-and-indexing.md) | Document pipeline deep dive |
| 5 | [Chat & RAG](architecture/chat-and-rag.md) | Question → retrieval → answer deep dive |

## Reference (build, operate, integrate)

| Document | Audience | Contents |
|----------|----------|----------|
| [Getting started](getting-started.md) | Everyone | Setup, URLs, admin bootstrap, llama |
| [Architecture overview](architecture/overview.md) | Developers | Components, layering, integrations |
| [Key flows](architecture/flows.md) | Developers | Compact technical flow charts |
| [API reference](service/api-reference.md) | Frontend / integrators | HTTP endpoints |
| [Data model](service/data-model.md) | Backend | Tables, migrations, storage |
| [Service](service/README.md) | Backend | FastAPI modules, env vars |
| [Web client](webclient/README.md) | Frontend | Routes, auth, React Query services |
| [Config & Docker](config/README.md) | Ops | Compose, Makefile, nginx, llama |
| [Security & roles](security.md) | Everyone | JWT, ACL, bootstrap |
| [Development & CI](development.md) | Contributors | Tests, Husky, PR checks |
| [Glossary & troubleshooting](glossary-and-troubleshooting.md) | Everyone | Terms and common fixes |

## Repository layout

```text
peka/
├── config/       # Docker Compose, Makefile, nginx, llama/model mounts
├── service/      # FastAPI API + OKF background worker
├── webclient/    # Next.js App Router UI
├── docs/         # This documentation
├── .github/      # PR CI workflows
└── .husky/       # pre-commit / pre-push gates
```

## Quick start

From `config/`:

```bash
make setup   # once (or when Dockerfiles / lockfiles change)
make up      # start the dev stack
```

| Service | URL |
|---------|-----|
| Web UI (via nginx) | http://localhost:3000 |
| API | http://localhost:8000 |
| OpenAPI docs | http://localhost:8000/docs |
| Health | http://localhost:8000/health |
| pgAdmin | http://localhost:5050 |
| llama.cpp (optional profile) | http://localhost:8080 |

See [Getting started](getting-started.md) for env files, admin bootstrap, and optional local LLM.
