# PEKA final report

Final evaluation of PEKA against its project objectives on the project's minimum hardware (6 GB VRAM, 16 GB RAM) with the **local** language model. PEKA answered through `llama.cpp` (`gemma-4-E4B-it-qat-UD-Q4_K_XL`), and no cloud model or web search was called. The evaluation first ran on 2026-10-30. It was repeated in full on 2026-11-07 on the code with issues #95, #96, #97, #98, #99 and #101, and the numbers below come from that repeat unless they say otherwise.

To run PEKA yourself, start with [System requirements and running PEKA locally](system-requirements.md). Earlier answer-quality runs are in [evaluation.md](evaluation.md).

## Verdict

| Requirement | Result | Verdict |
|-------------|--------|---------|
| **Objective 3**: Recall@5 ≥ 85% over 200+ documents | Recall@5 **100%** on 400 generated questions over **220 distinct documents** (270 files, 1,682 chunks); 100% and 98.3% on the two real question sets | **Met**, with the caveats below |
| **Objective 5 / NFR02**: response latency and time to first token | One user: first token **4.9 s median, 7.5 s p95**; full answer **5.6 s median, 8.3 s p95** | **Measured.** The repo states no target, so there is no pass or fail |
| **NFR04**: 10 concurrent users while indexing runs | **20 of 20** requests answered with 10 users while 8 files indexed; the slowest took 80 s | **Met** in that every request was answered. The repo states no limit on the wait, and this was one run |
| Answer quality (supporting result) | 57 of 59 answerable questions correct, 1 partly correct, 1 wrongly declined; 8 of 8 unanswerable declined, hand-graded | Good on the test set |

In short: PEKA finds the right documents reliably and answers correctly. On the minimum hardware it answers two questions at a time and queues the rest, so 10 people can use it together but may wait over a minute. Indexing no longer competes for the model. The result on 200+ documents comes from generated documents, so a proper test on real documents is still open (issue #104).

## What was built and tested

PEKA is an organization-private RAG assistant. Users upload documents, and a background worker extracts their original text, splits it into chunks, embeds the chunks and stores them in Postgres with pgvector, without using the language model. In chat, the service runs a hybrid keyword and vector search filtered by the user's role, reranks the hits with a local cross-encoder, refuses a question for a specific fact when no passage matches it, and otherwise has the model write an answer with citations. A follow-up question first makes one short model call to rewrite its search. See [How it works](how-it-works.md) and the [architecture](architecture/overview.md).

| Component | What runs it |
|-----------|--------------|
| API and indexing worker | FastAPI service and `index-worker`, same image |
| Database | Postgres 16 with pgvector |
| Embeddings | `BAAI/bge-small-en-v1.5`, 384 dimensions, local TEI on the CPU |
| Reranker | `cross-encoder/ms-marco-MiniLM-L6-v2`, local TEI on the CPU |
| Language model | `gemma-4-E4B-it-qat-UD-Q4_K_XL` on llama.cpp (CUDA), 16,384-token context shared by 4 server slots |

## Test system

| Item | Value |
|------|-------|
| GPU | NVIDIA RTX 3060 Laptop, 6 GB VRAM (about 3.1 GB used by the model, 3.9 GB with the desktop) |
| CPU and RAM | 16 threads, 14 GB visible to the OS (a 16 GB machine) |
| Software | Docker 28.5, Compose 2.40, NVIDIA driver 595 |
| Stack | A separate Compose project with its own database and storage, attached to the project's llama container. The web client was not involved: requests went straight to the API |
| Settings | `SEARCH_TOP_K=10`, `RERANK_CANDIDATES=20`, `RERANK_TOP_K=5`, `SEARCH_EVIDENCE_FLOOR=0.1`, `LLM_MAX_TOKENS=2048`, `LLM_MAX_CONCURRENT_CHATS=2`, `OKF_ENRICHMENT_ENABLED=false` |
| Real corpus | 70 files, 682 chunks, 20 distinct documents |
| Scale corpus (Objective 3, latency and load runs) | the real corpus plus 200 generated documents: 270 files, 1,682 chunks, 220 distinct documents |
| Users | one admin account (concurrent users are separate logins of that account) |

Raw output is kept locally and is not published in this repository. The model ran at about 85 tokens per second throughout, which the run checked before and after every step, and the service logged no `Context size has been exceeded` errors and no reranker failures.

## Objective 3: Recall@5 over 200+ documents

Each question is sent to `POST /search` exactly as written. A question is a hit when one of the first 5 results comes from the expected document (any format of the same file name). The language model is not involved, so this measures the retrieval stage only.

| Question set | Questions | Document Recall@1 | **Document Recall@5** | Document Recall@10 | Section Recall@5 | Search time (mean / p95) |
|--------------|-----------|-------------------|-----------------------|--------------------|------------------|--------------------------|
| Generated, 200 documents (`question-scale.json`) | 400 | 100% | **100%** | 100% | 100% | 430 ms / 612 ms |
| Real set 1 (`questions.jsonl`) | 57 | 98.2% | **100%** | 100% | see below | 752 ms / 877 ms |
| Real set 2 (`question-2.json`) | 59 | 96.6% | **98.3%** | 100% | n/a | 752 ms / 908 ms |
| **All three** | **516** | | **99.8%** (515 hits) | | | |

The 70-file corpus on its own gave the same 100% (set 1) and 98.3% (set 2), so adding 200 documents did not reduce recall. Compared with 2026-10-30, the reranker raised Recall@1 on the generated set from 82.0% to 100% and Recall@5 from 99.3% to 100%, at the cost of slower search (about 0.2 s before, 0.4 to 0.8 s now).

How the scale corpus was built: 200 generated documents (a purpose section, a metrics table, a decisions section and a risks section, each with unique names, owners, numbers, vendors and dates) were chunked by the real chunker, embedded by the real embedding service and inserted directly by a local script. Two questions per document ask for a metric's owner and target, and for the vendor and contract start date.

The one miss at rank 5 is set 2 question 31, which is found by rank 10. Set 1 questions 18, 19, 31, 32, 54 to 57 and 68 to 70 ask about files that are not in the knowledge base and are left out of the counts. Counting them as misses would give set 1 a Recall@5 of 83.8%.

**Caveats**

- **The 200 added documents are generated, not real.** They follow one template with unique invented names, and each question names its document, like most of the real questions. A real corpus of 200+ varied reports is likely harder. Treat these figures as the ceiling for well-named documents, not a field result. Issue #104 tracks a test on real questions.
- **The upload path was not exercised at this size.** The real corpus was uploaded through the API, and the generated documents were inserted directly.
- **Section Recall@5 on set 1 cannot be compared with the earlier run.** It reads 0% because `questions.jsonl` holds the section names of the old OKF pages, and chunks now use the headings of the original documents. The earlier source-text run measured a passage with the answer in the top 5 for 94.9% of set 2, on the same search.

## Objective 5 / NFR02: latency and time to first token

20 answerable questions from set 2 (random order, fixed seed), asked one at a time through `POST /chat/stream` after one discarded warm-up request, on the 270-file corpus. Times are measured by the client from sending the request.

| | Mean | Median | p95 | Max |
|---|------|--------|-----|-----|
| First status event ("Thinking...") | 0.01 s | 0.01 s | 0.01 s | 0.01 s |
| **Time to first answer token** | 5.2 s | 4.9 s | 7.5 s | 12.6 s |
| **Full answer** | 6.0 s | 5.6 s | 8.3 s | 13.3 s |

All 20 answered. The 67 questions of the answer-quality run, on 70 files, gave the same picture (first token 5.3 s median and 8.1 s p95, full answer 6.2 s and 9.6 s), so corpus size is not what drives latency. On 2026-10-30 the first token took 8.0 s median and 12.0 s p95.

- **Almost all of the wait is the model.** Search takes under a second, then the model reads 5 sources before it writes the answer. The answer then appears within about a second, so it behaves like a pause followed by a block of text, not a stream.
- **A follow-up question adds about 2 s** to rewrite its search. These questions were all first questions.
- **The first status event is immediate**, so the UI shows "Thinking..." right away.

## NFR04: concurrent users and indexing

Each simulated user logs in separately and asks questions back to back. Indexing runs upload generated Markdown files (about 4.5 KB each), and the worker indexes them without the language model. The files and chats were removed afterwards.

### Chat alone (one question per user)

| Concurrent users | 70 files: answered (slowest) | 270 files: answered (slowest) |
|------------------|------------------------------|-------------------------------|
| 1 | 1 of 1 (9.0 s) | 1 of 1 (7.7 s) |
| 2 | 2 of 2 (9.2 s) | 2 of 2 (9.0 s) |
| 3 | 3 of 3 (15.6 s) | 3 of 3 (13.9 s) |
| 4 | 4 of 4 (14.7 s) | 4 of 4 (16.1 s) |
| 6 | 6 of 6 (21.7 s) | 6 of 6 (21.3 s) |
| 10 | 10 of 10 (43.3 s) | 10 of 10 (48.7 s) |

### With indexing (270 files)

| Users and load | Chat only: answered, first token median / p95, slowest answer | Chat while indexing: answered, first token median / p95, slowest answer | Indexing finished in |
|----------------|---------------------------------------------------------------|-------------------------------------------------------------------------|----------------------|
| 1 user, 3 questions, 4 files | 3 of 3, 4.2 s / 7.0 s, 8.9 s | 3 of 3, 5.4 s / 8.1 s, 8.9 s | 7 s |
| 2 users, 3 questions each, 4 files | 6 of 6, 7.4 s / 8.3 s, 10.9 s | 6 of 6, 7.7 s / 14.3 s, 16.1 s | 7 s |
| 10 users, 2 questions each, 8 files | 20 of 20, 9.5 s / 75.8 s, 83.3 s | **20 of 20**, 15.5 s / 68.2 s, 79.7 s | 12 s |

The overlap is short: chat ran for 21 to 89 s and indexing took 7 to 12 s. That is what removing the model from indexing buys, but these files are small, so this does not show how a long indexing job behaves. The worker now competes with chat only for the CPU.

The wait is uneven. With 10 users the median first token is under 16 s but the slowest takes over a minute, because a waiting turn polls for a free slot and the order is not first come, first served.

### How this changed

| Code | 10 users, chat only | 10 users, while indexing | First token, one user (median) |
|------|---------------------|--------------------------|--------------------------------|
| 2026-10-30: no queue, the model also converted each document | 2 of 20 | 2 of 20 | 8.0 s |
| Queue added (#95) | 20 of 20 | 4 of 20 | not measured |
| Indexing without the model, one call per first question, reranker (#97, #98, #99), on 70 files | 20 of 20 | 20 of 20 | 5.9 s |
| Long-conversation limits and refusal (#96, #101), on 270 files | 20 of 20 | 20 of 20 | 4.9 s |

The early failures were `Context size has been exceeded` errors from llama.cpp. Its slots share one 16,384-token context, so three chats of about 4,500 tokens, or chats next to a document conversion, overflowed it. PEKA now answers two turns at a time and queues the rest, and indexing no longer uses the model. [From OKF pages to original text](evaluation.md#from-okf-pages-to-original-text) explains why the conversion was dropped, including what the tests could not show.

### Long conversations (#96)

The load runs above use short conversations, and a prompt budget also has to hold for long ones. In this test each user continues a conversation of 20 messages of 1,200 characters of table-heavy text and asks for a report of at least 3,000 words. Refusal was turned off so that the question reached the model.

| Limits | Answered | `Context size has been exceeded` | Largest slot |
|--------|----------|----------------------------------|--------------|
| Before: 24,000 characters of history, `LLM_MAX_TOKENS=8192` | **0 of 4** (2 users, 2 rounds) | 8 | 8,348 tokens |
| After: 5,000 characters of history and question, `LLM_MAX_TOKENS=2048` | **12 of 12** (2 users, 4 rounds; 4 users, 1 round) | 0 | 5,727 tokens |

With a normal short question, long histories already worked before the change (15 of 15), so what overflowed was long answers on top of long histories. In the "after" run, 6 replies reached the 2,048-token limit, and PEKA keeps what was already shown and adds a note that the answer was cut off. Each turn now fits its share of the context (8,192 tokens): about 380 for the system prompt, at most about 3,650 for 5 sources, 2,048 for the answer and the rest for history and question. The limits count characters, so text denser than the corpus's worst case (2.46 characters per token) could still overflow when two such turns overlap.

## No-evidence refusal (#101)

`refused` was never `true` before this change: declining was only wording the model chose. The server now checks the evidence after search. When there are no results, or the top rerank score is below `SEARCH_EVIDENCE_FLOOR` (0.1), one short model call asks whether the question needs a specific fact only the organization's records could hold. If it does, the server sends a fixed reply with `refused: true` and no citations, in about 2 s and without generating an answer. Anything else goes on to the answer model. The text is the same whether a document is missing or the user may not read it.

Why 0.1: this is the top rerank score of each group, on 70 files and on 270 files.

| Questions | Top rerank score | Below 0.1 |
|-----------|------------------|-----------|
| Generated, answerable (400) | lowest 0.995 | none |
| Real sets, answerable (116) | lowest 0.23 | **none** |
| Set 1, about files not in the corpus (11) | lowest 0.008 | 4 on 70 files, 3 on 270 files |
| Set 2, unanswerable (8) | 0.001, then 0.52 to 0.99 | 1 |
| Off-topic or missing private facts (6) | at most 0.013 | all 6 |
| Greetings, arithmetic, general knowledge (11) | at most 0.006 on 70 files, 0.31 on 270 files | all on 70 files, 10 on 270 files |

The score separates "no passage matches" from "a passage matches", but it cannot tell small talk from a missing fact, which is why the model call is needed. Results on the real model, one run per question on 70 files:

| Questions | Result |
|-----------|--------|
| Set 2, answerable (59) | **0 refused** |
| Set 2, unanswerable (8) | **1 refused** (question 66), 7 declined in words by the model, none cited |
| Missing private facts, such as a Wi-Fi password or a report that does not exist (9) | **9 of 9 refused** |
| Greetings, arithmetic, programming, public knowledge (13) | **0 refused.** Two public questions were declined in words, because the model still sees the weak sources |
| Broad requests, such as "Summarize all the documents" (10) | 9 answered, 1 refused ("List the key numbers from the latest report") |

**What refusal does not do.** It catches questions with no matching passage, not near misses. Seven of the 8 unanswerable questions in set 2 match a passage that does not hold the fact (the score is 0.52 to 0.99), so the model declines in words and `refused` stays `false`. Those replies get no "Not enough evidence" label. The check is also skipped for web search and when the reranker is down.

An answer block that claims a source ID from outside the current turn already loses it and becomes a general block, so no change was needed for that part of #101.

## Answer quality

67 questions from set 2 over the 70-file corpus, each in a new conversation, graded by reading each answer against its reference.

| Result | Count | Questions |
|--------|-------|-----------|
| Answerable, correct | **57 of 59** | |
| Answerable, partly correct | 1 | 29: gives the supply agreement's limit but not the stricter inspection limit it also asks about |
| Answerable, wrongly declined | 1 | 31: the reranker pushed its document out of the top 5 |
| Unanswerable, declined | **8 of 8** | 60 to 67, none with a citation |

Smaller problems: questions 2 and 14 are correct but cite nothing, question 14 also lists other suppliers' payment terms, and question 41 opens with an unsupported hedge before the correct owner and target.

The earlier run on the same search got question 29 fully right, cited question 2, and gave a clean answer to question 41, so some of this is variation between runs. Each question was asked once. Set 2 was graded in one pass by one grader, and its questions follow the source wording.

## How many users does this system serve?

On the minimum hardware, with the current configuration:

| Situation | What works |
|-----------|------------|
| Answered at the same moment | **2**. Anyone else waits for a free slot and then gets an answer |
| Chat while documents are indexing | The same. All 20 of 20 were answered with 10 users |
| 10 users asking together (NFR04) | **Supported, with waiting**: 20 of 20 answered, the slowest in 80 s |
| Throughput | About **14 answers a minute** (20 answers in 88 s) |

People who ask a question only now and then rarely overlap, so a team of occasional users seldom waits, while 10 people asking at once wait in turn. Whether 80 s is acceptable is for the project to decide, since NFR04 sets no limit.

## Recommendations

In order of value:

1. **Test recall on real documents (#104).** A real set of 200+ independent reports with independently written questions is the proper proof of Objective 3.
2. **Set a response-time target for NFR02 and NFR04.** Without one these results cannot pass or fail on speed.
3. **Mark near misses as refused.** Letting the model flag "the sources do not contain this" as its own answer type would set `refused` on the 7 of 8 near misses that the score cannot catch. Not tried.
4. **Keep the model out of indexing.** OKF enrichment sent each whole document to the model that serves chat, outside the chat queue, and the last run with the model in indexing answered 4 of 20. Enrichment was off for this evaluation and has since been removed.
5. **Make the queue first come, first served** if the longest waits matter more than the median.
6. **Cap llama.cpp's prompt cache on a 16 GB machine** (`--cache-ram`) if memory gets tight, as described below. Not tried.

## Limitations

- **One machine, one run per cell.** Latency has 20 samples, each load level was run once, and the 6 GB laptop GPU may differ from the target server.
- **Concurrent users share one account.** They use separate logins and conversations, but the same role and document access.
- **Synthetic indexing load.** The uploaded files are small and generated, and each indexing run overlapped chat for only 7 to 12 s.
- **No thresholds for latency or concurrency** are written in the repo. Only Objective 3 (85%) has a number.
- **The refusal floor was set on these question sets.** A different corpus or rerank model may need a new `SEARCH_EVIDENCE_FLOOR`. Setting it too high refuses questions the documents can answer.
- **The API was tested, not the web client, and only on an isolated dev-style stack.** `make prod-up` was not part of the evaluation.
- **An existing `.env` keeps its old limit.** `LLM_MAX_TOKENS=8192` in a `service/.env` overrides the new default of 2048, and it needs changing by hand.
- **The GPU can get stuck after a suspend.** During this evaluation, after the laptop suspended and resumed, the GPU stayed at 810 MHz of 2,100 MHz with the memory clock at 810 of 7,001 MHz. The model ran at about 10 tokens per second instead of 85, and the first token took 33 s median. Restarting llama did not help and a reboot did. Later short suspends did not cause it. The affected runs were discarded, and the numbers in this report come from runs after the reboot, with sleep blocked.
- **llama.cpp's memory grows.** After about 6 hours of testing the llama process held about 9.5 GB (2.7 GB in RAM and 6.8 GB in swap), most likely its prompt cache, on a machine with 14 GB visible. Restarting it brought available memory from about 1 GB to about 10 GB.

## Reproducing the results

These commands need the local `eval/` folder, which is not in this repository. They are recorded to show the method. The stack must be running with the local model (see [System requirements](system-requirements.md)). The scripts use only the Python standard library. The scripts overwrite their output files, so point `RESULTS_DIR` at a new folder. A step that runs longer than the access token (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, 30 by default) fails with HTTP 401. Before a run, keep the machine from sleeping and check that the model is fast: on this GPU, llama's log should show about 85 tokens per second.

```bash
cd eval
export PEKA_URL=http://localhost:8000 PEKA_EMAIL=... PEKA_PASSWORD=...   # an admin account
export RESULTS_DIR=results-perf/my-run

python3 perf_eval.py answers                     # set 2, one new conversation per question, for grading
python3 perf_eval.py recall                      # Recall@1/5/10 over the real question sets
python3 perf_eval.py ramp 1 2 3 4 6 10           # concurrent users, one question each

# Add the generated corpus for the runs on 200+ documents, then remove it
docker exec -i config-index-worker-1 python - add 200 < scale_corpus.py   # also writes /tmp/question-scale.json in the container
python3 perf_eval.py recall question-scale.json questions.jsonl question-2.json
python3 perf_eval.py latency                     # 20 sequential chats, time to first token
python3 perf_eval.py load 10 2 8                 # users, questions per user, files to index
docker exec -i config-index-worker-1 python - remove < scale_corpus.py
```

`question-scale.json` uses a fixed seed, so the `add` step reproduces the same questions. `load` uploads generated files as the logged-in user and deletes them afterwards. The rerank scores, long-conversation test and refusal checks were run with one-off scripts, and their results are recorded in this report.
