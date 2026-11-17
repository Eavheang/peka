# Evaluation

Scripts, question sets and raw results behind the [final report](../docs/final-report.md), the [answer-quality evaluation](../docs/evaluation.md) and the offline and deployment tests in [Objectives and evaluation](../docs/project/objectives-and-evaluation.md). Every run used the minimum hardware (an RTX 3060 Laptop GPU with 6 GB VRAM and 16 GB RAM) and the local model unless its notes say otherwise.

## Test documents

The documents describe fictional companies and generic business topics. They were written with AI assistance and edited by hand to read like real company files, and they hold no real personal or company data. They are **not** in this repository; the team keeps them as zip archives, and they are included in the project submission package.

| Corpus | Documents | Used by |
|--------|-----------|---------|
| Real corpus (70 files) | 20 distinct documents, many saved in several formats: the 9 Mekong Harvest Foods files (a Markdown company profile, a DOCX handbook, XLSX budget and inventory tracker, a PPTX deck, a PDF supply agreement, a DOCX marketing plan, and TXT QC procedure and meeting minutes) plus general business documents such as a remote-work policy, a churn analysis, a database outage postmortem and a food-safety SOP | Runs up to 7 November 2026; the offline test used 2 Mekong files |
| Generated scale corpus | 200 documents from one template, made by `scale_corpus.py` with a fixed seed and inserted straight into the database | Objective 3 on 220 distinct documents |
| RevoluMark | 50 distinct documents of one marketing agency: 14 Markdown, 12 DOCX, 10 PDF, 8 XLSX, 6 PPTX | The 12 November 2026 run |

Because the 70-file corpus repeats the same content in different formats, results on it say more about format handling than about telling documents apart. The RevoluMark run is the one with distinct documents and reworded questions.

## Runs

| Folder or file | Date | What | Report |
|----------------|------|------|--------|
| `questions.jsonl` | 21 October 2026 | Question set 1 (74 questions over the real corpus, with expected file and heading) | [Answer-quality evaluation](../docs/evaluation.md) |
| `results/answers.jsonl` | Last updated 30 October 2026 | Answers to question set 2 on OKF pages, kept from the RAGAS and graded runs | [Answer-quality evaluation](../docs/evaluation.md) |
| `question-2.json` | 28 October 2026 | Question set 2 (67 questions: 59 answerable, 8 not) | [Answer-quality evaluation](../docs/evaluation.md) |
| `results-perf/*.json` (top level) | 30 October 2026 | First recall, latency and load runs, while OKF conversion still used the model | [Final report: how this changed](../docs/final-report.md#how-this-changed) |
| `results-perf/2026-11-07-source-text/` | 7 November 2026 | First run on original text with the reranker | [Answer-quality evaluation](../docs/evaluation.md#from-okf-pages-to-original-text) |
| `results-perf/2026-11-07-search-indexes/` | 7 November 2026 | HNSW and keyword index checks, with `measure.py` | `notes.md` in the folder |
| `results-perf/2026-11-07-final/` | 7 November 2026 | Final recall (220 documents), latency, load and graded answers | [Final report](../docs/final-report.md); `notes.md` in the folder |
| `revolumark/` | 12 November 2026 | 50 distinct documents: 160 main and 65 held-out questions, before (`*_baseline`) and after the fixes | [Final report: 50 distinct documents](../docs/final-report.md#evaluation-on-50-distinct-documents-2026-11-12) |
| `nfr-2026-11-17/` | 17 November 2026 | Deployment from a clean clone (NFR07) and upload, index and chat with no route out (NFR03) | [Objectives and evaluation](../docs/project/objectives-and-evaluation.md#nfr03-offline-operation) |

## Scripts

All scripts use the Python standard library except `ragas_eval.py`. None of them contains a credential: they read an admin account from the environment or from `service/.env`.

| Script | Does |
|--------|------|
| `perf_eval.py` | `answers`, `recall`, `ramp`, `latency` and `load` runs against `POST /search` and `POST /chat/stream`. Env: `PEKA_URL`, `PEKA_EMAIL`, `PEKA_PASSWORD`, `RESULTS_DIR` |
| `scale_corpus.py` | Adds or removes the 200 generated documents; run inside the index-worker container |
| `ragas_eval.py` | RAGAS scores with a judge model at `JUDGE_BASE_URL` (the only script that can call an outside service). `pip install -r requirements.txt` |
| `revolumark/run.py` | `search` or `chat` over the RevoluMark question sets |
| `revolumark/reindex.py` | Re-extracts every stored file and queues it; run inside the service container |
| `nfr-2026-11-17/deploy_test.sh` | Clones the repository, deploys an isolated Compose project and times each step |
| `nfr-2026-11-17/offline_check.py` | Run inside the service container on an `internal` network (`compose.offline.yaml`): tries outbound connections, uploads, waits for indexing, asks one question |

Point `RESULTS_DIR` at a new folder before running `perf_eval.py`, or it overwrites the files here. How to run each step is in [Reproducing the results](../docs/final-report.md#reproducing-the-results).

## Notes on the NFR run (17 November 2026)

- On the test host, port 8000 was taken by another project, so `deploy_test.sh` moves the development API port to 18000. It does not affect timing.
- The run's script linked the model before `config/model/` existed, so Docker created an empty folder and llama failed until the model was put in by hand. The published script now creates the folder first.
- The first `bun install` left the web client incomplete (defect D-27) and was fixed by reinstalling with `--force`. Both fixes are inside the 316 s total in `deploy.log`.
