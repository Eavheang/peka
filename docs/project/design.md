# Design

The architecture, data model and main flows of PEKA as built, drawn as Mermaid diagrams (GitHub renders them). Each diagram matches the code on `main` at commit `4a08cd9`. Deeper explanations are in [Architecture overview](../architecture/overview.md), [Key flows](../architecture/flows.md), [Indexing](../architecture/indexing.md), [Chat and RAG](../architecture/chat-and-rag.md) and [Data model](../service/data-model.md).

## Why this design

| Decision | Reason | Requirement |
|----------|--------|-------------|
| One PostgreSQL database for operational data and vectors | The role filter runs inside the same SQL statement as the search, so a restricted chunk never leaves the database | FR13, NFR01 |
| A separate index worker polling a job table | Indexing never blocks chat, and no message broker is needed | FR16, NFR04 |
| Versioned chunk sets, switched only when a job succeeds | A failed re-index leaves the previous index in use | FR16 |
| Embeddings, reranker and language model as local containers | No document text leaves the machine in local mode | NFR03, Objective 2 |
| Citations built by the server from search results | The model cannot invent a source | FR08, Objective 4 |
| Two model slots and a queue | The 6 GB GPU's shared context does not overflow | FR20, NFR04, NFR05 |
| Modular monolith (`routes → service → repository`) | Small team, one deployable service, clear layers | Maintainability |

## Components

```mermaid
flowchart LR
    user([Browser]) --> proxy
    subgraph host["On the organization's machine"]
        proxy["nginx proxy<br/>:3000"] -- "/" --> web["webclient<br/>Next.js 16, React 19"]
        proxy -- "/api" --> api["service<br/>FastAPI, REST + SSE"]
        api --> db[("postgres<br/>PostgreSQL 16 + pgvector")]
        api --> store[("file_storage<br/>originals + extraction records")]
        worker["index-worker<br/>same image as service"] --> db
        worker --> store
        api --> emb["embeddings<br/>TEI, bge-small-en-v1.5"]
        worker --> emb
        api --> rr["reranker<br/>TEI, ms-marco-MiniLM-L6-v2"]
        api --> llm["llama<br/>llama.cpp, Gemma 4 E4B"]
    end
    subgraph outside["Outside the machine, optional"]
        exa["Exa web search<br/>(opt-in per question)"]
        hosted["OpenAI-compatible<br/>hosted model"]
        gdrive["Google Drive API"]
        smtp["SMTP server"]
    end
    api -. "only when configured" .-> outside
```

*Figure: Components. Everything in the upper box runs on one machine; the services below are used only when configured.*

| Component | Responsibility |
|-----------|----------------|
| nginx proxy | Single entry point; `/` to the web client, `/api/` to the service; long timeouts for streamed answers |
| webclient | Sign-in, invitations, chat, knowledge library, account settings, admin users, audit log and provider settings |
| service | Authentication and roles, files, Google Drive import, search, chat, audit log, provider settings |
| index-worker | Claims indexing jobs, extracts text, chunks, embeds and activates a new chunk set |
| postgres | Users, invitations, files, jobs, chunk sets, chunks with 384-dimension vectors, conversations, messages, audit events, settings |
| embeddings | Turns chunks and questions into vectors |
| reranker | Scores the 20 best candidates against the question |
| llama | Generates answers; optional because any OpenAI-compatible endpoint can replace it |

## Use cases

```mermaid
flowchart LR
    staff((Staff))
    senior((Senior))
    admin((Admin))
    subgraph PEKA
        uc1([Sign in and manage own account])
        uc2([Ask a question and read cited answer])
        uc3([Open a cited source])
        uc4([Upload or import general documents])
        uc5([Read confidential documents in answers])
        uc6([Upload confidential documents and set access levels])
        uc7([Invite users, change roles, deactivate])
        uc8([Configure model and web search providers])
        uc9([Read the audit log])
        uc10([Retry or delete documents])
    end
    staff --> uc1 & uc2 & uc3 & uc4
    senior --> uc1 & uc2 & uc3 & uc4 & uc5
    admin --> uc1 & uc2 & uc3 & uc4 & uc5 & uc6 & uc7 & uc8 & uc9 & uc10
```

*Figure: Use cases by role. Staff and senior users can also retry or delete documents they uploaded.*

## Data model

```mermaid
erDiagram
    users ||--o{ files : "author_id"
    users ||--o{ invitations : "invited_by"
    users ||--o{ conversations : "owner_id"
    users ||--o{ audit_events : "actor_id"
    users ||--o| google_drive_connections : "user_id"
    files ||--|| index_jobs : "file_id"
    files ||--o{ chunk_sets : "file_id"
    files ||--o{ knowledge_chunks : "file_id"
    chunk_sets ||--o{ knowledge_chunks : "chunk_set_id"
    conversations ||--o{ messages : "conversation_id"

    users {
        uuid id PK
        text email UK
        text display_name
        text password_hash
        text role "admin | senior | staff"
        int token_version
        bool is_active
    }
    invitations {
        uuid id PK
        text email
        text role
        text token_hash "SHA-256"
        uuid invited_by FK
        timestamptz expires_at
        timestamptz accepted_at
    }
    files {
        uuid id PK
        text path
        text content_type
        text sha256 UK
        uuid author_id FK
        text access_level "general | confidential"
    }
    index_jobs {
        uuid file_id PK,FK
        text status "queued | processing | completed | failed"
        int attempts "0 to 3"
        text last_error
    }
    chunk_sets {
        uuid id PK
        uuid file_id FK
        text status "building | active | superseded"
        int chunker_version
        vector centroid
    }
    knowledge_chunks {
        uuid id PK
        uuid file_id FK
        uuid chunk_set_id FK
        text file_path
        text heading
        text content
        jsonb source_locations
        vector embedding "384"
        tsvector search_words
    }
    conversations {
        uuid id PK
        uuid owner_id FK
        text title
    }
    messages {
        uuid id PK
        uuid conversation_id FK
        int sequence
        text role "user | assistant"
        text content
        bool refused
        jsonb citations
        text status
    }
    audit_events {
        uuid id PK
        text type "sync | query | system"
        uuid actor_id FK
        text summary
        jsonb metadata
    }
    google_drive_connections {
        uuid user_id PK,FK
        text refresh_token
    }
    provider_settings {
        smallint id PK "always 1"
        jsonb value
    }
```

*Figure: Entity-relationship diagram (11 tables, migrations 002 to 024). Timestamps are left out.*

Constraints that carry business rules:

| Constraint | Rule |
|------------|------|
| `users.role` `CHECK` | Only `admin`, `senior` or `staff` |
| `files.access_level` `CHECK` | Only `general` or `confidential` |
| `files.sha256` unique | The same content cannot be uploaded twice (FR14) |
| `index_jobs.file_id` primary key | One indexing job per file |
| `chunk_sets.status` `CHECK` | `building`, `active` or `superseded`; only active sets are searched |
| `provider_settings.id = 1` | A single settings row |
| `ON DELETE CASCADE` from files, users and conversations | Deleting a file removes its job, sets and chunks; deleting a conversation removes its messages |
| Trigger from migration 024 | A superseded chunk kept for an old citation is deleted with the last message citing it |

The full column list and every migration are in [Data model](../service/data-model.md).

## Upload and indexing

```mermaid
sequenceDiagram
    actor U as User
    participant W as Web client
    participant A as Service
    participant D as PostgreSQL
    participant X as Index worker
    participant E as Embeddings
    U->>W: Choose files and access level
    W->>A: POST /files (multipart)
    A->>A: Check type, size (25 MiB) and role
    A->>D: SHA-256 already stored?
    alt duplicate
        A-->>W: 409, nothing saved
    else new file
        A->>D: Insert file and queued index job
        A-->>W: 201, status "queued"
    end
    loop every few seconds
        X->>D: Claim next job (FOR UPDATE SKIP LOCKED)
    end
    X->>X: Extract text with locations, chunk by headings and tables
    X->>E: Embed chunks
    alt success
        X->>D: Write chunks into a new set, activate it, supersede the old one
        X->>D: Job completed, audit "sync_completed"
    else failure
        X->>D: Keep old set, record error, retry up to 3 attempts
    end
    W->>A: Poll index status
    A-->>W: queued, processing, completed or failed
```

*Figure: Upload and indexing sequence.*

## Chat sequence

```mermaid
sequenceDiagram
    actor U as User
    participant W as Web client
    participant A as Service
    participant E as Embeddings
    participant D as PostgreSQL
    participant R as Reranker
    participant L as Language model
    U->>W: Ask a question
    W->>A: POST /chat/stream
    A->>A: Validate (1 to 4,000 characters), check token and role
    A->>A: Wait for a free model slot (2 at a time)
    opt follow-up question, or web search on
        A->>L: Rewrite the search query
    end
    A->>E: Embed the query
    A->>D: Vector and keyword search, filtered by the role's access levels
    A->>R: Rerank 20 candidates
    A->>A: Keep the top 5
    alt no results and a question about a private fact
        A-->>W: Fixed reply, refused = true, no citations
    else results found
        A->>L: Question, recent history and 5 sources
        L-->>A: Answer blocks with source ids
        A->>A: Add [n] markers and citations from the search results
        A-->>W: Stream text, then the citations
    end
    A->>D: Save both messages and an audit event
```

*Figure: Chat sequence. Details and the weak-evidence path are in [Chat and RAG](../architecture/chat-and-rag.md).*

## Answer decision flow

```mermaid
flowchart TD
    q[Question] --> v{Valid length?}
    v -- no --> e422[422 error]
    v -- yes --> s[Search the knowledge base<br/>filtered by role]
    s --> r{Results?}
    r -- none --> c1{Needs a private fact?}
    c1 -- yes --> ref[Fixed reply naming the closest documents<br/>refused = true]
    c1 -- no --> gen[Answer model]
    r -- weak --> c2{Needs a private fact?}
    c2 -- yes --> strict[Answer only from a result that states it]
    strict --> cited{Answer cites a source?}
    cited -- yes --> out[Answer with citations]
    cited -- no --> ref
    c2 -- no --> gen
    r -- strong --> gen
    gen --> att[Server attaches citations<br/>or matches them with the reranker]
    att --> out
```

*Figure: How PEKA decides to answer or decline. "Weak" means the top rerank score is below `SEARCH_EVIDENCE_FLOOR`.*

## Deployment

```mermaid
flowchart TB
    subgraph host["One Linux machine (16 GB RAM, NVIDIA GPU with 6 GB VRAM)"]
        subgraph compose["Docker Compose project"]
            proxy["proxy (nginx)<br/>port 3000"]
            web[webclient]
            api[service]
            worker[index-worker]
            pg[(postgres)]
            emb[embeddings]
            rr[reranker]
            llama["llama (GPU)<br/>127.0.0.1:8080"]
        end
        vols[("Volumes: postgres_data,<br/>file_storage, embedding_models")]
        model["config/model/*.gguf<br/>(4.2 GB)"]
    end
    lan([Users on the LAN]) --> proxy
    pg --- vols
    emb --- vols
    llama --- model
```

*Figure: Deployment on one machine. Only the proxy is reachable from other machines.*

The same Compose file runs in development (`make setup`, `make up`, with hot reload) and production style (`make prod-up`). See [System requirements](../system-requirements.md) and [Config](../config/README.md).

## API

All endpoints are listed in the [API reference](../service/api-reference.md). The main groups:

| Group | Prefix | Used by |
|-------|--------|---------|
| Authentication, users, invitations | `/auth` | All users; user management is admin-only |
| Files | `/files` | All users; confidential uploads and access levels are admin-only |
| Google Drive import | `/integrations/google` | All users |
| Search | `/search` | All users |
| Chat | `/chat` | All users; conversations are owner-only |
| Audit log | `/admin/audit-events` | Admin |
| Provider settings | `/admin/settings/providers` | Admin |
| Health | `/health` | Public |
| Online status and configured features | `/status` | All users |

The web client talks only to the API through nginx; it has no database access. The service talks to the embedding, reranking and language model servers through their OpenAI-compatible or TEI HTTP APIs.
