# How PEKA works

This page explains the system **as a story**: what happens from first login to a cited answer. For folder layouts and APIs, see the linked deep dives.

## Big picture

```text
┌──────────────┐     ┌──────────────┐     ┌─────────────────────────────┐
│  Web client  │────▶│  FastAPI     │────▶│  Postgres + pgvector        │
│  (Next.js)   │◀────│  service     │◀────│  users, files, chunks, chat │
└──────────────┘     └──────┬───────┘     └─────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
        ┌──────────┐  ┌──────────┐  ┌────────────┐
        │ OKF      │  │ TEI      │  │ LLM        │
        │ worker   │  │ embed    │  │ (OpenAI-   │
        │          │  │ server   │  │ compatible)│
        └────┬─────┘  └──────────┘  └────────────┘
             │                ▲             ▲
             └────────────────┴─────────────┘
               shared storage: uploads + extracted text
```

The worker calls the LLM only when optional OKF enrichment is turned on.

Nginx (in Docker) sits in front so the browser talks to one origin: UI at `/`, API at `/api/…`.

---

## Lifecycle of a document

Imagine an admin uploads `Q3-launch-plan.pdf` as **general**.

### 1. Upload (API, synchronous)

1. Browser sends multipart `POST /files`.
2. Service checks type, size (default 25 MiB), and SHA-256 (duplicate content is rejected).
3. File is written under `storage/pdf/…` (or another type folder).
4. Text is **extracted** (pages/sections/slides/sheets) into `storage/extracted/{source_id}.json`.
5. A row is inserted in `files`, and an `okf_jobs` row is created as **`queued`**.
6. The API returns immediately — indexing is **not** finished yet.

The Knowledge page keeps polling the file list every few seconds while status is `queued` or `processing`.

### 2. Chunk + embed (worker, asynchronous, no LLM)

The `okf-worker` process loops forever:

1. Claim the next `queued` job (`FOR UPDATE … SKIP LOCKED`).
2. Load the extraction JSON. A file with no text fails here.
3. Chunk the **original text**: one chunk per heading, page, or slide, with tables and sheets as their own chunks. Each chunk fits the embedder's 512-token window; longer parts split into `Page 3`, `Page 3 (part 2)`, and so on.
4. Each chunk’s embedding text looks like:  
   `Document: <file name>\nSection: <heading>\n\n<content>`
5. Send batches to the TEI embeddings server (`BAAI/bge-small-en-v1.5`, **384** dimensions).
6. Insert a new `chunk_sets` row in `building`, store `knowledge_chunks`, then **atomically** mark the new set `active` and old ones `superseded`.

After this, search can find the document, and citations quote its source text with locators from the extractor. Status becomes **`completed`** (or **`failed`** after up to 3 attempts).

### 3. Optional OKF enrichment

Off by default (`OKF_ENRICHMENT_ENABLED`). When on, and only after the file is searchable, a background thread asks the LLM for a normalized OKF article and writes it to `storage/knowledge_base/`. Search does not use it, and if it fails the file stays indexed.

Details: [Indexing & OKF](architecture/okf-and-indexing.md).

---

## Lifecycle of a question

A staff user asks: *“What changed in our Q3 launch plan?”*

### 1. Client

- UI posts to `POST /chat/stream` (SSE) with `{ query, conversation_id?, web_search? }`.
- It shows optimistic bubbles and updates text as events arrive.

### 2. Retrieval plan (only when it is needed)

A first question with web search off makes no planning call: the server searches the knowledge base with the question as written, so the answer is the only model call.

For a follow-up, or whenever the user has web search on, the API first asks the model for a **SearchPlan**:

| `tool` | Meaning |
|--------|---------|
| `search_knowledge_base` | Search the company/docs the user may access |
| `web_search` | Public/current info — **only if** the user enabled web search |
| `none` | Not honored: the knowledge base is still searched |

The router may rewrite the question into a self-contained search `query` using conversation context (follow-ups like “what about the date?”).

If the user disabled web search, a `web_search` plan falls back to knowledge-base search.

### 3. Retrieval (server)

**Knowledge base path:**

1. Embed the search query (same TEI model).
2. Cosine similarity against **active** chunks: `1 - (embedding <=> query)`.
3. Filter by role ACL (`staff` → `general` only; `senior`/`admin` → also `confidential`).
4. Drop hits below `SEARCH_SIMILARITY_FLOOR` (default `0.3`).
5. Rerank the top `RERANK_CANDIDATES` (default `20`) with a local cross-encoder. Chat keeps `RERANK_TOP_K` (default `5`); `POST /search` keeps `SEARCH_TOP_K`. If the reranker fails, the hybrid order is kept.

**Web path:** call Exa when configured; results become citation sources with URLs.

Retrieved snippets are truncated for the prompt (content ~1200 chars) but full metadata remains available for citations.

### 4. Answer (Peka)

The model receives:

- System rules (be Peka; don’t invent private company facts; return structured JSON blocks)
- Recent conversation (historical `[n]` markers stripped so old citations aren’t reused)
- Optional `<search_results>` for **this turn only**

It must return JSON **blocks**:

- `general` — own knowledge / analysis, empty `source_ids`
- `grounded` — text supported by listed current-turn `source_ids`

The **server** appends `[1]`, `[2]`, … markers and builds the `citations` array. The model is told not to write those markers itself.

Messages are saved to the conversation. Streaming uses the same pipeline with incremental text events.

Details: [Chat & RAG](architecture/chat-and-rag.md).

---

## How access control fits in

```text
User role
   │
   ├─ staff  ──────────▶ may retrieve general files only
   ├─ senior ──────────▶ general + confidential
   └─ admin  ──────────▶ general + confidential
                         + manage users, ACL, providers
```

Even if a confidential PDF sits in storage, its chunks never enter a **staff** user’s search results or chat grounding. Upload of confidential files is admin-only; seniors can still *read* them via retrieval once indexed.

---

## How conversations work

- Each chat thread is a `conversation` owned by one user.
- Messages alternate `user` / `assistant`; assistant rows store `citations` JSON.
- Listing uses cursor pagination (`updated_at`, `id`).
- Deleting a conversation is owner-only.
- History is truncated for the model (~24k characters / last ~20 turns) so context stays bounded. Rewriting a follow-up's search query uses only the last 4 messages.

---

## How configuration works at runtime

| Concern | Source of truth |
|---------|-----------------|
| Database, JWT, embeddings, upload limits | Environment (`service/.env` / Compose) |
| LLM URL / key / model, Exa URL / key | Env **or** admin UI → `provider_settings` table |
| llama.cpp sampling / GGUF file | `config/llama/config.yaml` + `config/model/` |

Embeddings are **not** overridable from the admin UI — changing the embedding model requires ops changes and usually a re-index (dimension must match `EMBEDDING_DIMENSIONS` / migration `012`).

---

## Failure modes (expected behavior)

| Situation | What users see |
|-----------|----------------|
| Indexing still running | File shows `queued` / `processing`; chat won’t find it yet |
| Indexing failed, including a file with no text | `failed` + error; Retry OKF available |
| No relevant chunks | Model answers generally or says it doesn’t know the company fact |
| Web search off | Knowledge base is searched instead |
| Web search on, no Exa key | If the model picks web search, the turn fails with “Web search is not configured” |
| Model's answer is not valid JSON | Repaired if possible; plain prose is shown without citations; otherwise an error with a Retry button (no automatic second generation) |
| Token revoked (logout, password, role change) | API 401; UI refresh fails → sign-in |

---

## Suggested reading order for newcomers

1. This page  
2. [User guide](user-guide.md)  
3. [What is PEKA?](what-is-peka.md) (product framing)  
4. [Architecture overview](architecture/overview.md)  
5. [Indexing & OKF](architecture/okf-and-indexing.md) + [Chat & RAG](architecture/chat-and-rag.md)  
6. [API reference](service/api-reference.md) when integrating or debugging HTTP  
