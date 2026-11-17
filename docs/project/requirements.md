# Requirements

The approved requirements of PEKA, their priority and their final status, with the evidence for each. Requirement IDs come from the Review 1 document (27 August 2026) and never change. Features built after Review 1 are either folded into the requirement they belong to or given a new ID from FR17 on, marked **added**.

Status is checked against the code on `main` at commit `4a08cd9` (12 November 2026). Test names refer to `service/tests/`; test case IDs (TC-xx) are listed in [Testing](testing.md).

| Status | Meaning |
|--------|---------|
| **Completed** | Built, integrated and covered by automated tests or a recorded evaluation |
| **Partly completed** | Part of the requirement is built, or it is built but only partly verified |
| **Withdrawn** | Built, then removed on evidence; the reason is recorded in [Scope changes](scope-changes.md) |
| **Not done** | Not built or not measured |

## Stakeholders and users

| Stakeholder | Interest |
|-------------|----------|
| Employees (staff) | Fast answers from company documents, with sources they can check |
| Senior staff and managers | The same, including confidential documents |
| System administrators | Simple setup, user and document management, provider settings, audit records |
| IT and compliance officers | Documents and AI processing stay on the organization's own hardware |
| Executive leadership, donors and funders (NGOs) | Lower risk of data exposure and no recurring AI fees |

The target organizations are small and medium-sized enterprises (SMEs) and non-governmental organizations (NGOs).

## How the requirements were gathered

| Method | Used for | Source |
|--------|----------|--------|
| Secondary evidence | The productivity problem and the data-leak risk | McKinsey Global Institute (2012) on time spent searching for information; the 2023 Samsung restriction of generative AI tools after sensitive internal data was leaked to ChatGPT. See [Related work](related-work.md#references) |
| Existing-system analysis | Features that cloud and local assistants offer or lack | [Related work](related-work.md) |
| Domain analysis | Supported formats, access levels and the citation requirement | Typical SME and NGO document repositories: policies, procedures, reports, spreadsheets and slide decks |
| Supervisor reviews | Scope decisions and corrections | Review 0 (July), Review 1 (August) and Review 2 (October 2026); see [Methodology and timeline](methodology-and-timeline.md#reviews) |
| Evaluation runs | Changes to search, chunking and refusal | [Final report](../final-report.md) and [Answer-quality evaluation](../evaluation.md) |

## Roles and permissions

Three roles are enforced by the API and by a database `CHECK` constraint. Every document has an access level, `general` or `confidential`, set when it is uploaded.

| Role | General documents | Confidential documents | Upload | Administration |
|------|-------------------|------------------------|--------|----------------|
| `admin` | Yes | Yes | General and confidential | Users and invitations, document access levels, provider settings, audit log |
| `senior` | Yes | Yes | General only | No (403) |
| `staff` | Yes | No | General only | No (403) |

The role filter is applied inside the search SQL, so a document above the user's clearance is never retrieved, sent to the model or cited. See [Security](../security.md).

## Functional requirements

| ID | Requirement | Priority | Status | Evidence |
|----|-------------|----------|--------|----------|
| FR01 | Authorized users sign in with email and password, and can change their display name and password | Must | Completed | `test_auth_api`, `test_auth_security`; TC-01, TC-02, TC-05 |
| FR02 | Bring documents in from a designated Google Drive source | Should | Partly completed | One-off import of picked files through Google sign-in and the Google Picker (scope `drive.file`), since 6 October 2026. Automatic sync of later changes is not built (issue #102). `test_google_drive_api` (6 tests); TC-25, TC-26 |
| FR03 | Upload documents manually (several files at once) | Should | Completed | Knowledge library upload and `POST /files`; TC-09, TC-11 |
| FR04 | Extract text and metadata from PDF, DOCX, XLSX and PPTX, plus Markdown and plain text | Must | Completed | `test_extractor` (10 tests), including tables, DOCX headers, footers and footnotes, and PPTX speaker notes. Image-only (scanned) PDFs are not supported; OCR is out of scope. TC-27 |
| FR05 | Convert extracted content into the Open Knowledge Format (OKF: YAML front matter and Markdown) | Must | **Withdrawn** | Built in August 2026 and removed on 7 November 2026 after evaluation. Replaced by indexing the original extracted text. See [Scope changes](scope-changes.md#okf-conversion-withdrawn) |
| FR06 | Chunk documents, embed the chunks and index them for search | Must | Completed | Heading-aware chunker (`test_okf_chunker`, 29 tests), local embeddings, pgvector HNSW index and a keyword (`tsvector`) index. Includes hybrid keyword and vector search and a local cross-encoder **reranker** (added November 2026). TC-28, TC-29 |
| FR07 | Answer natural-language questions with the local language model | Must | Completed | Streaming chat with history and stop, one model call per first question, and **no-evidence refusal** (added November 2026). `test_chat` (105 tests); evaluation: 145 of 151 and 57 of 60 correct. TC-18 to TC-20, TC-30, TC-31 |
| FR08 | Include citations (document title, section heading, page or slide) with every generated answer | Must | Completed | Citations are built by the server from search results. 211 of 211 answers to answerable questions carried a citation on 12 November 2026. TC-18, TC-32 |
| FR09 | Admins view, delete and re-index documents and set their access level | Should | Completed | Knowledge library table (retry, delete, download, access level); outdated files are re-indexed automatically when the chunker changes. TC-12, TC-13, TC-33 |
| FR10 | Log indexing activity, user queries and system events for audit | Should | Completed | `audit_events` table and the admin **Audit log** page (added October 2026); prompts and answers are not stored. `test_audit_api`, `test_audit_writers_database`; TC-34 |
| FR11 | Refresh sessions with rotating refresh tokens; logout invalidates tokens | Must | Completed | `test_refresh` (12 tests); TC-03, TC-24 |
| FR12 | Admins manage user accounts: invite, list, change role, activate or deactivate, delete | Must | Completed | Accounts are created only through email invitations (changed in September 2026). `test_invitations` (25 tests); TC-06 to TC-08, TC-21, TC-22 |
| FR13 | Restrict search and chat results to documents the user's role may see | Must | Completed | Role filter in the search SQL; `test_search_database` runs it on a real PostgreSQL with pgvector (30 tests). TC-14, TC-23 |
| FR14 | Reject duplicate documents by content hash | Should | Completed | Unique SHA-256 per file; TC-10 |
| FR15 | Configure the language model endpoint (local llama.cpp or any OpenAI-compatible endpoint) without re-embedding documents | Must | Completed | `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, plus the admin **provider settings** page with a connection test. Configuration is unit-tested (`test_llm_config`); switching to a hosted provider was exercised by hand for the Review 2 demonstration |
| FR16 | Build a new index in the background without blocking chat, and switch to it only when the whole job succeeds | Must | Completed | Versioned chunk sets; `test_a_failed_swap_keeps_the_active_set_and_every_chunk` on a real database, `test_embed_failure_leaves_old_chunks_intact`; TC-15 |
| FR17 | Users can opt in to public web search for a question | Could | Completed, **added** | Off by default; needs an Exa API key. It is the only chat feature that leaves the machine. `test_web_search` (5 tests) |
| FR18 | Users can regenerate the last answer | Could | Completed, **added** | `test_chat_stream_regenerate_replays_last_question_and_replaces_pair`, `test_regenerate_conflict_is_a_409_on_both_endpoints`; TC-35 |
| FR19 | Users can open the cited section of a source document from an answer | Should | Completed, **added** | `POST /chat/source-preview`, subject to the user's current access; `test_source_preview` (6 tests) |
| FR20 | Extra chats wait for a free model slot instead of failing when the model is busy | Must | Completed, **added** | Two answers are generated at a time and the rest queue; `test_third_simultaneous_chat_waits_then_answers` (TC-36); load test in the [final report](../final-report.md#nfr04-concurrent-users-and-indexing) |
| FR21 | Users can choose a color theme | Could | Completed, **added** | Four themes (Clay, Daylight, Sage, Midnight) under Account settings, saved per browser; checked by hand, no automated test |

## Non-functional requirements

NFR02 and NFR04 are the versions refined in the Review 1 document. The proposal's original performance target is kept as Objective 5 in [Objectives and evaluation](objectives-and-evaluation.md).

| ID | Category | Requirement | Measurement | Priority | Status |
|----|----------|-------------|-------------|----------|--------|
| NFR01 | Security | Functions restricted by role; passwords hashed with Argon2; all JWT claims validated | Access-control and token tests | Must | Completed |
| NFR02 | Performance | Time to first token under 10 s in local mode for standard questions, warm model | Response-time test | Must | Completed: 4.9 s median, 7.5 s p95 |
| NFR03 | Offline operation | No call to an external AI API in local mode; only the opt-in features leave the machine | Network test | Must | See [Objectives and evaluation](objectives-and-evaluation.md#nfr03-offline-operation) |
| NFR04 | Scalability and concurrency | 500 indexed documents and about 10 concurrent chat users without response-time degradation, also while indexing | Load test | Should | Partly completed: 20 of 20 answered with 10 users, but slower; tested on 220 documents |
| NFR05 | Hardware | Runs on commodity hardware: 16 GB RAM, 6 GB VRAM for the local model | Compatibility test | Should | Completed: every evaluation ran on an RTX 3060 Laptop GPU (6 GB) with 16 GB RAM |
| NFR06 | Usability | Representative users complete the core task with minimal guidance | User test | Should | Not done |
| NFR07 | Deployability | Deployable from scratch within 30 minutes with Docker Compose | Deployment test | Should | See [Objectives and evaluation](objectives-and-evaluation.md#nfr07-deployment-time) |

## User stories and acceptance criteria

| ID | User story | Acceptance criteria | Requirements | Result |
|----|------------|---------------------|--------------|--------|
| US-01 | As an employee, I want to sign in with my email and password so that only authorized staff use the assistant | Valid credentials open the workspace; invalid credentials show one generic error; a deactivated account cannot sign in | FR01, NFR01 | Met (TC-01, TC-02, TC-05) |
| US-02 | As an employee, I want to ask a question in plain language and get an answer with citations so that I can check the source | Answers come only from retrieved passages; each answer lists citations with title, heading and page; with no relevant content the system says it cannot answer from the documents | FR07, FR08 | Met (TC-18, TC-30, evaluation) |
| US-03 | As an admin, I want to upload documents so that they become searchable | Supported files upload; a duplicate is rejected; each file's status reaches "Indexed" | FR03, FR04, FR06, FR14 | Met (TC-09 to TC-11, TC-27) |
| US-04 | As an admin, I want failed indexing to be visible and retryable so that no document silently disappears | A failed job keeps its error and attempt count; retry queues it again; status is shown per file | FR09, FR16 | Met (TC-16, TC-33) |
| US-05 | As an admin, I want to set a document's access level so that sensitive files reach only senior staff | After a change, a staff user's search and chat stop or start returning that document, with no other step | FR13 | Met (TC-14, TC-23) |
| US-06 | As an admin, I want to invite and deactivate users so that access follows employment | An invited user signs in with the assigned role; deactivation blocks new requests even with an issued token | FR12, NFR01 | Met (TC-04 to TC-07, TC-21) |
| US-07 | As a compliance officer, I want all AI processing to stay on local infrastructure so that confidential data never leaves the organization | With outside network access cut, upload, indexing, search and chat still work in local mode | NFR03 | See [NFR03](objectives-and-evaluation.md#nfr03-offline-operation) |
| US-08 | As an employee, I want my session to continue securely so that I am not signed out mid-task | The access token refreshes through the refresh token; logout invalidates both | FR11 | Met (TC-03, TC-24) |

## Scope

**In scope:** manual upload and one-off Google Drive import; PDF, DOCX, XLSX, PPTX, Markdown and plain text; local embeddings, reranking and search; a local language model by default, with an optional OpenAI-compatible endpoint; role-filtered retrieval; citations; invitations and three roles; audit log; Docker Compose deployment on one machine.

**Out of scope:** training or fine-tuning a model; autonomous agents; voice and image generation; languages other than English; OCR for scanned documents; automatic Google Drive sync (future work); multi-tenant hosting. Web search, listed as an exclusion in the proposal, was added as an opt-in feature (FR17); see [Scope changes](scope-changes.md).
