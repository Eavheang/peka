# Document indexing

Deep dive into how PEKA turns an uploaded file into searchable knowledge. Companion to [How it works](../how-it-works.md).

## Pipeline summary

```text
Upload bytes
  → store original (typed folder)
  → extract text + locators (JSON)
  → queue index_jobs
  → chunk the original text (headings, pages, slides, tables, sheets)
  → embed (TEI)
  → activate chunk_set: the file is searchable, job is completed
```

Indexing makes no LLM call, so it does not compete with chat for the model. Chunks and citations are the source text, and locators come from the extractor.

Code map:

| Step | Location |
|------|----------|
| Upload / extract trigger | `app/files/service.py`, `app/engine/source_extractor.py` |
| Job queue | `app/engine/indexing/job_repository.py`, `job_model.py` |
| Worker loop | `app/engine/indexing/worker.py` |
| Chunk | `app/engine/chunks/chunker.py` |
| Embed | `app/engine/chunks/embeddings.py` |
| Persist / swap active | `app/engine/chunks/repository.py` |

## Extraction

Supported extensions: `.pdf`, `.docx`, `.pptx`, `.xlsx`, `.md`, `.txt`.

Extractors produce ordered **sections** with text and optional locators (`page`, `section`, `slide`, `sheet` + `name`). Output JSON under `storage/extracted/` includes `source_id`, SHA-256, filename, path, extension, timestamp, and `sections`. That JSON is the source of truth for chunking.

Two conventions in the section text let the chunker see the structure:

- Tables in DOCX, PPTX, XLSX, and PDF are pipe-delimited rows (`| Region | Sales |`), which keeps cell boundaries.
- DOCX headings are written as `# Heading`. A paragraph counts as a heading when it has a Heading style, or when it is the next number in a `1. Title` sequence.
- PDF headings are written the same way when a whole line is bold and has the `1. Title` form. Bold keeps out numbered list items and table-of-contents lines, which are usually set in body text. Lines over 100 characters do not count. A section that runs onto the next page keeps its heading there.

A DOCX `section` locator is the position of its heading in the document, starting at 1. Text before the first heading is section 0.

PDF tables are found with PyMuPDF's `find_tables`. Each table is placed under the text above it, top to bottom, with blank lines around it, so two tables on one page keep their own column names. Two-column pages read top to bottom, so their paragraphs interleave. A PDF without numbered sections keeps chunks named after their page.

## Chunking for retrieval

`chunk_extraction` needs no model:

| Source | Chunk heading | `source_locations` |
|--------|---------------|--------------------|
| PDF numbered section | The heading text, such as `6. Spokespeople` | `[{"page": 3}]` |
| PDF page without one | `Page 3` | `[{"page": 3}]` |
| PPTX slide, including text inside grouped shapes | `Slide 3` | `[{"slide": 3}]` |
| PPTX speaker notes | `Slide 3 notes` | `[{"slide": 3, "part": "notes"}]` |
| XLSX sheet | `Sheet: Q1` | `[{"sheet": 1, "name": "Q1"}]` |
| DOCX heading | The heading text | `[{"section": 2}]` |
| DOCX footnotes | `Footnotes` | `[{"part": "footnotes"}]` |
| DOCX headers and footers, each distinct one once | `Headers and footers` | `[{"part": "headers and footers"}]` |
| Markdown `#` to `######` | The heading text | `[]` |
| Text before the first heading, and `.txt` | `Text` | `[{"section": 0}]` for DOCX, otherwise `[]` |

Rules:

1. **Tables and sheets are their own chunks.** Every cell is named after its column (`| Metric: Uptime | Owner: Dana |`), so a row says what its numbers mean in any chunk; the values stay exactly as in the source. They split between rows. The widest row of a table or sheet is taken as its header. One-cell title rows above it (units, "Q4 is a forecast", a total budget) are repeated at the top of every part, unless they take more than half the part's room. A short line just above a table, such as `Revenue by Quarter (FY2025)`, becomes its first title row. Plain-text columns aligned under a dashed ruler count as tables. PDF tables are found with PyMuPDF's `find_tables`, which needs ruled lines; a table drawn without lines stays in the page text.
2. **Everything else splits at the coarsest boundary that fits:** paragraph, line, sentence, word, then inside an unbroken run such as a long ID.
3. **Nothing is dropped.** That includes text before the first heading and plain text with no headings. A heading with no body of its own moves into the next section's text.
4. **A heading can repeat.** All parts of a long page keep the name `Page 3`. Citations and previews find a chunk by its ID, so this hides nothing. Search keeps only the best-ranked format of a file name, so `.pdf` and `.docx` copies of one report never compete for result slots.

Not extracted: DOCX endnotes, text boxes and comments; PPTX charts, SmartArt and alt text; text in images (there is no OCR). Footnotes and headers or footers are cited by part only, without a page or footnote number.

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

The swap deletes the superseded set's chunks except those a saved answer cites, so older citations still open their source preview. A trigger on `messages` deletes a kept chunk once the last message citing it is deleted.

## Worker reliability

- Single serial worker (no Redis); claim via `SKIP LOCKED`
- Stuck `processing` jobs are reset to `queued` on loop
- Max **3** attempts; then `failed` with `last_error`
- An extraction with no text fails the job with `No text to index in <file>`
- API: `POST /files/{id}/retry-indexing` requeues failed jobs
- Path safety: all writes resolve under `FILE_STORAGE_DIR`

Scaling note: code comments warn that org-level locking would be needed before running multiple concurrent workers safely.

## Re-indexing existing files

Each chunk set records the `chunker_version` that built it (`CHUNKER_VERSION` in `chunker.py`). When the index worker starts, it re-queues every file whose active set an older chunker built, whatever the state of its job. Bump `CHUNKER_VERSION` whenever chunk output changes.

Migration `023` gives every existing chunk set version 0, so **the first deploy with it re-indexes every file once**. That is intended: it moves files still on model-rewritten chunks onto the original text.

Re-indexing keeps the chunks that saved answers cite, so citations in older conversations still open their source preview. Kept chunks stay in their superseded set, which search never reads, and the preview still checks the file's current access level. Citations already broken by a re-index before this change stay broken.

To re-index every file now, without changing the version:

```sql
UPDATE index_jobs SET status = 'queued', attempts = 0, last_error = NULL, updated_at = CURRENT_TIMESTAMP
WHERE status IN ('completed', 'failed');
```

```bash
docker compose -f config/compose.yaml exec postgres psql -U peka -d peka -c "<the statement above>"
```

The old chunks stay searchable until each file's new set is active, and a job that fails keeps them. The worker reads the stored extraction JSON, and reads the original file again when an older extractor wrote it (`EXTRACTOR_VERSION` in `source_extractor.py`). Bump it together with `CHUNKER_VERSION` when extracted text changes, so stored files are re-extracted as well as re-chunked. Version 3 (2026-11-12) did this for PDF tables placed under their sections, bold numbered PDF headings, and table title rows repeated in every part.

## History: OKF pages

PEKA first indexed LLM-written Open Knowledge Format (OKF) pages. Testing found no measurable gain in answers, and conversion caused failures under load on the local model, so indexing moved to the original text and the conversion was removed. See [From OKF pages to original text](../evaluation.md#from-okf-pages-to-original-text). Older results and migration `007_create_okf_jobs` still use the old name.

## What “indexed” means for chat

A file is useful in RAG only when:

1. Its job is `completed`
2. An `active` chunk set exists with embeddings
3. The asking user’s role may see that file’s `access_level`

Until then, the retrieval router may still choose knowledge search, but results will simply omit that document.
