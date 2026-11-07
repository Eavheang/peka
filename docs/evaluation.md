# Answer-quality evaluation

A repeatable check of how well PEKA answers questions about the indexed documents. It asks PEKA questions with known answers and scores each reply: a deterministic retrieval check, plus either a human-style grade of each answer or [RAGAS](https://docs.ragas.io/) (an open-source RAG evaluation library).

The scripts, question sets, test documents and raw results are kept in a local `eval/` folder that is not published in this repository. This page records the method and results.

Recall@5, latency and concurrent-user results are in the [final report](final-report.md).

## What is measured

| Metric | Question it answers | How |
|--------|---------------------|-----|
| `doc_hit` | Did PEKA cite the right document? | At least one citation's title matches the expected file. Deterministic, no LLM. |
| `heading_hit` | Did PEKA cite the right section? | At least one citation matches the expected file **and** heading. Deterministic, no LLM. |
| `faithfulness` | Is the answer backed by the passages it cites? | RAGAS splits the answer into claims and asks a judge LLM whether each claim follows from the cited passages. Score = supported claims / all claims. |
| `context_recall` | Do the cited passages contain what the reference answer needs? | RAGAS checks each claim of the reference answer against the cited passages. |
| `context_precision` | Are the cited passages relevant, with the relevant ones first? | RAGAS judges each cited passage against the reference answer, rank-weighted. |
| `correct` | Does the answer match the reference? | Graded by hand: 1, 0.5 (partly right) or 0. |
| `grounded` | Is every claim backed by a cited passage? | Graded by hand: 0 if the answer adds unsupported claims or cites nothing. |
| `abstained` | Did PEKA decline an unanswerable question? | 1 when PEKA cites nothing. Deterministic. |

When PEKA cites nothing, the RAGAS metrics are scored 0 for that question: nothing backs the answer and nothing relevant was found.

## From OKF pages to original text

PEKA first indexed Open Knowledge Format (OKF) pages. The idea was that an LLM could turn a long document into one clear page, and that chunks of those pages would give better answers than chunks of the raw text. Testing did not show that, so PEKA now indexes each document's original text and the OKF conversion has been removed.

| Date | What was indexed | Questions | Answers | Retrieval |
|------|------------------|-----------|---------|-----------|
| 2026-10-27, run A | 70 files, OKF pages written by a cloud model | 74 | `correct` 0.772 | `heading_hit` 0.647 |
| 2026-10-27, run B | 70 files, OKF pages written by the local model | 74 | `correct` 0.544 | `heading_hit` 0.147 |
| 2026-10-28 | OKF pages, after the chunker and prompt changes listed below | Set 2, 67 | 59 of 59 correct | Answer passage first 49.2%, top 5 91.5% |
| 2026-11-07 | Original text, with reranking | Set 2, 67 | 58 of 59 correct | Answer passage first 88.1%, top 5 94.9% |
| 2026-11-07, final | Original text, with prompt limits and refusal | Set 2, 67 | 57 of 59 correct, 1 partly, 1 wrongly declined | See [final report](final-report.md) |

What the testing found:

- **OKF pages did not produce better answers.** On set 2, the OKF run and the first original-text run differ by one question out of 59, which is too small to favor either.
- **Page quality depended on the model.** With a cloud model, 77.2% of answers were correct. With the local model, 54.4% were, because its pages split into a few long chunks and facts late in a document were no longer found. Chunk counts also differed between the two runs (519 and 372).
- **Conversion was fragile.** Copies of a report overwrote each other's pages, so 70 files produced 31 pages until that was fixed, and long replies were cut off and failed as invalid JSON until the output limit was raised.
- **Conversion competed with chat.** It sent each whole document to the model that serves chat. With 10 users, 2 of 20 chats were answered with no queue, and 4 of 20 while indexing once a queue was added. With the model out of indexing, 20 of 20 were answered. See [How this changed](final-report.md#how-this-changed).
- **The right passage ranked higher on original text.** It came first for 88.1% of answerable questions, up from 49.2%.

These runs were not a controlled comparison. Reranking, table chunks and other changes arrived together with original-text indexing, so the retrieval gain cannot be credited to original text alone. Run A and run B used a different question set from the later runs. Each set was graded by one person, and the set 2 questions follow the source wording and name their document, which flatters retrieval. The results do not show that OKF makes answers worse. They show that it added cost and failures on the local model without a measurable gain in answers.

Broad questions, such as summarizing or comparing whole documents, were barely tested. Summaries might still help those, as a way to find documents while answering from original text, but that has not been tried.

## Question set 2 on OKF pages (2026-10-28)

67 questions (59 answerable, 8 unanswerable) in `question-2.json` over a 70-file corpus (docx, pdf, pptx, xlsx, md, txt). PEKA answered with the local `gemma-4-E4B-it-qat-UD-Q4_K_XL` model (llama.cpp), embeddings came from `BAAI/bge-small-en-v1.5` (local TEI), and the user was an admin. All 67 were graded by hand against the `reference` field; RAGAS `score` was not run (no judge credentials, and `question-2.json` has no `heading` field, which `score` needs).

| Metric | Result |
|--------|--------|
| `correct` (answerable) | **59/59** |
| Unanswerable questions correctly declined | **8/8** |
| Answers with no citations | 9 (7 of the 8 unanswerable, plus Q2 and Q23) |
| `refused` set to `true` | 0 |

The set has 31 questions on the Mekong Harvest Foods documents, 28 metric-table lookups and 8 unanswerable ones. It was graded in a single pass by one grader, and the questions follow the source wording and name their document, which flatters retrieval.

Changes in the stack for this run, compared with the earlier runs below:

- `SEARCH_TOP_K` raised from 5 to 10.
- The chunker splits on `##` as well as `#`.
- The chat system prompt tells the model to put every sourced fact in a grounded block, read tables carefully, answer only what was asked, and say plainly when the documents do not contain the answer.
- The model sees 3000 characters of each source instead of 1200.

Remaining problems:

- **Q2 and Q23 are correct but uncited**, so nothing backs them. RAGAS faithfulness and recall would score them 0.
- **Q60 declines correctly but still cites a document** (the handbook). The `abstained` metric requires no citations, so it would score 0 and the unanswerable set would read 7/8.
- **Unrequested detail**: Q14 lists payment terms for four other suppliers, and Q29 hedges with "likely".
- **`refused` is never `true`**, even on correct "I do not have information" replies. The server has since started refusing when no passage matches; see [No-evidence refusal](final-report.md#no-evidence-refusal-101).
- **Citations were not checked against the answers.** Correctness is judged on the answer text alone.

## Earlier runs

| Date | Corpus | Questions | Result |
|------|--------|-----------|--------|
| 2026-10-21 | 2 documents, 22 chunks; PEKA answered with a cloud Gemma model, judged by RAGAS | 20 | `doc_hit`, `heading_hit`, `context_recall` and `context_precision` 0.950, `faithfulness` 0.943 |
| 2026-10-27, run A | 70 files, 519 chunks, built by a cloud model, answered locally | 74 (6 unanswerable) | `correct` 0.772, `doc_hit` 0.853, `heading_hit` 0.647 |
| 2026-10-27, run B | 70 files, 372 chunks, built by the local model, answered locally | 74 | `correct` 0.544, `doc_hit` 0.676, `heading_hit` 0.147 |
| 2026-11-07 | 70 files, 682 chunks of original text with no LLM, reranked, answered locally | 67 from set 2 (8 unanswerable), graded by reading each answer against its reference | 58 of 59 correct, 8 of 8 declined. Document in the top 5: 98.3%. Passage with the answer: 94.9% in the top 5, 88.1% first (49.2% first and 91.5% in the top 5 on the OKF-page index) |
| 2026-11-07, final | Same, on the code with the prompt limits and refusal | Same 67 | 57 of 59 correct, 1 partly (Q29), 1 wrongly declined (Q31). 8 of 8 declined: 1 refused by the server (Q66), 7 in words |

What those runs found:

- **A small model writes worse OKF pages, and that hurt run B.** It put most documents under one `# Title` with `##` subsections. The chunker then split only on `#`, so each file became 1 to 3 chunks of about 2,200 characters, longer than `bge-small`'s 512-token input, and facts late in a document stopped being found. Splitting on `##` too fixed most of it.
- **OKF pages overwrote each other (fixed).** The docx, pdf, pptx, xlsx and txt copies of one report all wrote the same page name, so 70 files produced 31 pages. Pages later ended with the first 8 characters of the source ID.
- **Metric-table questions fail most.** Narrative chunks repeat the metric names, so they outrank the table that holds the numbers, and PEKA correctly says the numbers are not in what it found.
- **Formats disagree.** The same report in different formats has different numbers, so answers that pull from several formats list conflicting figures. Wrong owners were also taken from a document header when the metrics table was missing.
- **Questions that do not name their subject can skip search.** In the 2-document run, "Which embedding model does PEKA use?" was read as a question about the assistant, and "How many cooperative clusters are farmers organized into?" was answered from general knowledge. Chunks also rarely name the document they belong to.
- **The judge must see title and heading.** A citation shows the title, heading and passage, so the judge is given the same. With the passage alone, faithfulness was 0.783 instead of 0.943 because correct answers about "the farmers" could not be tied to a company.
- **Unanswerable questions were declined 6/6** in both 70-file runs.

## How to improve accuracy

Ordered by expected gain. These runs predate source-text indexing, which now covers items 2, 3 (a repeated heading no longer hides a chunk), 5 (search keeps one format per document), and 6. OKF conversion has since been removed. The 2026-11-07 run above uses them. `heading_hit` compares exact headings, and `questions.jsonl` holds OKF-page headings, so its `heading` values also need updating: PDF chunks are now named `Page N`.

1. **No longer applies: use a larger model for OKF conversion.** A larger model gave far better page structure (run A), but OKF conversion has been removed.
2. **Keep metric tables as their own chunk and include the row labels with the numbers.** A chunk like "Metrics table, Rate Limits: baseline 47%, target 82%, owner Finance Group" matches "who owns rate limits" much better than a markdown table under a generic heading.
3. **Make headings unique within a page.** Two sections with the same heading hid a delivery calendar.
4. **Reject or retry answers with no citations,** and set `refused` when the answer says the information is not available. The server now refuses when no passage matches. A reply the model declines in words still has `refused: false`.
5. **Deduplicate formats at upload or rank one format per topic,** so answers stop mixing conflicting figures from copies of the same report.
6. **Cap chunk length below the embedding model's 512 tokens.** The chunker allows 3,000 characters.

Already in the code: splitting on every Markdown heading level, the file name and heading in each embedded chunk, and hybrid keyword plus vector search.

## Running it

These commands need the local `eval/` folder, which is not in this repository. They are recorded to show the method. The stack must be running (`make up` in `config/`).

```bash
cd eval
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

export PEKA_URL=http://localhost:8000          # default
export PEKA_EMAIL=... PEKA_PASSWORD=...        # an account that can see the documents
export JUDGE_BASE_URL=https://openrouter.ai/api/v1 JUDGE_API_KEY=... JUDGE_MODEL=minimax/minimax-m3.1-flash:free

.venv/bin/python ragas_eval.py          # ask + score; or pass `ask` / `score` alone
```

- `ask` sends each question to `POST /chat`, fetches each cited passage via `POST /chat/source-preview`, and deletes the conversation so chat history stays clean. Output: `results/answers.jsonl`.
- `score` computes the metrics. Output: `results/scores.jsonl`.
- Both steps skip questions already in their output file. A failure (for example a free-tier `503` or a judge timeout) is printed and the question is retried on the next run.
- To re-run from scratch, delete `results/`. To re-score only, delete `results/scores.jsonl`.
- `QUESTIONS` (default `question-2.json`) and `RESULTS_DIR` (default `results`) select another question file and output directory. A `.json` question file is a JSON array; `.jsonl` is one object per line.
- `score` needs `file` to be a single file name and `heading` on every answerable question, so it works on `questions.jsonl` but not on `question-2.json` as it stands.

To add a question to `questions.jsonl`, append a line with `id`, `question`, `reference` (the correct answer), `file` (the file name as shown in citations; any format of the same file name counts) and `heading` (the chunk heading that holds the answer). For a question the documents cannot answer, set `"unanswerable": true` instead of `file` and `heading`; it scores `abstained` = 1 when PEKA cites nothing.

The set 2 results skip `score` and were graded by hand against `reference`.
