# What is PEKA?

PEKA (**Personal Knowledge Base**) is an organization-private assistant that answers questions using **your uploaded documents**, with **role-aware access** and **citations**. Optionally, it can also use public web search (Exa) when a user turns that on.

## The problem it solves

Organizations accumulate PDFs, Word docs, slide decks, spreadsheets, and notes. People still ask:

- “What does the Q3 plan say about the launch date?”
- “What is our expense approval procedure?”
- “Summarize last month’s meeting notes.”

Searching file shares is slow and easy to get wrong. Generic chatbots either invent company facts or require pasting sensitive text into a third-party tool.

PEKA’s answer:

1. **Ingest** approved documents into a private index.
2. **Retrieve** only passages the signed-in user’s role is allowed to see.
3. **Answer** with the model, attaching **citations** when facts come from documents (or the web).
4. **Refuse invented private facts** — if company-specific evidence is missing, the assistant should say it does not know rather than fabricate policy, numbers, or decisions.

## Who it is for

| Audience | What they do in PEKA |
|----------|----------------------|
| **Staff** | Chat against *general* documents; upload general files; manage their own chats and profile |
| **Senior** | Same as staff, plus *confidential* documents in search and chat |
| **Admin** | Manage users/roles, set confidential access, configure LLM/Exa providers, full knowledge library control |
| **Operators / developers** | Run Docker stack, migrations, OKF worker, embeddings, optional local LLM |

## What PEKA is (and is not)

**It is:**

- A **RAG** (retrieval-augmented generation) product with a full UI and API
- A **document pipeline**: extract → chunk the original text → embed → retrieve, with optional LLM “OKF” enrichment
- **Multi-user** with JWT auth and document ACLs (`general` / `confidential`)
- Deployable mostly **on your infrastructure** (Postgres, embeddings, optional llama.cpp)

**It is not:**

- A general-purpose public chatbot marketplace
- A full DMS / SharePoint replacement (no rich collaboration, versioning UI, or folder sync)
- Guaranteed hallucination-free (citations and prompts reduce risk; operators still review indexing quality)
- Multi-tenant SaaS out of the box (one org / one deployment model)

## Core product loop

```text
Upload documents
      → background indexing (chunks + embeddings)
            → ask a question in chat
                  → search the knowledge base (or the web, when enabled)
                        → answer (+ citations when grounded)
```

## Mental model of the three “brains”

| Piece | Job |
|-------|-----|
| **Knowledge base (source chunks + vectors)** | Searchable memory of your files, cited from their original text |
| **Retrieval router (LLM)** | On follow-ups, or with web search on: rewrites the search query and can choose the web |
| **Answer model (LLM)** | Writes the reply; server attaches `[1]`, `[2]` citation markers |

Embeddings (TEI + pgvector) are the **lookup index**, not the “writer.” The LLM never sees whole file shares—only retrieved snippets for that turn (plus recent chat history).

## Where to go next

1. [How it works](how-it-works.md) — end-to-end system behavior  
2. [User guide](user-guide.md) — screens and tasks by role  
3. [Indexing & OKF](architecture/okf-and-indexing.md) — document pipeline deep dive  
4. [Chat & RAG](architecture/chat-and-rag.md) — question → answer deep dive  
5. [Architecture overview](architecture/overview.md) — components and folders  
