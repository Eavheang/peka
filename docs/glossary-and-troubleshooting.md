# Glossary

| Term | Meaning |
|------|---------|
| **PEKA** | Personal Knowledge Base — this product |
| **OKF** | Open Knowledge Format (v0.2) — LLM-normalized Markdown concept + indexes under `knowledge_base/` |
| **Concept** | One OKF Markdown article for a source document (`knowledge_base/<category>/<file>.md`) |
| **okf-worker** | Background process that drains `okf_jobs`, writes OKF, chunks, and embeds |
| **chunk set** | Versioned embedding index for a file (`building` → `active` → `superseded`) |
| **Retrieval router** | First LLM call each chat turn; chooses `none` / KB / web search |
| **Grounded block** | Answer segment that cites current-turn source IDs |
| **General block** | Answer segment from model knowledge with no citations |
| **RAG** | Retrieval-augmented generation — chat grounded on search results |
| **TEI** | Hugging Face Text Embeddings Inference server |
| **ACL / access_level** | `general` vs `confidential` document visibility by role |
| **provider settings** | Runtime DB overrides for LLM and Exa endpoints |
| **SSE** | Server-Sent Events used by `POST /chat/stream` |
| **Exa** | Optional public web search provider |

# Troubleshooting

| Symptom | Checks |
|---------|--------|
| UI loads but API 401 loops | Clear storage/cookies; confirm JWT secret ≥32 chars; refresh token still valid |
| Uploads stuck in `queued` | Is `okf-worker` running? LLM reachable? Check job `last_error` / file okf-status |
| `failed` OKF jobs | `POST /files/{id}/retry-okf` or fix LLM/prompt; max 3 attempts |
| Empty / weak search | Embeddings healthy? Migration `012` applied (384-d)? Similarity floor too high? |
| Web search never used | `EXA_API_KEY` set? Toggle enabled in UI? Chat body `web_search: true`? |
| Admin pages redirect | User `role` must be `admin` (`GET /auth/me`) |
| Compose UI can't reach API | `NEXT_PUBLIC_API_URL` should be `/api` in Docker builds; nginx up? |
| Migration errors | Run `make migrate` from `config/`; ensure Postgres healthy |
| llama profile won't start | NVIDIA toolkit, GGUF present, `model:` filename matches file under `config/model/` |
