# Document indexing and optional OKF enrichment

Deep dive into how PEKA turns an uploaded file into searchable knowledge. Companion to [How it works](../how-it-works.md).

## Pipeline summary

```text
Upload bytes
  → store original (typed folder)
  → extract text + locators (JSON)
  → queue okf_jobs
  → chunk the original text (headings, pages, slides, tables, sheets)
  → embed (TEI)
  → activate chunk_set: the file is searchable, job is completed

Only when OKF_ENRICHMENT_ENABLED=true, afterwards and in the background:
  → LLM: OKF v0.2 concept Markdown
  → write knowledge_base tree + indexes
```

The default path makes no LLM call, so indexing does not compete with chat for the model. Chunks and citations are the source text, and locators come from the extractor.

Code map:

| Step | Location |
|------|----------|
| Upload / extract trigger | `app/files/service.py`, `app/engine/source_extractor.py` |
| Job queue | `app/engine/okf/job_repository.py`, `job_model.py` |
| Worker loop | `app/engine/okf/worker.py` |
| Chunk | `app/engine/chunks/chunker.py` |
| Embed | `app/engine/chunks/embeddings.py` |
| Persist / swap active | `app/engine/chunks/repository.py` |
| Optional enrichment | `app/engine/okf/converter.py`, `prompt.txt`, `file_writer.py` |

The `okf_jobs` table, `okf_status` fields, `okf-worker` service, and `retry-okf` route keep their names, but they now track indexing, not OKF conversion.

## Extraction

Supported extensions: `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.md`, `.txt`.

Extractors produce ordered **sections** with text and optional locators (`page`, `section`, `slide`, `sheet` + `name`). Output JSON under `storage/extracted/` includes `source_id`, SHA-256, filename, path, extension, timestamp, and `sections`. That JSON is the source of truth for chunking.

Two conventions in the section text let the chunker see the structure:

- Tables in DOCX, PPTX, and XLSX are pipe-delimited rows (`| Region | Sales |`), which keeps cell boundaries.
- DOCX headings are written as `# Heading`. A paragraph counts as a heading when it has a Heading style, or when it is the next number in a `1. Title` sequence.

A DOCX `section` locator is the position of its heading in the document, starting at 1. Text before the first heading is section 0.

PDF tables are not detected: they stay in the page text. PDF headings are not detected either, so PDF chunks are named after their page.

## Chunking for retrieval

`chunk_extraction` needs no model:

| Source | Chunk heading | `source_locations` |
|--------|---------------|--------------------|
| PDF page | `Page 3` | `[{"page": 3}]` |
| PPTX slide | `Slide 3` | `[{"slide": 3}]` |
| XLSX sheet | `Sheet: Q1` | `[{"sheet": 1, "name": "Q1"}]` |
| DOCX heading | The heading text | `[{"section": 2}]` |
| Markdown `#` to `######` | The heading text | `[]` |
| Text before the first heading, and `.txt` | `Text` | `[{"section": 0}]` for DOCX, otherwise `[]` |

Rules:

1. **Tables and sheets are their own chunks.** Every cell is named after its column (`| Metric: Uptime | Owner: Dana |`), so a row says what its numbers mean in any chunk; the values stay exactly as in the source. They split between rows. The widest row of a table or sheet is taken as its header, and any one-cell title rows above it stay as they are. Plain-text columns aligned under a dashed ruler count as tables. PDF tables are found with PyMuPDF's `find_tables`, which needs ruled lines; a table drawn without lines stays in the page text.
2. **Everything else splits at the coarsest boundary that fits:** paragraph, line, sentence, word, then inside an unbroken run such as a long ID.
3. **Nothing is dropped.** That includes text before the first heading and plain text with no headings. A heading with no body of its own moves into the next section's text.
4. **A heading can repeat.** All parts of a long page keep the name `Page 3`. Citations and previews find a chunk by its ID, so this hides nothing. Search keeps only the best-ranked format of a file name, so `.pdf` and `.docx` copies of one report never compete for result slots.

Embedding input string:

```text
Document: {file name without extension}
Section: {heading}

{content}
```

### Embedding window

`bge-small-en-v1.5` embeds 512 tokens. `MAX_CHUNK_TOKENS` limits the whole embedding string, header included, to 400 *estimated* tokens. The estimate is a regular expression, not the real tokenizer: a run of up to twelve letters, two digits, or any other non-space character each count as one token. On the 70-file evaluation corpus, measured with TEI `/tokenize`, this gave a median of about 300 real tokens and a maximum of 438.

The TEI image in Compose truncates longer input instead of rejecting it (`auto_truncate` in its `/info`). An underestimate, such as a chunk full of acronyms or non-English text, therefore loses the end of that chunk from the vector but does not fail the job, and keyword search still reads the whole chunk.

### Citations

`Citation.page` comes from a `{"page": N}` locator. Slide, sheet, and section locators pass through `source_locations`, and the UI shows all of them through the heading, such as `Page 3` or `Slide 2`. Chunks from before this format hold `{"type": "page", "value": N}` and cite with `page: null`.

## Embeddings and chunk sets

- Model (Compose default): `BAAI/bge-small-en-v1.5`
- Dimensions: **384** (`vector(384)` after migration `012`)
- HTTP: OpenAI-compatible `POST {EMBEDDING_BASE_URL}/embeddings`

Each re-index creates a new `chunk_sets` row (`building`), inserts chunks, then swaps so only one set per file is `active`. Search never mixes superseded vectors.

## Worker reliability

- Single serial worker (no Redis); claim via `SKIP LOCKED`
- Stuck `processing` jobs are reset to `queued` on loop
- Max **3** attempts; then `failed` with `last_error`
- An extraction with no text fails the job with `No text to index in <file>`
- API: `POST /files/{id}/retry-okf` requeues failed jobs
- Path safety: all writes resolve under `FILE_STORAGE_DIR`

Scaling note: code comments warn that org-level locking would be needed before running multiple concurrent workers safely.

## Re-indexing existing files

Files indexed before this format keep their old model-rewritten chunks until they are re-indexed. Nothing re-queues them automatically, because regenerating rewritten chunks later is expensive, so this is the owner's choice. Re-indexing deletes the old chunks, so previews of citations saved in older conversations stop working. To re-index every file from its original text:

```sql
UPDATE okf_jobs SET status = 'queued', attempts = 0, last_error = NULL, updated_at = CURRENT_TIMESTAMP
WHERE status IN ('completed', 'failed');
```

```bash
docker compose -f config/compose.yaml exec postgres psql -U peka -d peka -c "<the statement above>"
```

The old chunks stay searchable until each file's new set is active, and a job that fails keeps them. The worker reads the stored extraction JSON, so files extracted earlier keep that extraction: XLSX cell boundaries are gone, PDF, DOCX and plain-text tables stay in the surrounding text, and PPTX tables stay missing. Getting table chunks with labelled cells and unnumbered DOCX headings needs a fresh upload.

## Optional OKF enrichment

Off by default. With `OKF_ENRICHMENT_ENABLED=true`, once a file's source chunks are active and its job is `completed`, the worker queues one LLM conversion in a single background thread:

- The output goes only to `storage/knowledge_base/`. Search, citations, and chat do not read that folder, and it never replaces or adds chunks.
- A failure is logged and changes nothing: the job stays `completed` and the file stays searchable. There is no retry.
- Pending conversions live in memory, so a worker restart skips them.
- It uses the same `LLM_*` model as chat, so it competes with chat there. `OKF_MAX_TOKENS` limits its reply and is not used anywhere else.

An LLM rewrites the source into one **concept** Markdown file following the prompt in `prompt.txt`.

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

Structured JSON with `document_analysis`, `folder_structure`, and `files` (exactly one `okf_concept`).

## What “indexed” means for chat

A file is useful in RAG only when:

1. Its job is `completed`
2. An `active` chunk set exists with embeddings
3. The asking user’s role may see that file’s `access_level`

Until then, the retrieval router may still choose knowledge search, but results will simply omit that document.
