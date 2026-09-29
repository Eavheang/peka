# Key flows

## 1. Document upload → knowledge index

```text
Client multipart upload
        │
        ▼
POST /files  (auth + ACL)
  • validate type / size (default max 25 MiB)
  • stream to storage/{pdf|docx|pptx|xlsx|others}/…
  • SHA-256 dedup (unique on files.sha256)
  • extract text → storage/extracted/{source_id}.json
  • insert files + okf_jobs(status=queued)
        │
        ▼
okf-worker (poll, SKIP LOCKED, max 3 attempts)
  • load extracted JSON
  • LLM convert → Open Knowledge Format markdown
  • write storage/knowledge_base/<category>/<concept>.md
  • rebuild category / root index.md trees
  • chunk by # headings (max ~3000 chars, overlap)
  • embed batches via TEI
  • insert chunk_sets(building) + knowledge_chunks
  • swap: supersede old active set → activate new set
```

**Statuses** on a file (via job): `queued` → `processing` → `completed` | `failed`.

Failed jobs can be requeued with `POST /files/{id}/retry-okf` (author or admin). The UI polls the file list every 3s while any file is queued/processing.

### Access levels

| Level | Who can see / retrieve |
|-------|------------------------|
| `general` | `admin`, `senior`, `staff` |
| `confidential` | `admin`, `senior` only (upload of confidential requires admin) |

Vector search and chat retrieval always filter by the caller's role ACL.

---

## 2. Chat (non-streaming)

```text
POST /chat  { query, conversation_id?, web_search? }
        │
        ▼
Load owned conversation history (budget ~24k chars / last 20 turns)
        │
        ▼
LLM structured SearchPlan
  none | search_knowledge_base | web_search
        │
        ├─ KB → embed query → cosine on active chunks (floor + top_k + ACL)
        └─ Web → Exa /search (if key configured and web_search=true)
        │
        ▼
Inject <search_results> → LLM structured ModelAnswer (blocks)
        │
        ▼
Normalize citations [1], [2], … → persist messages → ChatResponse
```

---

## 3. Chat (SSE stream)

Same plan/search path as above, then:

```text
POST /chat/stream
  Content-Type: application/json
  Accept: text/event-stream

Events (data: lines):
  status  — progress hints
  text    — incremental answer text (JSON stream parser)
  done    — final payload (citations, conversation_id, …)
  error   — failure
  [DONE]  — terminator
```

On `done`, messages are persisted. New chats navigate the UI to `/workspace/{conversationId}`.

---

## 4. Authentication

```text
POST /auth/login { email, password }
  → access_token + refresh_token (JWT HS256)
  → webclient stores in localStorage or sessionStorage (+ cookie for proxy)

Authenticated requests: Authorization: Bearer <access>

401 → POST /auth/refresh → retry once → else clear storage → sign-in

Logout / password change / role or activation change
  → users.token_version++
  → old tokens rejected (claim ver must match)
```

Workspace edge gate: `proxy.ts` requires cookie `peka_access_token` for `/workspace/*`.

---

## 5. Source preview & citations

- Chat returns citations with titles/headings (and optional web URLs).
- `POST /chat/source-preview` resolves an active chunk by optional `chunk_id` + title + heading under ACL.
- File download for a citation uses `GET /files/{file_id}` when a knowledge file is attached.

---

## 6. Admin provider settings

Admins can override LLM and Exa endpoints without redeploying:

1. `GET /admin/settings/providers` — URLs/models + configured flags (keys never returned)
2. `PUT /admin/settings/providers` — upsert JSON in `provider_settings` (id=1)
3. `POST /admin/settings/providers/test/{llm|exa}` — connectivity check

Runtime `provider_config()` merges DB overrides over env for LLM/Exa. Embeddings stay env-only.
