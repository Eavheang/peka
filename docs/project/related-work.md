# Related work

Existing systems that answer questions from an organization's documents, the techniques PEKA builds on, the tools chosen and why, and the gap PEKA fills. Every source was checked online on 17 November 2026; references use IEEE style and are listed at the end. Where a feature could not be confirmed from a public source, the text says "not verified" rather than assuming it is missing.

## Existing systems

### Notion AI

Notion AI is an assistant inside the Notion workspace. It writes and edits pages, summarizes meetings, and, through Enterprise Search, finds answers in pages the user can access, in connected apps such as Slack and Google Drive, and on the web, with citations [3]. It is included in the Business and Enterprise plans; Free and Plus users get a small number of trial responses [3]. Notion states that it and its AI providers do not train models on customer data by default, that most models used on Enterprise plans keep no data, and that workspace embeddings are stored in a hosted vector database [4].

- **Strengths:** a mature product with broad search across connected tools, and search that respects workspace access rules [3].
- **Limitations for PEKA's users:** it runs only as a hosted service, so documents, embeddings and questions are processed on vendor and provider infrastructure [4]; it is paid per plan; it has no option to run on the organization's own hardware.

### Gemini Notebook (formerly NotebookLM)

Google's research assistant, now titled Gemini Notebook in its help pages, answers questions grounded in sources the user adds (PDFs, websites, YouTube videos, audio, Google Docs and Slides), with inline citations, and turns sources into study guides, briefings and audio overviews [5]. Google states that user data is not used to train the model unless the user gives feedback, and that Workspace users' uploads, questions and answers are not reviewed by humans or used for training [5].

- **Strengths:** strong source grounding and citations; no setup.
- **Limitations for PEKA's users:** it is a hosted Google service that needs the internet for every question; sources are added to each notebook by hand; role-based document access inside an organization was not verified.

### PrivateGPT

PrivateGPT is an open-source (Apache-2.0) self-hosted API for building applications on local models: file ingestion, retrieval with citations, web search and other tools, and a test interface [6]. It does not run models itself; it connects to any OpenAI-compatible server, such as llama.cpp, Ollama or vLLM [6]. Authentication is token-based, and organizations and OAuth are listed as unsupported; role-based access control is offered only in the team's commercial product [6].

- **Strengths:** local by design, works with many model servers, and adds tools such as web search and database queries.
- **Limitations for PEKA's users:** no user roles or per-document access levels in the open-source project [6]; it is an API layer, so an organization still has to build or adopt a user interface and user management.

### AnythingLLM

AnythingLLM is an open-source (MIT) application for chatting with documents through local or hosted models [7]. It runs locally by default, includes a built-in local model engine, supports many model providers and vector databases (LanceDB by default, PGVector and others), ingests PDF, DOCX, TXT and other files, and shows citations in chat [7]. In its Docker version it supports several users with three roles: admin, manager and default; default users can chat only in the workspaces they are added to [8]. The project notes outbound connections for hosted providers, model downloads and optional telemetry [7].

- **Strengths:** the most complete local alternative reviewed: desktop and server editions, agents, many providers and vector stores, multi-user mode.
- **Limitations for PEKA's users:** access is controlled per workspace [8], so restricting one confidential document means keeping it in a separate workspace; its performance on a fixed minimum hardware target was not verified.

## Techniques PEKA builds on

**Retrieval-augmented generation (RAG).** Lewis et al. combined a retriever with a generator so that answers draw on retrieved passages, which reduces unsupported answers and lets a system show where an answer came from [9]. PEKA applies this to private documents, with the retrieval and generation steps both run locally.

**Dense embeddings.** PEKA embeds chunks and questions with `BAAI/bge-small-en-v1.5`, a 384-dimension English model with a 512-token input and an MIT license, from the C-Pack embedding work [10], [11]. It is small enough to run on a CPU.

**Approximate nearest-neighbor search.** Hierarchical Navigable Small World (HNSW) graphs give fast approximate vector search with high recall [12]. The pgvector extension adds vector types, cosine distance and HNSW indexes to PostgreSQL, so vectors live next to the relational data [13].

**Hybrid search and rank fusion.** Vector search can miss exact names and numbers that keyword search finds. Reciprocal rank fusion (RRF) combines several rankings and tends to beat each one alone [14]. PEKA runs vector and keyword searches, lets the two lists take turns filling the candidates, and breaks ties with RRF.

**Cross-encoder reranking.** A cross-encoder reads the question and a passage together and scores their relevance, which ranks passages better than comparing separate embeddings [15]. PEKA reranks 20 candidates with `cross-encoder/ms-marco-MiniLM-L6-v2`, a small model trained on the MS MARCO passage ranking task [16].

**Small quantized local models.** Gemma 4 E4B is an open model from Google DeepMind with 4.5 billion effective parameters (8 billion with embeddings), a 128K-token context and an Apache 2.0 license [17]. PEKA runs a quantization-aware-trained build in the `UD-Q4_K_XL` GGUF format [18] on llama.cpp, which serves an OpenAI-compatible API [19]. Embeddings and reranking are served by Hugging Face Text Embeddings Inference (TEI) [20].

**Open Knowledge Format (OKF).** OKF represents knowledge as Markdown files with YAML front matter, with `type` as the only required field [21], [22]. The proposal used it as an intermediate format before indexing. PEKA built this and then withdrew it, because it added cost on the local model without a measured gain in answers (see [Scope changes](scope-changes.md#okf-conversion-withdrawn)).

**Prompt injection.** Text retrieved from documents can carry instructions that change what a model does, including leaking data through links or images in its answer [23]. PEKA treats retrieved text as data in its prompt, builds citations on the server, and drops images and raw HTML from answers (defect D-20 in [Testing](testing.md#defects)).

## Tools and languages

| Layer | Choice | Why | Trade-off |
|-------|--------|-----|-----------|
| Backend language and API | Python 3.12, FastAPI [24] | Request validation from type hints, generated OpenAPI docs, streaming responses; Python has the document parsers needed (PyMuPDF, python-docx, python-pptx, openpyxl) | Python is slower than compiled languages, which matters little next to model time |
| Database and vectors | PostgreSQL 16 with pgvector [13] | One database for users, files, jobs and vectors; the role filter runs inside the search SQL; HNSW and a keyword index in the same query | A dedicated vector database scales further; not needed at thousands of documents |
| Embeddings and reranking | TEI [20] with `bge-small-en-v1.5` [11] and `ms-marco-MiniLM-L6-v2` [16] | Runs on the CPU, leaving the GPU to the language model; about 0.4 s per search with reranking | English only; a larger reranker (`bge-reranker-base`) took 2.5 s per search and ranked no better ([final report](../final-report.md#what-was-wrong-and-what-changed)) |
| Language model runtime | llama.cpp [19] with Gemma 4 E4B QAT [17], [18] | Fits the 6 GB GPU (about 3.1 GB used); OpenAI-compatible, so a hosted endpoint can replace it through settings | 16K-token context shared by two slots limits prompt size |
| Orchestration | None; direct code in the service | The pipeline is short; avoids framework dependency risk | Features such as agents must be written by hand |
| Web client | Next.js 16, React 19, TypeScript, Tailwind CSS 4, TanStack Query, Bun [25] | Typed components, App Router, streamed answers | A heavier toolchain; the floating Bun image tag caused defect D-27 |
| Deployment | Docker Compose [26] | One-command setup on one machine (NFR07) | One host; no failover |
| Testing and CI | pytest, Bun test, GitHub Actions with a PostgreSQL service | Every pull request runs the backend suite against real pgvector | No end-to-end browser tests |
| Optional web search | Exa search API [27] | Opt-in answers about public information | Sends the question outside the machine |

## Comparison

| Aspect | Notion AI | Gemini Notebook | PrivateGPT | AnythingLLM | PEKA |
|--------|-----------|-----------------|------------|-------------|------|
| Concept | Workspace assistant with enterprise search [3] | Research assistant over added sources [5] | Self-hosted RAG API [6] | Document chat app, desktop or server [7] | Self-hosted RAG assistant for one organization |
| Deployment | Hosted only | Hosted only | Self-hosted | Desktop or self-hosted Docker | Self-hosted Docker Compose on one machine |
| Model | Hosted providers [4] | Gemini (hosted) | Any OpenAI-compatible server | Built-in local engine or many providers | Local Gemma 4 E4B by default; optional OpenAI-compatible endpoint |
| Document access control | Workspace access rules [3] | Not verified | No roles in the open-source project [6] | Three roles, access per workspace [8] | Three roles and a level per document, enforced inside the search query |
| Citations | Yes [3] | Inline [5] | Yes [6] | Yes [7] | Built by the server from search results, with page, slide, sheet or section |
| Works with no internet | No | No | Depends on setup [6] | Locally by default; some features call out [7] | Yes after setup, tested (NFR03) |
| Evaluation on stated hardware | Not published | Not published | Not verified | Not verified | Recall, answers, latency and load published for a 6 GB GPU |
| Cost | Business or Enterprise plan [3] | Free and paid tiers (pricing not verified) | Free (Apache-2.0) | Free (MIT) | Free; hardware and running costs only |
| Main limitation | Data processed in the cloud | Data processed in the cloud; manual sources | No user management | Workspace-level access only | English only; slower than hosted models; one machine; Drive import not synced |

## The gap PEKA addresses

The hosted assistants (Notion AI, Gemini Notebook) answer well and cite sources, but every document and question is processed outside the organization. The local tools (PrivateGPT, AnythingLLM) keep data local, but the open-source PrivateGPT has no user roles, and AnythingLLM controls access per workspace rather than per document. Among the systems reviewed, none combined:

1. local processing that was tested with the network cut off,
2. a confidentiality level per document, enforced inside the search query so restricted text never reaches the model,
3. citations built by the server, not written by the model, and
4. published measurements of recall, answer quality and latency on a stated minimum machine.

These points led to requirements FR08, FR13 and FR16 and NFR02, NFR03 and NFR05 (see [Requirements](requirements.md)), and to the single-database design in [Design](design.md). PEKA is narrower than AnythingLLM and PrivateGPT: it has no agents, fewer model providers and English-only models.

## References

[1] McKinsey Global Institute, "The social economy: Unlocking value and productivity through social technologies," McKinsey & Company, Jul. 2012. [Online]. Available: https://www.mckinsey.com/industries/technology-media-and-telecommunications/our-insights/the-social-economy (accessed Nov. 17, 2026).

[2] K. Park, "Samsung bans use of generative AI tools like ChatGPT after April internal data leak," TechCrunch, May 2, 2023. [Online]. Available: https://techcrunch.com/2023/05/02/samsung-bans-use-of-generative-ai-tools-like-chatgpt-after-april-internal-data-leak/ (accessed Nov. 17, 2026).

[3] Notion, "What is Notion AI? FAQs," Notion Help Center. [Online]. Available: https://www.notion.com/help/notion-ai-faqs (accessed Nov. 17, 2026).

[4] Notion, "Notion AI security & privacy practices," Notion Help Center. [Online]. Available: https://www.notion.com/help/notion-ai-security-practices (accessed Nov. 17, 2026).

[5] Google, "Learn about Gemini Notebook," Gemini Notebook Help. [Online]. Available: https://support.google.com/notebooklm/answer/16164461?hl=en (accessed Nov. 17, 2026).

[6] Zylon, "PrivateGPT," GitHub repository zylon-ai/private-gpt. [Online]. Available: https://github.com/zylon-ai/private-gpt (accessed Nov. 17, 2026).

[7] Mintplex Labs, "AnythingLLM," GitHub repository Mintplex-Labs/anything-llm. [Online]. Available: https://github.com/Mintplex-Labs/anything-llm (accessed Nov. 17, 2026).

[8] Mintplex Labs, "Security and access," AnythingLLM Docs. [Online]. Available: https://docs.anythingllm.com/features/security-and-access (accessed Nov. 17, 2026).

[9] P. Lewis, E. Perez, A. Piktus, F. Petroni, V. Karpukhin, N. Goyal, H. Küttler, M. Lewis, W. Yih, T. Rocktäschel, S. Riedel, and D. Kiela, "Retrieval-augmented generation for knowledge-intensive NLP tasks," in *Proc. 34th Conf. Neural Information Processing Systems (NeurIPS)*, 2020. arXiv:2005.11401.

[10] S. Xiao, Z. Liu, P. Zhang, N. Muennighoff, D. Lian, and J.-Y. Nie, "C-Pack: Packed resources for general Chinese embeddings," in *Proc. SIGIR*, 2024. arXiv:2309.07597.

[11] Beijing Academy of Artificial Intelligence, "BAAI/bge-small-en-v1.5," Hugging Face model card. [Online]. Available: https://huggingface.co/BAAI/bge-small-en-v1.5 (accessed Nov. 17, 2026).

[12] Y. A. Malkov and D. A. Yashunin, "Efficient and robust approximate nearest neighbor search using hierarchical navigable small world graphs," *IEEE Trans. Pattern Anal. Mach. Intell.*, vol. 42, no. 4, pp. 824–836, Apr. 2020, doi: 10.1109/TPAMI.2018.2889473.

[13] pgvector, "pgvector: Open-source vector similarity search for Postgres," GitHub repository pgvector/pgvector. [Online]. Available: https://github.com/pgvector/pgvector (accessed Nov. 17, 2026).

[14] G. V. Cormack, C. L. A. Clarke, and S. Büttcher, "Reciprocal rank fusion outperforms Condorcet and individual rank learning methods," in *Proc. 32nd Int. ACM SIGIR Conf. Research and Development in Information Retrieval*, Boston, MA, USA, 2009, pp. 758–759, doi: 10.1145/1571941.1572114.

[15] R. Nogueira and K. Cho, "Passage re-ranking with BERT," arXiv:1901.04085, Jan. 2019.

[16] Sentence Transformers, "cross-encoder/ms-marco-MiniLM-L6-v2," Hugging Face model card. [Online]. Available: https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2 (accessed Nov. 17, 2026).

[17] Google DeepMind, "google/gemma-4-E4B-it," Hugging Face model card. [Online]. Available: https://huggingface.co/google/gemma-4-E4B-it (accessed Nov. 17, 2026).

[18] Unsloth, "unsloth/gemma-4-E4B-it-qat-GGUF," Hugging Face model repository. [Online]. Available: https://huggingface.co/unsloth/gemma-4-e4b-it-qat-GGUF (accessed Nov. 17, 2026).

[19] ggml-org, "llama.cpp: LLM inference in C/C++," GitHub repository ggml-org/llama.cpp. [Online]. Available: https://github.com/ggml-org/llama.cpp (accessed Nov. 17, 2026).

[20] Hugging Face, "Text Embeddings Inference," Hugging Face documentation. [Online]. Available: https://huggingface.co/docs/text-embeddings-inference/index (accessed Nov. 17, 2026).

[21] S. McVeety and A. Hormati, "Introducing the Open Knowledge Format," Google Cloud Blog, Jun. 13, 2026. [Online]. Available: https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing (accessed Nov. 17, 2026).

[22] Google Cloud Platform, "Open Knowledge Format (OKF)," specification version 0.2, GitHub repository GoogleCloudPlatform/knowledge-catalog. [Online]. Available: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md (accessed Nov. 17, 2026).

[23] K. Greshake, S. Abdelnabi, S. Mishra, C. Endres, T. Holz, and M. Fritz, "Not what you've signed up for: Compromising real-world LLM-integrated applications with indirect prompt injection," arXiv:2302.12173, 2023.

[24] FastAPI, "FastAPI documentation." [Online]. Available: https://fastapi.tiangolo.com/ (accessed Nov. 17, 2026).

[25] Vercel, "Next.js documentation." [Online]. Available: https://nextjs.org/docs (accessed Nov. 17, 2026).

[26] Docker, "Docker Compose documentation." [Online]. Available: https://docs.docker.com/compose/ (accessed Nov. 17, 2026).

[27] Exa, "Search," Exa API reference. [Online]. Available: https://docs.exa.ai/reference/search (accessed Nov. 17, 2026).
