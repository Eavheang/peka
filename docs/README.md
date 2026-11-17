# PEKA Documentation

**PEKA** (Private Enterprise Knowledge Assistant) is an organization-private RAG assistant. Users upload documents, the system chunks their original text into a knowledge base, embeds it for retrieval, and answers questions with citations—optionally augmented by web search.

## Start here (understand the product)

Read these first if you want to know **what PEKA does** and **how it works**:

| # | Document | Why |
|---|----------|-----|
| 1 | [What is PEKA?](what-is-peka.md) | Problem, audience, what it is / isn’t |
| 2 | [How it works](how-it-works.md) | End-to-end: upload → index → cited answer |
| 3 | [User guide](user-guide.md) | Screens and tasks by role |
| 4 | [Indexing](architecture/indexing.md) | Document pipeline deep dive |
| 5 | [Chat & RAG](architecture/chat-and-rag.md) | Question → retrieval → answer deep dive |

## Project record (requirements, design, testing, evaluation)

The academic record of the project, checked against the code: see [Project record](project/README.md).

| Document | Contents |
|----------|----------|
| [Objectives and evaluation](project/objectives-and-evaluation.md) | Problem, aim, the five objectives with verdicts, offline and deployment tests |
| [Requirements](project/requirements.md) | Roles, FR01–FR21 and NFR01–NFR07 with final status, user stories |
| [Design](project/design.md) | Architecture, ER, sequence, use-case and deployment diagrams |
| [Testing](project/testing.md) | Test inventory, test cases, traceability, defect log |
| [Related work](project/related-work.md) | Existing systems, techniques, tool choices, references |
| [Methodology and timeline](project/methodology-and-timeline.md) | Process, reviews, quality controls, risks |
| [Scope changes](project/scope-changes.md) | Proposal versus final system, and why |

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
| [Answer-quality evaluation](evaluation.md) | Everyone | Graded and RAGAS answer-quality runs, why OKF was dropped, limitations |
| [Final report](final-report.md) | Everyone | Verdict on the objectives: Recall@5 over 200+ docs, latency, users served on 6 GB VRAM |
| [System requirements](system-requirements.md) | Everyone | Hardware, software, how to run PEKA locally, what to expect |
| [Backup and restore](backup-and-restore.md) | Ops | What holds state, backup and restore commands |
| [Glossary & troubleshooting](glossary-and-troubleshooting.md) | Everyone | Terms and common fixes |

## Repository layout

```text
peka/
├── config/       # Docker Compose, Makefile, nginx, llama/model mounts
├── service/      # FastAPI API + indexing background worker
├── webclient/    # Next.js App Router UI
├── docs/         # This documentation
├── eval/         # Evaluation scripts, question sets and raw results
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
| API (dev stack) | http://127.0.0.1:8000 |
| OpenAPI docs | http://127.0.0.1:8000/docs |
| Health | http://127.0.0.1:8000/health |
| pgAdmin (optional `--profile pgadmin`) | http://127.0.0.1:5050 |
| llama.cpp (optional profile) | http://127.0.0.1:8080 |

See [Getting started](getting-started.md) for env files, admin bootstrap, and optional local LLM.
