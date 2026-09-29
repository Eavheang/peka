# Data model and storage

## Database tables

Postgres with the `vector` extension (pgvector). Schema is owned by Alembic; do not create tables from FastAPI startup.

| Table | Purpose |
|-------|---------|
| `users` | Email (unique, lowercased), `display_name`, `password_hash`, `role`, `token_version`, `is_active`, timestamps |
| `invitations` | Pending and accepted invites: `email`, `role`, `token_hash` (SHA-256; the token itself is never stored), `invited_by`, `expires_at`, `accepted_at`. One pending invite per address |
| `files` | Relative `path`, `content_type`, unique `sha256`, `author_id`, `access_level` (`general` \| `confidential`) |
| `okf_jobs` | PK `file_id` → files; `status` (`queued` \| `processing` \| `completed` \| `failed`); `attempts` 0–3; `last_error` |
| `chunk_sets` | Per-file index generations: `building` \| `active` \| `superseded` |
| `knowledge_chunks` | `heading`, `content`, `source_locations` JSONB, `embedding vector(384)`, FKs to file + chunk_set |
| `conversations` | Owned chat threads (`owner_id`, title, timestamps) |
| `messages` | `role` `user` \| `assistant`; content; citations JSONB |
| `provider_settings` | Single row `id=1`, JSONB `value` for LLM/Exa overrides |

Conversation list uses index `(owner_id, updated_at DESC, id DESC)` for cursor pagination.

## Alembic revision chain

| Revision | Change |
|----------|--------|
| `002_create_users` | users |
| `003_create_files` | files |
| `004_add_user_activation` | `is_active` |
| `005` / `006` | sha256 column + uniqueness |
| `007_create_okf_jobs` | job queue |
| `008_create_knowledge_chunks` | pgvector + chunks (originally 1024-d) |
| `009_migrate_user_roles` | roles → `admin` / `senior` / `staff` |
| `010_add_file_access_level` | `general` / `confidential` |
| `011_create_chunk_sets` | chunk set versioning |
| `012_resize_embeddings` | clear chunks; `vector(384)` for bge-small |
| `013_create_chat_tables` | conversations / messages |
| `014_…pagination…` | conversation list index |
| `015_create_provider_settings` | provider_settings |
| `016_add_user_display_name` | `display_name` |
| `017_create_invitations` | invitations |

Apply:

```bash
cd config && make migrate
# → alembic upgrade head inside the service container
```

Create after model changes (from `service/`):

```bash
alembic revision --autogenerate -m "describe schema change"
```

## On-disk storage (`FILE_STORAGE_DIR`, default `storage/`)

```text
storage/
├── pdf/ | docx/ | pptx/ | xlsx/ | others/   # original uploads
├── extracted/
│   └── {16-char-source-id}.json            # extraction records
└── knowledge_base/
    ├── index.md
    └── <category>/
        ├── index.md
        └── <concept>.md                    # OKF markdown
```

Compose mounts a named volume `file_storage` at `/app/storage` for both `service` and `okf-worker`.

## Embedding dimensions

Current production path uses **384-d** vectors with `BAAI/bge-small-en-v1.5` (see migration `012` and Compose TEI service). Older docs mentioning BGE-M3 / 1024-d are outdated relative to the code.
