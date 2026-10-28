# Answer-quality evaluation

A repeatable check of how well PEKA answers questions about the indexed documents. It asks PEKA questions with known answers and scores each reply: a deterministic retrieval check, plus either a human-style grade of each answer or [RAGAS](https://docs.ragas.io/) (an open-source RAG evaluation library).

This lives in [`eval/`](../eval/) as a standalone script. It is not part of the app and has its own dependencies.

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

When PEKA cites nothing, the RAGAS metrics are scored 0 for that question for that question: nothing backs the answer and nothing relevant was found.

## Results: 70-file corpus (2026-10-27)

74 questions (68 answerable, 6 unanswerable) over the 70 files in `service/storage/` (docx, pdf, pptx, xlsx, md, txt). Each answer was graded by hand by Claude (Opus 5.5) acting as judge, reading the answer, the reference and the cited passages. RAGAS was not run.

| Metric | Run A | Run B |
|--------|-------|-------|
| `correct` (answer matches reference; 0.5 = partly) | **0.772** | **0.544** |
| `doc_hit` | 0.853 | 0.676 |
| `heading_hit` | 0.647 | 0.147 |
| `grounded` (no claim beyond the cited passages, answer has citations) | 0.956 | 0.941 |
| Unanswerable questions correctly declined | 6/6 | 6/6 |
| Answerable questions with no citations | 10 | 21 |

- **Run A**: knowledge base built by `google/gemma-4-26b-a4b-it:free` (OpenRouter), 519 chunks. Pages overwrote each other (see below): 31 pages for 70 files.
- **Run B**: knowledge base rebuilt with the overwrite fix by the local `gemma-4-E4B-it-qat-UD-Q4_K_XL` (llama.cpp), 372 chunks, 70 pages.

In both runs PEKA answered with the local gemma-4-E4B model. Per-question grades for run B are in [`eval/results/claude_judge.jsonl`](../eval/results/claude_judge.jsonl), replies in [`eval/results/answers.jsonl`](../eval/results/answers.jsonl).

### Setup

| Item | Value |
|------|-------|
| Corpus | 70 files: about 30 topics, most in several formats with differing content |
| Questions | 74, in [`eval/questions.jsonl`](../eval/questions.jsonl). Drafted by AI assistants from the knowledge base; every reference fact was checked against the indexed chunks |
| User role | Admin |
| PEKA's model | `gemma-4-E4B-it-qat-UD-Q4_K_XL` via local llama.cpp |
| Embeddings | `BAAI/bge-small-en-v1.5` (local TEI) |
| Judge | Claude (Opus 5.5), manual grading |

### Findings

- **Run B is worse because the local model writes worse OKF pages, not because of the overwrite fix.** The small model put most documents under one `# Title` with `##` subsections. The chunker splits only on `#`, so each file became 1 to 3 chunks of about 2,200 characters, all headed with the document title. That is longer than `bge-small`'s 512-token input, so the end of each chunk is never embedded. Facts that live late in a document (handbook leave rules, meeting decisions, metric tables) stopped being found: answerable questions with no citations went from 10 to 21. `heading_hit` collapsed because the expected section headings no longer exist.
- **OKF pages overwrote each other (fixed).** The LLM picks a page's filename from its title, so the docx, pdf, pptx, xlsx and txt copies of one report all wrote the same `knowledge_base/<category>/<name>.md`, and the last one won. 70 files produced 31 pages. Pages now end with the first 8 characters of the source ID (`data-retention-policy-b6419b61.md`). Search was not affected: chunks are stored per file.
- **Metric-table questions fail most.** Most misses ask for a metric's baseline, target or owner. The narrative chunks repeat the metric names many times ("A clear owner for rate limits reduces delays…"), so they outrank the table that holds the numbers. PEKA then correctly says the numbers are not in what it found (run A: Q27, 28, 34, 43, 49, 69, 71).
- **Formats disagree.** The same report in different formats has different numbers (battery storage "moved by 13, 4 or 14 percent" in Q59). Answers that pull from several formats list conflicting figures.
- **Wrong-owner answers.** When the metrics table is missing, the model sometimes takes the document's owner from its header and presents it as the metric's owner (run B: Q12, Q72), or invents positioning text (Q53 in both runs).
- **Correct answers without citations.** Run A Q37, run B Q28: right answer, empty citation list.
- **`refused` is never `true`.** It stayed `false` on all six correct "I do not have information" replies.
- **Unanswerable questions: 6/6 in both runs.** PEKA did not make up allowances, emissions figures or audit dates.

### How to improve accuracy

Ordered by expected gain, with the questions each would fix.

1. **Split chunks on `##` too, and cap chunk length below the embedding model's 512 tokens.** Fixes run B's regression regardless of how the OKF model nests headings (Q1, 5, 6, 9, 10, 22, 52 and most metric questions). Alternatively, tell the OKF prompt to use `#` for sections and validate it.
2. **Use the larger model for OKF conversion.** Conversion runs once per file, so a slower or paid model costs little and gave far better page structure (run A). Answering can stay local.
3. **Keep metric tables as their own chunk and include the row labels with the numbers.** A chunk like "Metrics table, Rate Limits: baseline 47%, target 82%, owner Finance Group" matches "who owns rate limits" much better than a markdown table under a generic heading (12 of the 15 misses in run A).
4. **Add the document title to each chunk before embedding** (contextual chunk header). The boilerplate text never says which report it belongs to, so similar reports compete.
5. **Make headings unique within a page.** Two sections both called "Farmer Supply Agreement" hid the delivery calendar (Q15).
6. **Hybrid search (BM25 + vectors).** Questions with exact terms such as "QC-014", "Lotus Packaging" or "30-60-90" benefit from keyword matching.
7. **Reject or retry answers with no citations,** and set `refused` when the answer says the information is not available.
8. **Deduplicate formats at upload or rank one format per topic,** so answers stop mixing conflicting figures from copies of the same report.

### Limitations

- **Questions follow the source wording** and name their document, which flatters retrieval. Most are metric lookups because the synthetic documents are mostly boilerplate plus a metrics table.
- **One grader, one pass.** Grades are Claude's judgment, not RAGAS scores, so they are not directly comparable with the earlier run below.
- **Two things changed between runs A and B** (the overwrite fix and the OKF model). The findings above explain why the drop comes from the model, but it was not tested separately.

## Results: question set 2 (2026-10-28)

67 questions (59 answerable, 8 unanswerable) in [`eval/question-2.json`](../eval/question-2.json), re-asked after the retrieval and prompt changes listed below. Replies are in [`eval/results-2/answers.jsonl`](../eval/results-2/answers.jsonl). All 67 were graded by hand against the `reference` field; RAGAS `score` was not run (no judge credentials, and `question-2.json` has no `heading` field, which `score` needs).

| Metric | Result |
|--------|--------|
| `correct` (answerable) | **59/59** |
| Unanswerable questions correctly declined | **8/8** |
| Answers with no citations | 9 (7 of the 8 unanswerable, plus Q2 and Q23) |
| `refused` set to `true` | 0 |

Compared with the 70-file run B (`correct` 0.544), this is a large gain on a different question set. The sets are not directly comparable: question set 2 has 31 questions on the Mekong Harvest Foods documents, 28 metric-table lookups and 8 unanswerable ones, and it was graded in a single pass by one grader.

Changes in the stack for this run:

- `SEARCH_TOP_K` raised from 5 to 10.
- The chunker splits on `##` as well as `#` (improvement 1 above).
- The chat system prompt tells the model to put every sourced fact in a grounded block, read tables carefully, answer only what was asked, and say plainly when the documents do not contain the answer.
- The model sees 3000 characters of each source instead of 1200.

Remaining problems:

- **Q2 and Q23 are correct but uncited**, so nothing backs them. RAGAS faithfulness and recall would score them 0.
- **Q60 declines correctly but still cites a document** (the handbook). The `abstained` metric requires no citations, so it would score 0 and the unanswerable set would read 7/8.
- **Unrequested detail**: Q14 lists payment terms for four other suppliers, and Q29 hedges with "likely".
- **Citations were not checked against the answers.** Correctness is judged on the answer text alone.

## Earlier run: 2 documents (2026-10-21)

| Metric | Mean (n = 20) |
|--------|---------------|
| `doc_hit` | **0.950** |
| `heading_hit` | **0.950** |
| `faithfulness` | **0.943** |
| `context_recall` | **0.950** |
| `context_precision` | **0.950** |

19 of 20 questions scored 1.0 on every retrieval metric. Per-question results and replies for this run are in `eval/results/` at commit `bf6e644`.

#### Setup

| Item | Value |
|------|-------|
| Corpus | 2 documents, 22 chunks: `1_Business_Plan_MekongFreshFoods.pdf`, `B11-G03_PEKA_Review1_Document.docx` |
| Questions | 20 (10 per document), in [`eval/questions.jsonl`](../eval/questions.jsonl) |
| User role | Admin (can see every document) |
| PEKA's model | `google/gemma-4-26b-a4b-it:free` via OpenRouter (cloud mode, not the local llama.cpp model) |
| Judge model | `minimax/minimax-m3.1-flash:free` via OpenRouter |
| Embeddings | `BAAI/bge-small-en-v1.5` (local TEI) |
| RAGAS | 0.4.3 |

#### Failures and findings

- **Q12, "Which embedding model does PEKA use?": search was skipped.** PEKA's planning step chose `tool: none` and answered as if asked about the assistant itself ("I do not have access to my own internal technical specifications…"). No citations, so every metric scored 0. This is a failure in deciding whether to search, not in retrieval. Questions about "PEKA" can be read as questions about the assistant.
- **Q9, faithfulness 0.86: a small embellishment.** The answer describes redundant refrigeration as "backup cooling systems to prevent temperature fluctuations". The passage does not say that, and the judge correctly marked that claim unsupported.
- **Retrieval depends on the question naming its subject.** During setup, the question "How many cooperative clusters are farmers organized into?" (no company name) was answered from general knowledge with no search and no citations. With "Mekong Fresh Foods'" added, it was answered correctly. All 20 evaluation questions name their subject.
- **Chunks lose their document context.** Many chunks never name who they are about. For example, the "Operations Plan" chunk says "Farmers are organized into eight cooperative clusters" but never mentions Mekong Fresh Foods. See the scoring note below.

#### Scoring note: the judge sees title and heading

A PEKA citation shows the user the document title, the section heading and the passage. The judge is given the same: each passage is prefixed with `title > heading`. In an earlier run the judge got the passage text alone and faithfulness came out at **0.783**. Correct answers such as "the farmers are organized into eight cooperative clusters" (Q8) scored 0, because the passage alone does not say *whose* farmers. Removing the `[1]` citation markers from answers did not change this (0.719 on the 19 questions scored). Adding title and heading did. Retrieval metrics were the same in every run.

This also suggests a product improvement: putting the document title in each chunk before embedding (a "contextual chunk header") would help retrieval for questions that don't name their subject.

#### Limitations

- **Small, easy corpus.** With 22 chunks, finding the right passage is much easier than in the project objective's target of Recall@5 ≥ 85% over 200+ documents. These numbers do **not** validate that objective.
- **20 questions.** One question is worth 0.05 on every mean. Treat differences of a few points as noise.
- **Questions were drafted from the chunk text by an AI assistant**, not written by independent users. They name their subject and closely follow the source wording, which flatters retrieval. Questions written independently (paraphrased, vague, multi-hop, or unanswerable) would be a harder test.
- **Only cited passages are visible.** The API returns the passages PEKA cited, not everything it retrieved. "Context recall" and "precision" here mean "found **and** cited".
- **LLM judge.** Faithfulness and the context metrics come from a free "flash" judge model. Each question was scored once. The judge is strict about context it cannot see (see the scoring note above).
- **Cloud generator.** PEKA ran with a cloud Gemma model, not the local llama.cpp setup described in the design document.

## Running it

The stack must be running (`make up` in `config/`).

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
- Both steps skip questions already in their output file. A failure (e.g. a free-tier `503` or a judge timeout) is printed and the question is retried on the next run.
- To re-run from scratch, delete `results/`. To re-score only, delete `results/scores.jsonl`.
- `QUESTIONS` (default `questions.jsonl`) and `RESULTS_DIR` (default `results`) select another question file and output directory, e.g. `QUESTIONS=question-2.json RESULTS_DIR=results-2 .venv/bin/python ragas_eval.py ask`. A `.json` question file is a JSON array; `.jsonl` is one object per line.
- `score` needs `file` to be a single file name and `heading` on every answerable question, so it does not work on `question-2.json` as it stands.

To add a question, append a line to `questions.jsonl` with `id`, `question`, `reference` (the correct answer), `file` (the file name as shown in citations; any format of the same file name counts) and `heading` (the chunk heading that holds the answer). For a question the documents cannot answer, set `"unanswerable": true` instead of `file` and `heading`; it scores `abstained` = 1 when PEKA cites nothing.

The 2026-10-27 results skip `score` and are graded by hand into `results/claude_judge.jsonl` with `doc_hit`, `heading_hit`, `correct` (0, 0.5 or 1) and `grounded` (0 or 1).
