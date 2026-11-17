# Objectives and evaluation

The problem PEKA addresses, its aim and objectives as approved in the proposal (15 July 2026), and whether each objective was met, with the evidence. Detailed measurements are in the [final report](../final-report.md); requirement status is in [Requirements](requirements.md).

## Problem

Staff in small and medium-sized enterprises and NGOs keep policies, procedures, reports, spreadsheets and slide decks across shared drives, email and chat. Finding an answer means searching by file name or opening documents one by one, and an answer may be spread over several files. Two pieces of published evidence frame the problem:

- **Time.** The McKinsey Global Institute estimated that an interaction worker spends nearly 20% of the workweek looking for internal information or tracking down colleagues who can help [1]. This is a 2012 estimate across many industries, not a measurement of SMEs or NGOs, but it shows that finding information has a real cost.
- **Data leaks.** In May 2023 Samsung temporarily restricted generative AI tools on company devices after sensitive internal data was leaked to ChatGPT in April [2]. Pasting internal documents into a public AI service moves them outside the organization's control.

Cloud assistants such as Notion AI and NotebookLM answer questions with citations, but they run on the vendor's servers and charge per user or at scale (see [Related work](related-work.md)). PEKA keeps documents, search and, by default, the language model on the organization's own machine.

## Aim

To design and implement a privacy-preserving, offline retrieval-augmented generation (RAG) platform that lets SMEs and NGOs retrieve organizational knowledge through natural-language questions without relying on cloud services, deployable with minimal setup.

## Objectives and verdicts

Judgements are **Achieved**, **Partly achieved** or **Not achieved**.

| # | Objective (approved target) | Evidence | Judgement |
|---|-----------------------------|----------|-----------|
| 1 | **Document synchronization and OKF conversion.** Detect new or changed documents, download, extract and convert them to OKF with clear source references | Upload, one-off Google Drive import and the daily sync of an admin-designated Drive folder go through extraction, chunking and indexing, and every chunk keeps its page, slide, sheet or section for citations. The sync detects new, edited and deleted files in the folder tree (added 17 November). OKF conversion was built and then withdrawn on evidence ([Scope changes](scope-changes.md#okf-conversion-withdrawn)) | **Partly achieved**: synchronization built, OKF withdrawn |
| 2 | **Data sovereignty.** The local model and local vector store do all search and generation, with no outbound call to a public AI API after setup | Embeddings, reranking, search and the language model run in local containers. With the stack's network cut off from the outside, upload, indexing and a cited answer all worked ([NFR03](#nfr03-offline-operation)) | **Achieved** in local mode. Opt-in web search, the optional hosted model, invitation emails and Google Drive import and sync use the internet by design; offline they pause instead of failing |
| 3 | **High-precision retrieval.** Recall@5 of at least 85% over 200+ documents | Recall@5 100% on 400 questions over 220 distinct documents (200 generated); 100% and 98.3% on two real question sets; 100% on 211 reworded questions over 50 distinct documents ([final report](../final-report.md#objective-3-recall5-over-200-documents)) | **Achieved.** The 200+ result uses generated documents; no single run used 200+ distinct real documents |
| 4 | **Grounded traceability.** 100% of answers carry an application-generated citation, and 100% of claims are supported | Citations on 211 of 211 answers to answerable questions; 202 of 211 answers fully correct, 3 wrong ([final report](../final-report.md#objective-4-citations)) | **Achieved** for citation coverage, **partly achieved** for claim support |
| 5 | **Hardware and performance.** Runs on commodity hardware (16 GB RAM) with an average response under 3 s for standard questions | Every evaluation ran on a 6 GB laptop GPU with 16 GB RAM. The full answer took 6.0 s on average (5.6 s median); the first token 4.9 s median and 7.5 s p95, which meets the refined NFR02 target of under 10 s ([final report](../final-report.md#objective-5--nfr02-latency-and-time-to-first-token)) | **Partly achieved.** The hardware target is met; the 3 s average is not |

## Success indicators from the proposal

| Indicator | Target | Result |
|-----------|--------|--------|
| Query response time | Average under 3 s | 6.0 s average full answer; not met (Objective 5) |
| Retrieval recall | Recall@5 ≥ 85% over 200+ documents | 100%; met (Objective 3) |
| Citation coverage | 100% of answers cite a source | 211 of 211; met (Objective 4) |
| Offline operation | No outbound call to an external AI API | Met in local mode ([NFR03](#nfr03-offline-operation)) |
| System uptime | 99% during testing | Not measured |
| User task completion | 90% of test users find the right information within 3 questions | Not measured; no user test was run (NFR06) |
| Deployment time | Under 30 minutes with Docker Compose | Met on the test machine ([NFR07](#nfr07-deployment-time)) |

## NFR03: offline operation

**Date:** 17 November 2026. **Code:** `main` at commit `4a08cd9`. **Machine:** the test machine below.

**Method.** The stack deployed in the [NFR07 test](#nfr07-deployment-time) was stopped and started again with its Docker network marked `internal`, so no container had a route outside the host. The embedding and reranking models were already in their volume and the language model file on disk. A script inside the API container then:

1. tried to open connections to `huggingface.co:443` and `1.1.1.1:443`,
2. signed in, uploaded `08_QC_Procedure_Dried_Mango.txt` and `06_Supply_Agreement.pdf` and waited for indexing,
3. asked "What are the critical control points in our dried mango QC procedure?"

**Result.**

| Check | Result |
|-------|--------|
| Outbound connections | Both blocked: name resolution failed, and the network was unreachable |
| Embedding, reranking and language model containers | Started and reported healthy from their local files |
| Upload and indexing | Both files indexed in 3.0 s |
| Chat | Answered in 12.9 s (the first question after start), not refused, citing `08_QC_Procedure_Dried_Mango.txt` |

**What needs the internet.** The first setup downloads Docker images and the embedding and reranking models, and the language model file has to be downloaded once. After that, only these features leave the machine, and each is optional: web search (FR17), a hosted language model (FR15), invitation emails over SMTP (the invite link still works when copied by hand) and Google Drive import and folder sync (FR02).

Offline, these features pause rather than break. The server checks for a connection and the web client shows an **Offline** badge. Chat answers from the documents without web search, Drive requests explain that PEKA is offline, invitations return the link to copy, and a due folder sync waits and runs once the internet is back.

**Limits.** One run, one question. The check proves that the local pipeline needs no outside network; it does not inspect a long session's traffic.

## NFR07: deployment time

**Date:** 17 November 2026. **Code:** a fresh clone of `main` at commit `4a08cd9`. **Steps:** the ones in [System requirements](../system-requirements.md#start-peka): copy `service/.env.example`, set the JWT secret and first admin, `make setup`, `make llm`, then sign in.

| Step | Time |
|------|------|
| Clone and environment files | under 1 s |
| `make setup` (build, start Postgres, embeddings and reranker, migrate, start API, worker, web client and proxy) | 58 s |
| `make llm` and model loaded | 62 s |
| Web client answering | 196 s |
| First admin sign-in | under 1 s |
| **Total** | **316 s (5 min 16 s)** |

About 3 minutes of the total went to two faults found during the run, both now documented:

- **Model folder.** A fresh clone has no `config/model/` folder, because it is gitignored. The test script linked the model file before the folder existed, so Docker created an empty, root-owned folder and llama could not find the model. Following the documented step (create the folder and save the model in it before `make llm`) avoids this.
- **Incomplete web client install (D-27).** The first `bun install` in the new `node_modules` volume left the `next` package without its `dist/bin` folder, so the web client failed with `next: not found`. Running `bun install --frozen-lockfile --force` fixed it. See [Troubleshooting](../glossary-and-troubleshooting.md#troubleshooting).

**What this does not include.** Docker images and build layers were already cached on the machine, and the 4.2 GB model file was already downloaded; the embedding and reranking models were downloaded during the run. A first install on a new machine also downloads about 10 GB (the llama.cpp CUDA image 4.35 GB, the model 4.2 GB, the embeddings image 0.69 GB, pgvector 0.44 GB and the Bun image 0.17 GB), which was not timed and depends on the connection. SMTP and Google OAuth setup are optional and were not part of the timing.

## Test machine

| Item | Value |
|------|-------|
| GPU | NVIDIA RTX 3060 Laptop, 6 GB VRAM |
| CPU and RAM | 16 threads, 16 GB RAM (14 GB visible to the OS) |
| OS and Docker | Linux 7.3, Docker 28.5 |

## Limitations of the evaluation

- **Generated and fictional documents.** The 200 documents used for Objective 3 were generated from one template, and the 50 distinct documents describe one fictional company. Questions were written by the evaluator after reading the documents.
- **One machine, mostly one run per measurement.** Answers vary between runs.
- **No user test.** Usability (NFR06), task completion and uptime were not measured.
- **500 documents (NFR04)** were not tested; the largest corpus had 220 distinct documents.

## References

Numbers match the full list in [Related work](related-work.md#references).

[1] McKinsey Global Institute, "The social economy: Unlocking value and productivity through social technologies," McKinsey & Company, Jul. 2012. [Online]. Available: https://www.mckinsey.com/industries/technology-media-and-telecommunications/our-insights/the-social-economy (accessed Nov. 17, 2026).

[2] K. Park, "Samsung bans use of generative AI tools like ChatGPT after April internal data leak," TechCrunch, May 2, 2023. [Online]. Available: https://techcrunch.com/2023/05/02/samsung-bans-use-of-generative-ai-tools-like-chatgpt-after-april-internal-data-leak/ (accessed Nov. 17, 2026).
