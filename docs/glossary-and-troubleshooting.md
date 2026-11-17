# Glossary

| Term | Meaning |
|------|---------|
| **PEKA** | Private Enterprise Knowledge Assistant — this product |
| **OKF** | Open Knowledge Format. An earlier design indexed LLM-written OKF pages; it was removed, and older results still mention it |
| **index-worker** | Background process that drains `index_jobs`, chunks original text, and embeds |
| **chunk set** | Versioned embedding index for a file (`building` → `active` → `superseded`) |
| **Retrieval router** | LLM call before the answer, only on a follow-up or with web search on; rewrites the search query and can choose web search |
| **Grounded block** | Answer segment that cites current-turn source IDs |
| **General block** | Answer segment from model knowledge with no citations |
| **Refusal** | Templated "need more detail" reply (`refused: true`) that names the closest documents and asks what the user meant, when no passage matches a question for a specific organization fact, or the model cites none of the weak matches |
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
| Uploads stuck in `queued` | Is `index-worker` running? Embeddings healthy? Check job `last_error` / file index-status |
| `failed` jobs | `No text to index` means extraction found no text, such as a scanned PDF. Otherwise check embeddings, then `POST /files/{id}/retry-indexing`; max 3 attempts |
| Empty / weak search | Embeddings healthy? Migration `012` applied (384-d)? Similarity floor too high? |
| "Need more detail" on a question the documents answer | Is the file `completed`, and can this role see it? Rephrase with the document's own terms, or lower `SEARCH_EVIDENCE_FLOOR` (`0` turns the check off) |
| Answer ends with "cut off" | It reached `LLM_MAX_TOKENS` (default 2048). Ask for less, or for one part at a time |
| `Context size has been exceeded` | Check `service/.env`: `LLM_MAX_TOKENS` should be 2048, not 8192, and `LLM_MAX_CONCURRENT_CHATS` should be 2 |
| Answers take over 30 s on a machine that was fast | Did the laptop suspend? llama's log shows about 10 tokens per second instead of about 85 when the GPU is stuck at low clocks after a resume. Restarting containers does not help; reboot |
| Web search never used | `EXA_API_KEY` set? Toggle enabled in UI? Chat body `web_search: true`? |
| Admin pages redirect | User `role` must be `admin` (`GET /auth/me`) |
| Compose UI can't reach API | `NEXT_PUBLIC_API_URL` should be `/api` in Docker builds; nginx up? |
| Migration errors | Run `make migrate` from `config/`; ensure Postgres healthy |
| llama profile won't start | NVIDIA toolkit, GGUF present, `model:` filename matches file under `config/model/`. If `config/model/` is owned by root and empty, Docker created it because it was missing when llama started: remove it, create it as your user, put the model in, then `make llm` |
| Web client restarts with `next: not found` (fresh `make setup`) | The first `bun install` into the new `node_modules` volume can leave the `next` package incomplete (defect D-27). Run `docker compose -f compose.yaml -f compose.dev.yaml run --rm webclient bun install --frozen-lockfile --force`, then `docker compose -f compose.yaml -f compose.dev.yaml restart webclient` |
| `pytest` stops with `DATABASE_URL uses the old default Postgres password` | `service/.env` still has the pre-November default. Set `POSTGRES_PASSWORD` in `config/.env` and the matching `DATABASE_URL` in `service/.env` (see [Getting started: existing install](getting-started.md#existing-install)) |
| Google Drive import returns 503 | `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_API_KEY`, `GOOGLE_APP_ID` and `APP_BASE_URL` must be set in `service/.env`, and the machine needs internet access |
| Folder sync says "Reconnect Google Drive" | The owner's Google token expired or lacks `drive.readonly`. Choose **Change folder** on the admin settings card and allow access. If it happens every 7 days, the Google OAuth app is still in "Testing"; set it to "In production" |
| Folder sync says "the admin who set it up is no longer an active admin" | The owner was demoted or deactivated. Another admin saves the folder sync again (same folder keeps its history) and allows Drive access if asked |
| Folder sync says "The synced folder is gone…" | The folder was deleted, trashed or unshared from the owner. Nothing was removed from PEKA; pick a folder again |
| Invite email not sent | `SMTP_*` unset or failing: the dialog shows the link to copy instead. Audit events show the failure reason |
