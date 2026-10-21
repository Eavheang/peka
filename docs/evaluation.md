# Answer-quality evaluation

A small, repeatable check of how well PEKA answers questions about the indexed documents. It asks PEKA 20 questions with known answers, then scores each reply with [RAGAS](https://docs.ragas.io/) (an open-source RAG evaluation library) and with a simple retrieval check.

This lives in [`eval/`](../eval/) as a standalone script. It is not part of the app and has its own dependencies.

## What is measured

| Metric | Question it answers | How |
|--------|---------------------|-----|
| `doc_hit` | Did PEKA cite the right document? | At least one citation's title matches the expected file. Deterministic, no LLM. |
| `heading_hit` | Did PEKA cite the right section? | At least one citation matches the expected file **and** heading. Deterministic, no LLM. |
| `faithfulness` | Is the answer backed by the passages it cites? | RAGAS splits the answer into claims and asks a judge LLM whether each claim follows from the cited passages. Score = supported claims / all claims. |
| `context_recall` | Do the cited passages contain what the reference answer needs? | RAGAS checks each claim of the reference answer against the cited passages. |
| `context_precision` | Are the cited passages relevant, with the relevant ones first? | RAGAS judges each cited passage against the reference answer, rank-weighted. |

When PEKA cites nothing, all five metrics are scored 0 for that question: nothing backs the answer and nothing relevant was found.

## Results (2026-10-21)

| Metric | Mean (n = 20) |
|--------|---------------|
| `doc_hit` | **0.950** |
| `heading_hit` | **0.950** |
| `faithfulness` | **0.943** |
| `context_recall` | **0.950** |
| `context_precision` | **0.950** |

19 of 20 questions scored 1.0 on every retrieval metric. Per-question results are in [`eval/results/scores.jsonl`](../eval/results/scores.jsonl) and PEKA's full replies are in [`eval/results/answers.jsonl`](../eval/results/answers.jsonl).

### Setup

| Item | Value |
|------|-------|
| Corpus | 2 documents, 22 chunks: `1_Business_Plan_MekongFreshFoods.pdf`, `B11-G03_PEKA_Review1_Document.docx` |
| Questions | 20 (10 per document), in [`eval/questions.jsonl`](../eval/questions.jsonl) |
| User role | Admin (can see every document) |
| PEKA's model | `google/gemma-4-26b-a4b-it:free` via OpenRouter (cloud mode, not the local llama.cpp model) |
| Judge model | `minimax/minimax-m3.1-flash:free` via OpenRouter |
| Embeddings | `BAAI/bge-small-en-v1.5` (local TEI) |
| RAGAS | 0.4.3 |

### Failures and findings

- **Q12, "Which embedding model does PEKA use?": search was skipped.** PEKA's planning step chose `tool: none` and answered as if asked about the assistant itself ("I do not have access to my own internal technical specifications…"). No citations, so every metric scored 0. This is a failure in deciding whether to search, not in retrieval. Questions about "PEKA" can be read as questions about the assistant.
- **Q9, faithfulness 0.86: a small embellishment.** The answer describes redundant refrigeration as "backup cooling systems to prevent temperature fluctuations". The passage does not say that, and the judge correctly marked that claim unsupported.
- **Retrieval depends on the question naming its subject.** During setup, the question "How many cooperative clusters are farmers organized into?" (no company name) was answered from general knowledge with no search and no citations. With "Mekong Fresh Foods'" added, it was answered correctly. All 20 evaluation questions name their subject.
- **Chunks lose their document context.** Many chunks never name who they are about. For example, the "Operations Plan" chunk says "Farmers are organized into eight cooperative clusters" but never mentions Mekong Fresh Foods. See the scoring note below.

### Scoring note: the judge sees title and heading

A PEKA citation shows the user the document title, the section heading and the passage. The judge is given the same: each passage is prefixed with `title > heading`. In an earlier run the judge got the passage text alone and faithfulness came out at **0.783**. Correct answers such as "the farmers are organized into eight cooperative clusters" (Q8) scored 0, because the passage alone does not say *whose* farmers. Removing the `[1]` citation markers from answers did not change this (0.719 on the 19 questions scored). Adding title and heading did. Retrieval metrics were the same in every run.

This also suggests a product improvement: putting the document title in each chunk before embedding (a "contextual chunk header") would help retrieval for questions that don't name their subject.

### Limitations

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

To add a question, append a line to `questions.jsonl` with `id`, `question`, `reference` (the correct answer), `file` (the file name as shown in citations) and `heading` (the chunk heading that holds the answer).
