# OKF and document indexing

Deep dive into how PEKA turns an uploaded file into searchable knowledge. Companion to [How it works](../how-it-works.md).

## Pipeline summary

```text
Upload bytes
  → store original (typed folder)
  → extract text + locators (JSON)
  → queue okf_jobs
  → LLM: OKF v0.2 concept Markdown + retrieval_sections
  → write knowledge_base tree + indexes
  → chunk by H1 (+ Summary)
  → embed (TEI)
  → activate chunk_set
```

Code map:

| Step | Location |
|------|----------|
| Upload / extract trigger | `app/files/service.py`, `app/engine/source_extractor.py` |
| Job queue | `app/engine/okf/job_repository.py`, `job_model.py` |
| Worker loop | `app/engine/okf/worker.py` |
| LLM conversion | `app/engine/okf/converter.py`, `prompt.txt` |
| Write markdown | `app/engine/okf/file_writer.py` |
| Chunk | `app/engine/chunks/chunker.py` |
| Embed | `app/engine/chunks/embeddings.py` |
| Persist / swap active | `app/engine/chunks/repository.py` |

## Extraction

Supported extensions: `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.md`, `.txt`.

Extractors produce ordered **sections** with text and optional locators (`page`, `section`, `slide`, `sheet`). Output JSON under `storage/extracted/` includes `source_id`, SHA-256, filename, path, extension, timestamp, and `sections`.

That JSON is the **source of truth** for OKF conversion (filenames are supporting evidence only).

## Open Knowledge Format (OKF) v0.2

The worker does **not** embed raw PDF text directly. An LLM rewrites each source into one **concept** Markdown file following the prompt in `prompt.txt`.

### Classification

The model picks exactly one category/type, for example:

| Category folder | Type (examples) |
|-----------------|-----------------|
| `policies` | Policy Document |
| `faqs` | FAQ |
| `reports` | Report |
| `meeting-notes` | Meeting Notes |
| `procedures` | Procedure |
| `guidelines` | Guideline |
| `handbooks` | Handbook |
| `announcements` | Announcement |
| `technical-documents` | Technical Documentation |
| `documents` | General Document (fallback) |

Wording cues matter: *must/shall/required* → policy; *should/recommended* → guideline. The prompt forbids turning optional language into mandatory rules.

### Concept file shape

Path: `knowledge_base/<category>/<kebab-case-filename>.md`

YAML frontmatter includes: `type`, `title`, `description`, `resource`, source ids/hashes/filename, `tags`, `timestamp`, `summary`, `keywords`.

Body uses meaningful `#` headings (Overview, Requirements, Procedure, Findings, …). Empty sections are disallowed. Facts, dates, numbers, and obligation strength must stay faithful to the source—no invented URLs or requirements.

### Indexes

The application (not the LLM) rebuilds:

- Root `knowledge_base/index.md` — OKF version frontmatter + links to non-empty categories  
- Per-category `index.md` — links to every concept with short descriptions  

Existing entries are preserved when rebuilding; duplicates are avoided.

### LLM output contract

Structured JSON with `document_analysis`, `folder_structure`, `files` (exactly one `okf_concept`), and `retrieval_sections` (per H1: heading, anchor, pages, summary). Invalid or incomplete results fail the job.

## Chunking for retrieval

`parse_okf_chunks`:

1. Optional **Summary** chunk from frontmatter `summary` / `description`
2. One or more chunks per `#` section
3. Split long sections at **3000** characters with **200** character overlap
4. Attach page locators from `retrieval_sections` when present

Embedding input string:

```text
Document: {title}
Section: {heading}

{content}
```

## Embeddings and chunk sets

- Model (Compose default): `BAAI/bge-small-en-v1.5`
- Dimensions: **384** (`vector(384)` after migration `012`)
- HTTP: OpenAI-compatible `POST {EMBEDDING_BASE_URL}/embeddings`

Each re-index creates a new `chunk_sets` row (`building`), inserts chunks, then swaps so only one set per file is `active`. Search never mixes superseded vectors.

## Worker reliability

- Single serial worker (no Redis); claim via `SKIP LOCKED`
- Stuck `processing` jobs are reset to `queued` on loop
- Max **3** attempts; then `failed` with `last_error`
- API: `POST /files/{id}/retry-okf` requeues failed jobs
- Path safety: all writes resolve under `FILE_STORAGE_DIR`

Scaling note: code comments warn that org-level locking would be needed before running multiple concurrent workers safely.

## What “indexed” means for chat

A file is useful in RAG only when:

1. OKF job is `completed`
2. An `active` chunk set exists with embeddings
3. The asking user’s role may see that file’s `access_level`

Until then, the retrieval router may still choose knowledge search, but results will simply omit that document.
