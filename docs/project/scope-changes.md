# Scope changes

What changed between the approved proposal (15 July 2026) and the final system (November 2026), why, and who agreed to it. The aim and the five objectives did not change; how they are met did.

## Summary

| Area | Proposal | Final system | When | Agreed |
|------|----------|--------------|------|--------|
| Vector store | LanceDB (embedded) | PostgreSQL 16 with the pgvector extension | August 2026 | Review 1 |
| Local language model | Gemma 3 4B IT QAT Q4_0 (GGUF) | Gemma 4 E4B IT QAT (`UD-Q4_K_XL` GGUF) on llama.cpp | August 2026 | Review 1 |
| Embedding serving | Model inside the API process | Hugging Face Text Embeddings Inference container, same model (`BAAI/bge-small-en-v1.5`, 384 dimensions) | August 2026 | Review 1 |
| AI orchestration | LangChain or LlamaIndex | Neither: a small pipeline written directly in the FastAPI service | August 2026 | Review 1 |
| Roles | Admin and regular user | `admin`, `senior`, `staff`, and a `general` or `confidential` level per document | August 2026 | Review 1 |
| Language model choice | Local model only | Local model by default, or any OpenAI-compatible endpoint chosen by the admin | August 2026 | Review 1 |
| Google Drive | Automatic sync of a designated folder (FR02) | Deferred, then a one-off import of picked files (October 2026). Automatic sync is future work | August and October 2026 | Review 1 (deferral), Review 2 |
| Accounts | Admins create accounts | Email invitations; the invitee sets their own password | September 2026 | Review 2 |
| Web search | Excluded | Opt-in public web search (Exa), off by default (FR17) | September 2026 | Review 2 |
| OKF conversion | Every document converted to OKF before indexing (FR05) | Withdrawn; the original extracted text is indexed | 7 November 2026 | Team decision after evaluation |
| Search | Vector similarity | Hybrid keyword and vector search, a local cross-encoder reranker and a no-evidence refusal | November 2026 | Team decision after evaluation |
| Chat capacity | Not specified | Two answers at a time, the rest queue (FR20) | November 2026 | Team decision after evaluation |

## Reasons

### PostgreSQL with pgvector instead of LanceDB

One database holds users, files, jobs and the vectors. The search runs as one SQL statement that joins chunks to their file's access level, so the role filter is applied before any text is ranked or sent to the model. It also removes one moving part.

### Gemma 4 E4B instead of Gemma 3 4B

A newer quantized model with a similar memory footprint, served by the same llama.cpp runtime the proposal planned. It fits the 6 GB GPU with about 3.1 GB in use.

### No LangChain or LlamaIndex

The pipeline (search, build the prompt, generate, attach citations) is small. A framework would have added dependency risk (proposal risk R-04) without a clear benefit.

### Three roles and document access levels

The proposal required that managers and compliance officers do not automatically see every document (proposal section 8.3). Three roles and a per-document access level implement that, and the search SQL enforces it.

### Optional hosted language model

An organization without a suitable GPU still needs a usable assistant (architecture decision record, 21 August 2026). The admin can point PEKA at an OpenAI-compatible endpoint. Embeddings, search and storage stay local in every mode; in hosted mode only the question, recent history and the retrieved passages go to that endpoint. The privacy guarantee is stated for local mode only.

### Google Drive deferred, then imported once

Review 0 asked the team to finish the core document-to-answer workflow before secondary features, so Drive sync was deferred at Review 1 and manual upload became the ingestion path. In October 2026 a one-off import was added: a user signs in with Google and picks files, which then go through the same pipeline as uploads. Picked files are not kept in sync afterwards (issue #102).

### Invitations instead of admin-created accounts

An admin no longer handles other people's passwords. The invitation token is random and only its SHA-256 hash is stored.

### Opt-in web search

It lets a user ask about public information that company documents do not hold. Web search is off by default, needs an Exa API key and a per-question opt-in, and is documented as the one chat feature that sends the question outside the machine.

### OKF conversion withdrawn

PEKA first converted each document into an OKF page with the language model and indexed those pages. Testing between 27 October and 7 November 2026 did not show better answers, and the conversion caused problems on the local model:

- **No measurable gain in answers.** On question set 2, OKF pages gave 59 of 59 correct answers and original text 58 of 59, a difference of one question.
- **Quality depended on the model.** With OKF pages written by a hosted model, 77.2% of answers were correct; with pages written by the local model, 54.4%.
- **It competed with chat.** Conversion sent each whole document to the model that serves chat. With 10 users, 2 of 20 chats were answered with no queue, and 4 of 20 while indexing once a queue was added. Without conversion, 20 of 20 were answered.
- **It was fragile.** Copies of a report overwrote each other's pages, and long pages were cut off and failed as invalid JSON.

PEKA's main goal is role-filtered search with citations, so the team kept original-text indexing with a reranker. The right passage then ranked first for 88.1% of answerable questions instead of 49.2%, but the reranker arrived at the same time, so that gain cannot be credited to original text alone. These runs were not a controlled comparison, and they do not show that OKF makes answers worse. Whether OKF pages help when a model reads whole documents, rather than search chunks, was not tested. Details: [From OKF pages to original text](../evaluation.md#from-okf-pages-to-original-text).

### Hybrid search, reranking and refusal

In the 28 October 2026 run, the passage holding the answer ranked first for only 49.2% of answerable questions, and declining an unanswerable question was left to the model's wording. Keyword search, a local reranker and a server-side refusal when search finds nothing were added, and the [50-document run](../final-report.md#evaluation-on-50-distinct-documents-2026-11-12) led to rarer query words counting more. See [Chat and RAG](../architecture/chat-and-rag.md).

### Chat queue

The local model's context is shared by its server slots. Without a queue, three long chats at once overflowed it and failed with `Context size has been exceeded`. PEKA now answers two at a time and the rest wait. See [How this changed](../final-report.md#how-this-changed).
