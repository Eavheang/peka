# Testing

How PEKA was tested, the test cases traced to requirements, and the defect log. Answer quality, recall, latency and load are measured separately in the [final report](../final-report.md); the offline and deployment tests are in [Objectives and evaluation](objectives-and-evaluation.md).

## Strategy

| Level | What | Where | How it runs |
|-------|------|-------|-------------|
| Unit and API | Business rules, validation, auth, chat logic, extraction and chunking. Requests go through the FastAPI routes; the language model, embedding and reranking servers are replaced by fakes | `service/tests/` (pytest) | Every pull request, GitHub Actions `backend.yml` |
| Database integration | The search SQL, role filter, chunk-set swap, audit writers and citation triggers on a real PostgreSQL with pgvector | `test_search_database.py`, `test_audit_writers_database.py` | In CI with a Postgres service; skipped locally without `TEST_DATABASE_URL` |
| Frontend unit | Citation matching and safe Markdown rendering | `webclient/utils/*.test.ts` (Bun) | `bun test`; the frontend CI runs type checking and lint |
| System | Upload, index and answer on the real stack with the local model; recall, answer quality, latency, concurrency | `eval/` scripts against the running API | By hand, on the test machine |
| Acceptance | The Review 2 demonstration workflows (invite, upload, ask, access control) | Running web client | By hand at each review |
| Non-functional | Offline operation (NFR03) and deployment time (NFR07) | Isolated Compose project | By hand, 17 November 2026 |

Fakes keep the unit tests fast and repeatable; the system runs cover what fakes cannot (model behavior, real retrieval quality and speed).

## Test inventory

Counted on `main` at commit `4a08cd9`. The backend run in CI on 12 November 2026 (Python 3.12, pytest 9.2) ended with **328 passed**, 0 failed, 0 skipped. The frontend tests (Bun 1.4) ended with **9 passed** on 17 November 2026.

| Test file | Tests | Covers |
|-----------|-------|--------|
| `test_chat.py` | 105 | Answers, citations, streaming, stop, regenerate, history budget, refusal, chat queue |
| `test_search_database.py` | 30 | Role filter, hybrid search, format copies, re-index and kept citations, on real Postgres |
| `test_okf_chunker.py` | 29 | Chunking by headings, tables and size (name kept from the OKF period) |
| `test_invitations.py` | 25 | Create, look up, accept, resend, revoke, expiry, token hashing, email escaping |
| `test_ai_runtime.py` | 22 | Model calls, retries, JSON repair, context-overflow handling |
| `test_search.py` | 19 | Reranking, fallbacks, role mapping, search endpoint auth |
| `test_auth_api.py` | 12 | Login, tokens, roles, activation, password change |
| `test_refresh.py` | 12 | Refresh-token rotation and rejection |
| `test_extractor.py` | 10 | Every format; tables, headers, footnotes, speaker notes |
| `test_files_api.py` | 8 | Upload, list, download, access levels, unsupported, oversized and duplicate files |
| `test_audit_api.py` | 7 | Audit list, filters, pagination, fail-open recording |
| `test_database_schema.py` | 7 | Columns and `CHECK` constraints |
| `test_auth_security.py` | 6 | Token forgery, expiry, type confusion, revocation, role escalation |
| `test_audit_writers_database.py` | 6 | Audit rows on real Postgres; regenerate safety |
| `test_google_drive_api.py` | 6 | Google sign-in, forged state, picker, import, confidential rule |
| `test_source_preview.py` | 6 | Permission-aware source preview |
| `test_web_search.py` | 5 | Opt-in web search |
| `test_index_worker.py` | 4 | Indexing, failures, old chunks kept on failure, re-extraction |
| `test_bootstrap.py`, `test_worker_lifespan.py` | 3 each | First admin, worker start and stop |
| `test_embeddings.py`, `test_health.py`, `test_llm_config.py` | 1 each | Embedding client, health, model settings |
| **Backend total** | **328** | |
| `webclient/utils/*.test.ts` | 9 | Citation excerpt matching; images and raw HTML dropped from answers |

**Not automated:** the full upload, index and answer pipeline with real models (covered by the system runs), the web client pages (no component or end-to-end tests), and usability.

## Test cases

TC-01 to TC-24 are the Review 2 test cases (30 September 2026). TC-25 onwards were added for the final system. "Pass" means the named test passed in the CI run of 12 November 2026.

| ID | Requirement | Input | Expected | Actual | Status | Evidence |
|----|-------------|-------|----------|--------|--------|----------|
| TC-01 | FR01 | Valid credentials, then `GET /auth/me` | 200; role claim matches the account | As expected | Pass | `test_login_and_me_assert_role_claim` |
| TC-02 | FR01, NFR01 | Wrong password; unknown email | The same generic error for both | As expected | Pass | `test_login_rejects_unknown_and_wrong_credentials_generically` |
| TC-03 | FR11 | Logout, then `GET /auth/me` with the old token | 204, then 401 | 204, 401 | Pass | `test_logout_revokes_the_token` |
| TC-04 | NFR01 | Missing, invalid or old-version token | 401 | As expected | Pass | `test_auth_rejects_missing_invalid_and_version_mismatch` |
| TC-05 | FR12 | A deactivated user signs in | Sign-in fails | As expected | Pass | `test_inactive_user_cannot_login` |
| TC-06 | NFR01, FR12 | A senior user calls invite, deactivate and delete | 403 for each | 403 each | Pass | `test_senior_cannot_use_admin_endpoints` |
| TC-07 | FR12 | Admin calls the removed `POST /auth/users` | 405; users only via invitations | 405 | Pass | `test_users_can_only_be_added_through_invitations` |
| TC-08 | FR12 | Admin demotes their own account | 409 | 409 | Pass | `test_admin_can_change_role_and_cannot_demote_self` |
| TC-09 | FR03 | Upload `image/png` | 415; nothing saved | 415, nothing saved | Pass | `test_upload_rejects_unsupported_files_without_saving` |
| TC-10 | FR14 | Upload identical bytes twice | 409; nothing saved | 409, nothing saved | Pass | `test_upload_rejects_duplicate_content` |
| TC-11 | FR03 | Upload above the size limit | 413; nothing saved | 413, nothing saved | Pass | `test_upload_rejects_oversized_files_without_saving` |
| TC-12 | FR13 | Staff lists files | Confidential files hidden | Hidden | Pass | `test_list_hides_confidential_files_from_staff` |
| TC-13 | FR13 | Staff downloads a confidential file | Not available | As expected | Pass | `test_download_hides_confidential_files_from_staff` |
| TC-14 | FR13 | Access levels for staff, senior and admin | Staff: general; others: both | As expected | Pass | `test_staff_cannot_see_confidential`, `test_search_knowledge_applies_the_role_mapping_end_to_end` |
| TC-15 | FR16 | The embedding call fails while a file is re-indexed | Old chunks intact; new set not activated | Intact | Pass | `test_embed_failure_leaves_old_chunks_intact`, `test_a_failed_swap_keeps_the_active_set_and_every_chunk` |
| TC-16 | FR05 | OKF conversion fails three times | Job failed, error kept | — | **Retired** | OKF was withdrawn on 7 November 2026; failure handling is now covered by TC-33 |
| TC-17 | FR05 | OKF output path outside the knowledge base | Rejected | — | **Retired** | Withdrawn with OKF |
| TC-18 | FR07, FR08 | Question with retrieved sources | Answer with a citation (title, page, file id) | As expected | Pass | `test_grounded_answer_carries_citations` |
| TC-19 | FR07 | Blank question; 4,001-character question | 422 before the model is called | 422 | Pass | `test_question_length_is_rejected_before_answering` |
| TC-20 | FR07 | The model returns invalid structured output | Fails closed with a model error | As expected | Pass | `test_invalid_structured_answer_fails_closed` |
| TC-21 | FR12 | Accept an invite with a bad token, during a race, with a short password | 404, 409, 422 | 404, 409, 422 | Pass | `test_accept_rejects_bad_token_short_password_and_email_race` |
| TC-22 | FR12 | Untrusted values in the invitation email | HTML-escaped | Escaped | Pass | `test_invitation_html_escapes_untrusted_values` |
| TC-23 | FR13 | Role-filtered search on real PostgreSQL with pgvector | Staff get no confidential chunk, even when it is closer | As expected | Pass | `test_general_only_search_never_returns_the_closer_confidential_chunk` |
| TC-24 | FR11 | `POST /auth/refresh` with valid, invalid, revoked and wrong-type tokens | New tokens for a valid one; 401 otherwise | As expected | Pass | `test_refresh.py` (12 tests) |
| TC-25 | FR02 | Start Google sign-in without login or configuration; callback with a forged state | Refused; forged state rejected | As expected | Pass | `test_connect_requires_login_and_configuration`, `test_callback_rejects_forged_state` |
| TC-26 | FR02, FR13 | Import Google Docs; staff imports a confidential file | Docs exported to Office formats and stored; staff refused (403) | As expected | Pass | `test_import_exports_google_docs_and_stores_files`, `test_staff_cannot_import_confidential` |
| TC-27 | FR04 | One file of every supported format; DOCX headers and footnotes; PPTX speaker notes | Text extracted with its locations | As expected | Pass | `test_upload_extraction_supports_every_format`, `test_docx_headers_footers_and_footnotes_become_their_own_chunks`, `test_pptx_grouped_shapes_and_speaker_notes_are_extracted` |
| TC-28 | FR06 | A query whose words match a chunk that vector search misses | The keyword search finds it | As expected | Pass | `test_keyword_match_finds_a_chunk_the_vector_search_misses` |
| TC-29 | FR06, FR13 | Rerank results for a staff user | The reranker only receives rows the role may see | As expected | Pass | `test_reranker_only_receives_rows_the_role_may_see` |
| TC-30 | FR07 | A question about company facts when search finds nothing | Refused without an answer call | As expected | Pass | `test_document_question_without_results_is_refused_without_an_answer_call` |
| TC-31 | FR07, FR08 | Weak evidence and an answer that cites nothing | Replaced by a clarifying question | As expected | Pass | `test_weak_evidence_answer_that_cites_nothing_becomes_the_clarifying_question` |
| TC-32 | FR08 | The model names no source although results were relevant | Citations attached without another model call | As expected | Pass | `test_uncited_answer_gets_citations_without_another_model_call` |
| TC-33 | FR09, FR16 | A file with no extractable text; files indexed by an older chunker | Job fails with a clear error; outdated files queued again | As expected | Pass | `test_extraction_without_text_fails_the_job_clearly`, `test_files_indexed_by_an_older_chunker_are_queued_again` |
| TC-34 | FR10 | Staff lists audit events; admin lists after login, chat and a denied request | Staff 403; admin sees each event; recording never blocks | As expected | Pass | `test_staff_cannot_list_audit_events`, `test_admin_list_includes_sync_query_login_and_admin_deny`, `test_record_is_fail_open` |
| TC-35 | FR18 | Regenerate the last answer; regenerate after another turn was added | Pair replaced; 409 when it is no longer last | As expected | Pass | `test_chat_stream_regenerate_replays_last_question_and_replaces_pair`, `test_regenerate_never_deletes_a_turn_added_while_it_ran` |
| TC-36 | FR20 | Three chats at once with two model slots | The third waits, then answers | As expected | Pass | `test_third_simultaneous_chat_waits_then_answers` |
| TC-37 | NFR01 | An answer containing Markdown, reference-style and HTML images | Images dropped; links send no Referer | As expected | Pass | `webclient/utils` Bun tests |
| TC-38 | FR13 | Change a file to confidential | Hidden from staff at once | As expected | Pass | `test_changing_a_file_to_confidential_hides_it_from_staff_immediately` |
| TC-39 | FR08, FR16 | Open a citation after its file was re-indexed | The cited passage still opens | As expected | Pass | `test_a_cited_chunk_still_opens_after_its_file_is_re_indexed` |
| TC-40 | FR07 | A long history and question | Both fit one character budget; an oversize message is cut, not dropped | As expected | Pass | `test_history_and_question_share_one_character_budget`, `test_message_that_overflows_the_budget_is_cut_not_dropped` |
| TC-41 | NFR03 | Upload, index and chat with no route outside the host | Works; outbound connections fail | As expected | Pass | [NFR03](objectives-and-evaluation.md#nfr03-offline-operation), 17 Nov 2026 |
| TC-42 | NFR07 | Deploy from a clean clone | Signed in within 30 minutes | 5 min 16 s, with defect D-27 | Pass | [NFR07](objectives-and-evaluation.md#nfr07-deployment-time), 17 Nov 2026 |

**Summary:** 42 test cases; 40 passed, 2 retired with OKF, 0 failed, 0 not run.

## Traceability

Each requirement, the design and code that implement it, and the tests that check it.

| Requirement | Design | Module | Tests |
|-------------|--------|--------|-------|
| FR01 | [Security](../security.md) | `app/auth/` | TC-01, TC-02, TC-05 |
| FR02 | [Design: components](design.md#components) | `app/google_drive/` | TC-25, TC-26 |
| FR03 | [Indexing](../architecture/indexing.md) | `app/files/` | TC-09, TC-11 |
| FR04 | [Indexing: extraction](../architecture/indexing.md#extraction) | `app/engine/source_extractor.py` | TC-27 |
| FR05 | — | Removed | TC-16, TC-17 retired |
| FR06 | [Indexing: chunking](../architecture/indexing.md#chunking-for-retrieval), [Chat and RAG](../architecture/chat-and-rag.md#knowledge-base-search) | `app/engine/chunks/`, `app/engine/search/` | TC-28, TC-29 |
| FR07 | [Chat and RAG](../architecture/chat-and-rag.md) | `app/chat/` | TC-18 to TC-20, TC-30, TC-31, TC-40 |
| FR08 | [Chat and RAG: citations](../architecture/chat-and-rag.md#citation-assembly) | `app/chat/` | TC-18, TC-32, TC-39 |
| FR09 | [Indexing: re-indexing](../architecture/indexing.md#re-indexing-existing-files) | `app/files/`, `app/engine/indexing/` | TC-33 |
| FR10 | [Security: audit log](../security.md#audit-log-fr10--d-02) | `app/audit/` | TC-34 |
| FR11 | [Security](../security.md) | `app/auth/` | TC-03, TC-24 |
| FR12 | [Security](../security.md) | `app/auth/` | TC-05 to TC-08, TC-21, TC-22 |
| FR13 | [Design: search](design.md#chat-sequence), [Security: document ACL](../security.md#document-acl) | `app/engine/search/repository.py` | TC-12 to TC-14, TC-23, TC-26, TC-29, TC-38 |
| FR14 | [Data model](../service/data-model.md) | `app/files/` | TC-10 |
| FR15 | [Config](../config/README.md) | `app/workspace_settings.py` | `test_llm_config` |
| FR16 | [Indexing: chunk sets](../architecture/indexing.md#embeddings-and-chunk-sets) | `app/engine/chunks/` | TC-15, TC-33, TC-39 |
| FR17 | [Chat and RAG: web search](../architecture/chat-and-rag.md#web-search) | `app/engine/web_search/` | `test_web_search` |
| FR18 | [Flows](../architecture/flows.md) | `app/chat/` | TC-35 |
| FR19 | [Chat and RAG: source preview](../architecture/chat-and-rag.md#source-preview) | `app/chat/` | `test_source_preview` |
| FR20 | [Final report: load](../final-report.md#nfr04-concurrent-users-and-indexing) | `app/chat/` | TC-36 |
| FR21 | [Web client](../webclient/README.md) | `webclient/` | Checked by hand |
| NFR01 | [Security](../security.md) | `app/auth/`, `webclient/` | TC-02, TC-04, TC-06, TC-37 |
| NFR02 | [Final report](../final-report.md#objective-5--nfr02-latency-and-time-to-first-token) | — | Latency run, 7 Nov 2026 |
| NFR03 | [Objectives and evaluation](objectives-and-evaluation.md#nfr03-offline-operation) | `config/compose.yaml` | TC-41 |
| NFR04 | [Final report](../final-report.md#nfr04-concurrent-users-and-indexing) | `app/chat/` | Load run, 7 Nov 2026 |
| NFR05 | [System requirements](../system-requirements.md) | — | Every evaluation run |
| NFR06 | — | — | Not run |
| NFR07 | [Objectives and evaluation](objectives-and-evaluation.md#nfr07-deployment-time) | `config/Makefile` | TC-42 |

## Defects

D-01 to D-09 come from Review 2. Later defects come from GitHub issues, bugfix pull requests and the final tests. Severity is the team's own judgement. Fixes were made by Eavheang Oeng unless noted.

| ID | Found | Defect | Severity | Fix and retest | Status |
|----|-------|--------|----------|----------------|--------|
| D-01 | Sep 2026 | The role filter in SQL was only tested against a mocked database | High | PR #70: real-database tests in CI; weakening the filter fails 6 of them | Fixed |
| D-02 | Sep 2026 | No query or audit log (FR10) | Medium | PR #73: `audit_events` and the admin audit page; TC-34 | Fixed |
| D-03 | Sep 2026 | Performance, offline and usability targets not measured | Medium | Latency, load and recall measured 30 Oct and 7 Nov; offline and deployment 17 Nov. Usability still not measured | Partly fixed |
| D-04 | Sep 2026 | The model could return malformed JSON | Medium | Repair and one retry (PRs #64, #65); TC-20 | Mitigated |
| D-05 | Sep 2026 | No frontend or end-to-end tests | Medium | 9 Bun unit tests added; no component or end-to-end tests | Partly fixed |
| D-06 | Sep 2026 | An empty search answered without citations, unlike the refusal described in Review 1 | Low | Server-side refusal (#101, PR #107); TC-30 | Fixed |
| D-07 | Sep 2026 | No test for the refresh endpoint | Low | PR #69: 12 refresh tests; TC-24 | Fixed |
| D-08 | Sep 2026 | The upload error toast showed "Request failed with status code 409" | Low | PR #67: the server's message is shown | Fixed |
| D-09 | Sep 2026 | An unknown chat URL showed "Loading conversation…" forever | Low | PR #68: "Conversation not found" | Fixed |
| D-10 | 7 Oct 2026 | Regenerate deleted whichever pair was newest, so a turn sent from another tab was lost | Medium | PR #82: the request pins the pair it replaces; TC-35 | Fixed |
| D-11 | 27 Oct 2026 | On a fresh volume, `make setup` ran migrations before Postgres accepted TCP connections | Medium | PR #89: readiness checked over TCP | Fixed |
| D-12 | 27 Oct 2026 | OKF pages of copies of a report overwrote each other (70 files gave 31 pages) | High | PR #88; later moot when OKF was withdrawn | Fixed, then removed |
| D-13 | 28 Oct 2026 | Long OKF pages were cut off and failed as invalid JSON | Medium | PR #91: higher output limit; later moot | Fixed, then removed |
| D-14 | 30 Oct 2026 | The landing hero and sign-in page overflowed on phones | Low | PR #93 | Fixed |
| D-15 | 30 Oct 2026 | With 10 users, 2 of 20 chats were answered; the rest failed with `Context size has been exceeded` | High | #95, PR #105: chat queue; 20 of 20 answered; TC-36 | Fixed |
| D-16 | 7 Nov 2026 | Long answers on long histories overflowed the model context (0 of 4 answered) | High | #96, PRs #107 and #108: prompt budget; 12 of 12 answered; TC-40 | Fixed |
| D-17 | 9 Nov 2026 | After `make prod-up`, nginx kept the API's old address, so every request failed with 502 and sign-in said "Invalid email or password" | High | PR #114: nginx re-resolves through Docker DNS; sign-in reports an unreachable server | Fixed |
| D-18 | 9 Nov 2026 | A blank email in "Invite user" silently blocked submit; audit rows hid failure reasons | Low | PR #112 | Fixed |
| D-19 | 9 Nov 2026 | The local model left about one answer in five without a citation | Medium | PR #113: server-side citation matching; 211 of 211 cited on 12 Nov; TC-32 | Fixed |
| D-20 | 11 Nov 2026 | A planted document could make an answer load an outside image that carries chat data in its URL | High (security) | #123, PR #126: images and raw HTML dropped, links send no Referer; TC-37 | Fixed |
| D-21 | 11 Nov 2026 | Postgres, pgAdmin, the API and llama were published on all interfaces with default passwords | High (security) | #124, PR #127: localhost-only ports, generated passwords, old defaults rejected | Fixed |
| D-22 | 11 Nov 2026 | One malformed saved citation made every message delete fail | Medium | Migration 024 guard; `test_deleting_a_message_with_malformed_citations_still_works` | Fixed |
| D-23 | 11 Nov 2026 | Re-uploaded files stored as `name_N` were not grouped with their original, giving conflicting answers | Medium | #125, PR #128 | Fixed |
| D-24 | 12 Nov 2026 | On 50 distinct documents: the evidence floor refused 3 answerable questions, a common word outranked rare ones, PDF tables merged, short PDF sections were buried, split tables lost their titles | Medium | PR #128; main set 141 to 145 of 151 correct, held-out 57 of 60 | Fixed |
| D-25 | 12 Nov 2026 | A "the documents do not contain this" reply can still show a citation (5 of 9 unanswerable questions) | Low | — | Open |
| D-26 | 17 Nov 2026 | `pytest` fails locally when `service/.env` still holds the old default database password, and hangs at the audit tests | Medium | Fix in progress (Eavheang Oeng); CI is unaffected | Open |
| D-27 | 17 Nov 2026 | On a fresh `make setup`, `bun install` left the `next` package incomplete, so the web client failed with `next: not found` | Medium | Workaround: `bun install --frozen-lockfile --force`; see [Troubleshooting](../glossary-and-troubleshooting.md#troubleshooting). Likely cause: the floating `oven/bun:1` image tag | Open |
