# PEKA final report

Final evaluation of PEKA against its project objectives, run on 2026-10-30 on the project's minimum hardware (6 GB VRAM, 16 GB RAM) with the **local** language model. PEKA answered through `llama.cpp` (`gemma-4-E4B-it-qat-UD-Q4_K_XL`, `LLM_BASE_URL=http://llama:8080/v1`), and no cloud model or web search was called.

To run PEKA yourself, start with [System requirements and running PEKA locally](system-requirements.md). Answer correctness in detail is in [evaluation.md](evaluation.md).

## Verdict

| Requirement | Result | Verdict |
|-------------|--------|---------|
| **Objective 3**: Recall@5 ≥ 85% over 200+ documents | Recall@5 **99.3%** on 400 questions over **220 distinct documents** (270 files, 1,506 chunks) | **Met**, with the caveats below |
| **Objective 5 / NFR02**: response latency and time to first token | One user: first token **8.0 s median, 12.0 s p95**; full answer **8.7 s median, 14.0 s p95** | **Measured.** The repo states no target, so there is no pass or fail |
| **NFR04**: 10 concurrent users while indexing runs | **2 of 20** requests answered with 10 users. Chat alone holds **2** simultaneous users, and **1** user was served normally while files were indexing | **Not met** |
| Answer quality (supporting result) | 59 of 59 answerable questions correct, 8 of 8 unanswerable declined, hand-graded | Good on the test set |

In short: PEKA finds the right documents reliably and answers correctly, but on the minimum hardware it serves about two people at a time and cannot index documents while several people chat.

## What was built and tested

PEKA is an organization-private RAG assistant. Users upload documents, a background worker converts each one with the language model into a structured page (OKF), splits it into chunks, embeds the chunks and stores them in Postgres with pgvector. In chat, the model first decides whether to search, the service runs a hybrid keyword and vector search filtered by the user's role, and the model writes an answer with citations. See [How it works](how-it-works.md) and the [architecture](architecture/overview.md).

| Component | What runs it |
|-----------|--------------|
| Web client | Next.js behind nginx on port 3000 |
| API and indexing worker | FastAPI service and `okf-worker`, same image |
| Database | Postgres 16 with pgvector |
| Embeddings | `BAAI/bge-small-en-v1.5`, 384 dimensions, local TEI on the CPU |
| Language model | `gemma-4-E4B-it-qat-UD-Q4_K_XL` on llama.cpp (CUDA), 16,384-token context, 4 server slots sharing one KV cache |

## Test system

| Item | Value |
|------|-------|
| GPU | NVIDIA RTX 3060 Laptop, 6 GB VRAM (about 3.7 GB used by the model when idle) |
| CPU and RAM | 16 threads, 14 GB visible to the OS (a 16 GB machine) |
| Software | Docker 28.5, Compose 2.40, NVIDIA driver 595 |
| Search | `SEARCH_TOP_K=10`, hybrid vector + keyword search with reciprocal rank fusion |
| Real corpus | 70 files, 506 chunks, 20 distinct documents |
| Scale corpus (Objective 3, latency and load runs) | the real corpus plus 200 generated documents: 270 files, 1,506 chunks, 220 distinct documents |
| Users | one admin account (concurrent users are separate logins of that account) |

## Objective 3: Recall@5 over 200+ documents

Each question is sent to `POST /search` exactly as written. A question is a hit when one of the first 5 results comes from the expected document (any format of the same file name). The LLM that rewrites the query in a real chat turn is not involved, so this measures the retrieval stage only. Search takes about 0.2 s per query.

| Question set | Questions | Document Recall@1 | **Document Recall@5** | Document Recall@10 | Section Recall@5 | Search time (mean / p95) |
|--------------|-----------|-------------------|-----------------------|--------------------|------------------|--------------------------|
| Generated, 200 documents (`question-scale.json`) | 400 | 82.0% | **99.3%** | 99.8% | 99.0% | 213 ms / 223 ms |
| Real set 1 (`questions.jsonl`) | 57 | 96.5% | **100%** | 100% | 42.1% | 213 ms / 222 ms |
| Real set 2 (`question-2.json`) | 59 | 89.8% | **96.6%** | 100% | n/a | 211 ms / 220 ms |
| **All three** | **516** | | **99.0%** (511 hits) | | | |

The 70-file corpus on its own gave 100% (set 1) and 94.9% (set 2), so adding 200 documents did not reduce recall.

How the scale corpus was built: 200 generated OKF pages (a purpose section, a metrics table, a decisions section and a risks section, each with unique names, owners, numbers, vendors and dates) were chunked by the real chunker, embedded by the real embedding service and inserted directly by [`eval/scale_corpus.py`](../eval/scale_corpus.py). The local-LLM conversion step was skipped because it takes about 60 to 80 s per file, which would be about 4.5 hours for 200 files. Two questions per document ask for a metric's owner and target, and for the vendor and contract start date. The corpus and its rows were removed after the run, and the database is back to 70 files and 506 chunks.

Misses at rank 5: generated questions 3, 359 and 373 (all three found by rank 10), and set 2 questions 15 and 26. Set 1 questions 18, 19, 31, 32, 54 to 57 and 68 to 70 ask about files that are not in the current knowledge base and are left out of the counts. Counting them as misses would give set 1 a Recall@5 of 83.8%.

**Caveats**

- **The 200 added documents are generated, not real.** They follow one template with unique facts, and each question names its document, like the real question sets. A real corpus of 200+ varied reports is likely harder. Treat 99% as the ceiling for well-named documents, not a field result.
- **Indexing was not exercised at this size.** Real conversion by the local model produced worse page structure in earlier runs ([evaluation.md](evaluation.md)), and recall on pages it writes is what users get.
- **Finding the right section is weak on the real documents.** Section Recall@5 is 42% on set 1: the right file is found but another section or copy ranks first.

## Objective 5 / NFR02: latency and time to first token

20 answerable questions from set 2 (random order, fixed seed), asked one at a time through `POST /chat/stream` after one discarded warm-up request, on the 270-file corpus. Times are measured by the client from sending the request.

| | Mean | Median | p95 | Max |
|---|------|--------|-----|-----|
| First status event ("Thinking...") | 0.01 s | 0.01 s | 0.01 s | 0.01 s |
| **Time to first answer token** | 8.6 s | 8.0 s | 12.0 s | 16.2 s |
| **Full answer** | 9.8 s | 8.7 s | 14.0 s | 17.9 s |

All 20 answered. The earlier run on 70 files gave the same picture (8.98 s mean, 12.9 s p95 to first token), so corpus size is not what drives latency.

- **Almost all of the wait is the model.** Before any text appears PEKA makes a planning call, searches (0.2 s), then reads up to 10 sources of 3,000 characters before it writes the answer. The answer then appears within about a second, so it behaves like a pause followed by a block of text, not a stream.
- **The first status event is immediate**, so the UI shows "Thinking..." right away.

## NFR04: concurrent users and indexing

Each simulated user logs in separately and asks questions back to back. Indexing runs upload generated Markdown files (about 4.5 KB each) that the OKF worker converts with the same llama server. The files, their knowledge base pages and the chats were removed afterwards.

### Where chat alone starts to fail (one question per user)

| Concurrent users | Run 1 (70 files) | Run 2 (270 files) |
|------------------|------------------|--------------------|
| 1 | 1 of 1 | 1 of 1 |
| 2 | 2 of 2 | 2 of 2 |
| 3 | **0 of 3** | **0 of 3** |
| 4 | 0 of 4 | 1 of 4 |
| 6 | 1 of 6 | not run |
| 10 | 1 of 10 | not run |

Two users also answered 6 of 6 over three questions each (first token 11.9 s median, 13.8 s p95).

### With indexing

| Users and load | Chat only | Chat while indexing |
|----------------|-----------|---------------------|
| 1 user, 3 questions, 4 files indexed | 3 of 3, first token 9.1 s mean | **3 of 3**, first token 10.6 s mean; indexing finished in 232 s (58 s per file) |
| 2 users, 3 questions each, 4 files indexed | 6 of 6 | **2 of 6**; indexing finished in 345 s |
| 10 users, 2 questions each, 8 files indexed | **2 of 20** | **2 of 20**; indexing finished in 633 s |

The 1-user runs only partly overlap: the chat finished after 35 s while indexing took 232 s. They show that one chat user and the worker can share the model, not how the two behave over a long overlap.

### Why it fails

The failures are not a cloud call or an API key problem. The service log shows 146 `openai.APIError: Context size has been exceeded.` errors from the local llama server, and PEKA turns every model failure into the generic message `AI provider request failed`.

llama.cpp starts 4 slots that **share one 16,384-token context** (`n_ctx_slot = 16384`, unified KV cache). A chat turn sends the system prompt plus up to 10 sources of 3,000 characters, and the llama log shows requests of about 4,500 tokens or more. Two chats fit, three do not, and an OKF conversion takes a share of the same pool. PEKA retries a failed model call once, which adds load while the pool is still full. Users see an error message, and nothing queues a request until the model has room.

## How many users does this system serve?

On the minimum hardware, with the current configuration:

| Situation | Simultaneous chat users that work |
|-----------|-----------------------------------|
| Chat only | **2** (3 or more start to fail) |
| Chat while documents are indexing | **1** (2 users lost 4 of 6 requests) |
| 10 users (NFR04) | **Not supported**: 2 of 20 answered |

"Simultaneous" means questions being answered at the same moment. One answer takes about 10 s, so people who ask a question only now and then take far fewer of these slots than the number of accounts. As a rough estimate (a model, not a measurement): if each user asks one question a minute at random times, about **4 to 5 such users** keep the chance of 3 overlapping questions under about 5%. The system has no queue, so every overlap of 3 or more questions fails instead of waiting.

## Recommendations

The 6 GB GPU already holds about 3.7 GB for the model at the current context, so a much larger context is unlikely to fit and needs testing. In order of effort:

1. **Queue model requests in the service** (a semaphore sized to what the model holds) so extra users wait about 10 s each instead of failing. Any number of users then works, though slowly. With 10 users the last one would wait about 100 s, so NFR04 would still depend on what response time it allows.
2. **Retry after a delay** when the error is `Context size has been exceeded`, instead of straight away.
3. **Cut the prompt size** with a lower `SEARCH_TOP_K` or fewer characters per source, at some cost to answer quality.
4. **Keep indexing off the chat model**: a hosted or larger model for OKF conversion (also recommended in the answer-quality findings) or indexing outside working hours.
5. **Re-run Objective 3 on real documents.** The generated corpus shows retrieval holds at 220 documents, but a real set of 200+ independent reports with independently written questions is the proper proof.

None of these were tried for this report. Items 1 and 2 have since been added (issue #95), so the concurrency figures above describe the system before that change. Two later chat-only runs, with one question per user and no indexing, answered every question: 3 of 3 users (slowest 22 to 25 s), 4 of 4 (31 to 35 s) and 10 of 10 (82 to 89 s), with no `Context size has been exceeded` errors. One repeat of the load tests above gave: 1 user 3 of 3 chat only and 3 of 3 while indexing; 2 users 6 of 6 chat only and **0 of 6** while indexing; 10 users 20 of 20 chat only (slowest 134 s) and **4 of 20** while indexing. So the queue fixes chat alone, but chat while indexing still fails above 1 user, because the OKF worker is outside the queue. All 22 delayed retries in those indexing runs failed too.

## Limitations

- **One machine, one run per cell.** Latency has 20 samples, load levels were run once or twice, and the 6 GB laptop GPU may differ from the target server.
- **Concurrent users share one account.** They use separate logins and conversations, but the same role and document access.
- **Synthetic indexing load.** The uploaded files are small and generated, so real documents would hold the model longer. Indexing time per file (58 to 86 s) comes from these files.
- **No thresholds for latency or concurrency** are written in the repo. Only Objective 3 (85%) has a number, so only it gets a pass.
- **The users-per-minute estimate is a model**, assuming random arrivals and 10 s per answer. It was not measured.
- **Only the dev stack was run** (`make up`). `make prod-up` was not part of the evaluation.

## Reproducing the results

The stack must be running with the local model (see [System requirements](system-requirements.md)). The scripts use only the Python standard library. Raw output is in [`eval/results-perf/`](../eval/results-perf/), and the answers behind the answer-quality numbers are in [`eval/results/`](../eval/results/).

```bash
cd eval
export PEKA_URL=http://localhost:8000 PEKA_EMAIL=... PEKA_PASSWORD=...   # an admin account

python3 perf_eval.py recall                      # Recall@1/5/10 over the real question sets
python3 perf_eval.py latency                     # 20 sequential chats, time to first token
python3 perf_eval.py ramp 1 2 3 4                # concurrent users, one question each
python3 perf_eval.py load 2 3 4                  # users, questions per user, files to index

# 200+ document recall: add the generated corpus, test, then remove it
docker exec -i config-okf-worker-1 python - add 200 < scale_corpus.py   # also writes /tmp/question-scale.json in the container
python3 perf_eval.py recall question-scale.json questions.jsonl question-2.json
docker exec -i config-okf-worker-1 python - remove < scale_corpus.py
```

`eval/question-scale.json` is already in the repo for the fixed seed, so the `add` step reproduces the same questions. `load` uploads generated files as the logged-in user and deletes them afterwards, but the OKF worker writes knowledge base pages under `service/storage/knowledge_base/` that are not removed with the file, and the pages belong to root. Delete the `perf-test-*` pages (and the `index.md` of any category directory the run created) with `docker exec config-okf-worker-1 rm ...`.
