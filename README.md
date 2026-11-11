# PEKA

PEKA (Personal Knowledge Base) is a self-hosted assistant for an organization's documents. Upload your files, ask questions in chat, and get answers that cite the passages they came from.

It can run entirely on your own machine, including the language model.

## Features

- **Cited answers:** answers link to the source passage, and a question the documents cannot answer is declined rather than guessed.
- **Many file types:** PDF, Word, PowerPoint, Excel, Markdown and plain text, up to 25 MB each.
- **Hybrid search:** keyword and vector search, reranked by a local cross-encoder.
- **Access control:** `admin`, `senior` and `staff` roles, with `general` and `confidential` documents.
- **Team features:** email invitations and an admin audit log.
- **Optional integrations:** public web search through Exa, and Google Drive import.
- **Any OpenAI-compatible model:** use the bundled llama.cpp server or a hosted service.

## Requirements

| Item | Minimum |
|------|---------|
| OS | Linux. Windows and macOS have not been tested |
| Software | Docker with Compose, `make`, `openssl` |
| RAM | 16 GB |
| Disk | About 20 GB free |
| GPU | NVIDIA with 6 GB VRAM, plus the NVIDIA Container Toolkit. Not needed with a hosted model |

Only port `3000` is published. The dev stack also binds `8000` and `5432` to `127.0.0.1`, and `5050` (pgAdmin) and `8080` (llama) when those are started.

## Quick start

**1. Clone the repository**

```bash
git clone https://github.com/Eavheang/peka.git
cd peka
```

**2. Create your settings**

```bash
cp service/.env.example service/.env
openssl rand -base64 32
```

In `service/.env`:

- Set `JWT_SECRET_KEY` to the generated value. The app will not start with the placeholder.
- Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` for your first admin account. The password needs at least 12 characters.

**3. Add a language model**

Download the Gemma 4 E4B QAT GGUF (`UD-Q4_K_XL` quantization) and save it as:

```text
config/model/gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf
```

To use another GGUF file, change `model:` in `config/llama/config.yaml`.

No suitable GPU? Skip this step and `make llm` below. Instead, set `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY` in `service/.env` to an OpenAI-compatible service. Your questions and retrieved passages will then be sent to that service.

**4. Start PEKA**

```bash
cd config
make setup   # first run only: builds images, installs dependencies, runs migrations
make llm     # starts the local model
make up      # starts the app
```

The first start downloads the embedding and reranking models and can take several minutes.

**5. Use it**

Open <http://localhost:3000/sign-in> and sign in with your admin account. Upload documents in the knowledge library, wait for them to show `completed`, then ask questions in chat.

Run `make help` in `config/` to see all commands. To stop PEKA, run `make down` and `make llm-down`.

## How it works

```text
Upload  ->  extract text  ->  index-worker: chunk + embed  ->  Postgres with pgvector

Question  ->  hybrid search  ->  rerank  ->  top passages + language model  ->  cited answer
```

Indexing does not use the language model, so it does not compete with chat for it. Answers are built from your documents' original text.

PEKA originally indexed LLM-written summary pages in Open Knowledge Format (OKF). Testing found no measurable gain in answers, while conversion caused failures under load on the local model, so it was removed. See [what we tested and found](docs/evaluation.md#from-okf-pages-to-original-text).

| Part | Technology |
|------|------------|
| Web client | Next.js |
| API and `index-worker` | FastAPI, Python |
| Database | Postgres with pgvector |
| Embeddings and reranking | Hugging Face Text Embeddings Inference, on CPU |
| Language model | llama.cpp or any OpenAI-compatible service |

## Evaluation

Measured on a laptop with an RTX 3060 (6 GB VRAM) and the local model, using 67 questions over 70 files:

- 57 of 59 answerable questions were answered correctly, 1 partly, and 1 was wrongly declined.
- All 8 unanswerable questions were declined.

These figures come from one test corpus and were graded by a single person. See the [final report](docs/final-report.md) for the method, limits, and multi-user results. Evaluation scripts and test documents are not included in this repository.

## Security

The default setup is for local use. Before exposing PEKA to a network:

- Set your own secrets, and never commit `.env` files.
- See [Security](docs/security.md) before publishing any port beyond the web app.
- Serve the app over HTTPS.

See [Security](docs/security.md) for details.

## Documentation

- **Use it:** [What is PEKA?](docs/what-is-peka.md) · [User guide](docs/user-guide.md) · [System requirements](docs/system-requirements.md)
- **Understand it:** [How it works](docs/how-it-works.md) · [Indexing](docs/architecture/indexing.md) · [Chat and retrieval](docs/architecture/chat-and-rag.md)
- **Build on it:** [Getting started](docs/getting-started.md) · [Architecture](docs/architecture/overview.md) · [API reference](docs/service/api-reference.md) · [Docker and config](docs/config/README.md)
- **All documentation:** [docs/](docs/README.md)
