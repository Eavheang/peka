# Methodology and timeline

How the project was run from 13 July to 7 November 2026, the reviews it passed, and how quality and risk were controlled. Dates come from the review documents and the git history of `Eavheang/peka`.

> **To be updated:** the sprint dates and phase plan will be filled in from the team's One-Page Project Management (OPPM) sheet.

## Approach

The proposal chose Agile Scrum adapted for a two-person team, with the supervisor as product owner:

| Element | Plan |
|---------|------|
| Sprint length | 2 weeks |
| Planning | At the start of each sprint, from a prioritized backlog (Must and Should requirements) |
| Check-ins | Informal, between the two developers |
| Review | Supervisor feedback at each review milestone |
| Definition of done | Committed, documented, passing its automated tests and shown to the other student; backend work is done only when the web client uses it or an API test covers it |

The team had two roles: a **backend and RAG lead** (service, indexing, search, chat, evaluation) and a **frontend and integration lead** (web client, design, invitations, integration). Both shared planning, code review, deployment and documentation.

### How work flowed

1. A feature or fix starts on a branch named after it (`feat/…`, `fix/…`, `task/…`).
2. Commits follow `[TASK]`, `[FEATURE]`, `[IMP]` or `[BUGFIX]` prefixes.
3. Local hooks (Husky) run the backend tests, or the frontend lint, type check and format, before a commit or push touches that part. See [Development](../development.md).
4. A pull request to `main` runs GitHub Actions: pytest on Python 3.12 with a PostgreSQL and pgvector service, and the frontend type check and lint.
5. The pull request is reviewed and merged. Larger changes and investigations are tracked as GitHub issues.
6. Changes to search, chunking or chat are checked with an evaluation run before and after (see [Final report](../final-report.md)).

Activity on `main`, counted from git on 17 November 2026:

| Month (2026) | Commits (not merges) | Merged pull requests |
|--------------|----------------------|----------------------|
| July | 13 | 5 |
| August | 28 | 25 |
| September | 43 | 40 |
| October | 26 | 19 |
| November | 23 | 15 |
| **Total** | **133** | **104** |

## Timeline

| Period | Work | Evidence |
|--------|------|----------|
| 13 to 26 July | Proposal, repository and Docker skeleton; first commit 16 July | Review 0 proposal |
| 23 July | **Review 0 outcome:** approved with minor modification | Supervisor email |
| Late July to August | Upload with SHA-256 duplicate check, extraction, OKF conversion, chunking, embeddings in pgvector, role-based access, versioned chunk sets, chat with citations and refusal (23 August); architecture decision record (21 August) | Commits 28 July to 26 August |
| 26 August | Web client sign-in and upload | Commits |
| 27 August | **Review 1:** requirements, design and prototype | Review 1 document |
| September | Chat streaming and history, source preview, opt-in web search, provider settings, invitations, real-database search tests (159 tests) | Commits 14 to 30 September |
| 1 October | **Review 2:** core development and interim testing; 65% verified completion | Review 2 document |
| October | Audit log (2 October), theme selection, Google Drive import (6 October), chat regenerate (7 October), evaluation scripts and the 70-file evaluation (21 to 28 October), first final report (30 October) | Commits, PRs #73 to #93 |
| 7 November | Chat queue, prompt budget, refusal, reranker, original-text indexing; OKF withdrawn; final evaluation re-run | Issues #95 to #101, PRs #105 to #108 |
| 9 to 12 November | Citation matching, security fixes (image exfiltration, exposed ports), re-indexing that keeps old citations, the 50-document evaluation and its fixes | Issues #115 to #125, PRs #112 to #128 |
| 17 November | Offline and deployment tests; documentation aligned with the thesis | This folder |
| 20 November | Thesis submission | |
| 26 November | Final presentation and live demonstration | |

The proposal planned the work in seven phases over 17 weeks. The order changed after Review 0: the document-to-answer path was built first and Google Drive sync was deferred, so phases 2 to 4 (ingestion, indexing, RAG engine) finished in August, ahead of plan, and the evaluation phase moved to late October and November.

## Reviews

| Review | Date | Outcome | What changed |
|--------|------|---------|--------------|
| Review 0 (proposal) | Submitted 15 July, outcome 23 July 2026 | Approved with minor modification | Strengthen the distinctive features (local processing, document standardization, controlled sync, privacy, verifiable citations); build the complete core workflow before dashboards. Drive sync was deferred and the core path built first |
| Review 1 (requirements, design and prototype) | 27 August 2026 | Satisfactory with corrections | The slides still named LanceDB and Gemma 3; every later document uses PostgreSQL with pgvector and Gemma 4, and requirement status was refreshed from the code |
| Review 2 (core development and interim testing) | 1 October 2026 | Proceed with development and finish the test cases | Scope changes accepted (hosted model option, web search, Drive import, invitations). Tests grew from 159 to 328, and the evaluation runs measured the objectives |

## Quality controls

| Control | Where |
|---------|-------|
| Automated tests on every pull request | GitHub Actions; 328 backend tests on 12 November 2026 |
| Real-database tests for the role filter | `test_search_database.py` in CI |
| Pre-commit and pre-push hooks | Husky (`.husky/`) |
| Schema changes only through reviewed migrations | Alembic, 23 migration files (002 to 024) |
| Evaluation before and after retrieval changes | [Final report](../final-report.md), [Answer-quality evaluation](../evaluation.md) |
| Defects tracked to a fix and a retest | [Testing: defects](testing.md#defects) |
| Requirement status checked against the code | [Requirements](requirements.md) |

## Risks

The risk register from Review 2, with the final status.

| ID | Risk | Impact | Mitigation | Final status |
|----|------|--------|------------|--------------|
| R-01 | Local model output unstable or slow on commodity hardware | High | JSON repair and retry; chat queue; prompt budget; provider configurable | Mitigated: 20 of 20 answered under load; first token 4.9 s median |
| R-02 | The full upload, index and search pipeline not tested end to end | Medium | Real-database search tests; system evaluation runs | Mitigated by the system runs; not automated in CI |
| R-03 | Scope creep (Drive sync, extra features) | Medium | Drive sync deferred; features frozen for the thesis | Controlled: Drive import only; sync is future work |
| R-04 | Time before 7 November with thesis writing | Medium | Weekly plan; documentation split between the students | Evaluation and fixes ran to 12 November |
| R-05 | One student's work under-represented in commit counts | Medium | Pull requests, review comments and design work recorded | Addressed in the thesis contribution record, which is not part of this repository |
| R-06 | The demonstration depends on local containers and the model | High | Rehearsal on the demo machine; screenshots and a recording as fallback | Open until the final presentation |

Earlier risks from the proposal: insufficient hardware (closed: the quantized model runs on a 6 GB GPU), Google Drive API complexity (closed by deferring sync), poor parsing of complex PDFs (partly mitigated: tables and headings handled; scanned PDFs out of scope), and dependency conflicts (mitigated: no orchestration framework, pinned images, CI).

## Data and ethics

- The test documents describe fictional companies, such as Mekong Harvest Foods and RevoluMark, and generic business topics. They were written with AI assistance and edited by hand to read like real company documents, and they contain no real personal or company data. They are kept out of the public repository and included in the submission package; see [`eval/`](../../eval/README.md).
- The evaluation uses an admin account on a local test stack; no real users' data was collected by the system.
- The repository holds no secrets: environment files are created from examples with generated passwords (issue #109).
