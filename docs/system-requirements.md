# System requirements and running PEKA locally

This page is for someone who wants to run PEKA on their own machine and use it. It covers what PEKA is, what hardware and software it needs, how to start it, and what to expect from it on a small machine. The numbers come from the [final report](final-report.md) and later runs on the same machine, all on the minimum hardware below.

## What PEKA is

PEKA (Personal Knowledge Base) is an organization-private assistant. You upload documents (PDF, Word, PowerPoint, Excel, Markdown or text), PEKA indexes them, and you ask questions in a chat. Each answer cites the passages it came from, and people only see documents their role allows. Everything runs on your own machine: the database, the embedding and reranking models and, optionally, the language model. See [What is PEKA?](what-is-peka.md) and [How it works](how-it-works.md).

## Minimum requirements

These are the requirements the project targets, and the final report was measured on exactly this class of machine.

| Item | Minimum | Notes |
|------|---------|-------|
| GPU | NVIDIA with **6 GB VRAM** | Needed only for the local language model. Tested on an RTX 3060 Laptop GPU. With a hosted model instead (see below) no GPU is needed. |
| RAM | **16 GB** | The stack uses about 0.4 GB for its services plus about 1.8 GB for the local model server when idle, measured on the test machine (14 GB visible). The reranker adds about 0.25 GB when idle and about 0.7 GB once it has served requests, measured alone in a 1 GB container. |
| Disk | About **20 GB free** | About 7.5 GB of Docker images, the 4.2 GB model file and room for documents and the database. Estimated from the sizes measured on the test machine. The reranker adds an 88 MB model and shares the embedder's image. |
| CPU | Modern multi-core CPU | The test machine had 16 threads. Embeddings and reranking run on the CPU and use no VRAM. Reranking 20 long passages took about 0.9 s on 16 threads and about 3.3 s when limited to 4 CPUs. A smaller CPU was not tested. |
| OS | Linux with Docker | Tested on Linux. Windows and macOS were not tested, and macOS has no NVIDIA GPU for the local model. |

Software:

| Software | Version tested | Why |
|----------|----------------|-----|
| Docker and Docker Compose | Docker 28.5, Compose 2.40 | Runs every service |
| NVIDIA driver and NVIDIA Container Toolkit | driver 595 | Lets the llama.cpp container use the GPU |
| `make` | any | Wraps the Compose commands in `config/Makefile` |
| Bun | 1.4 | Only for working on the web client outside Docker |
| Python 3.12 | | Only for working on the service outside Docker (the container image provides it) |
| A GGUF model file | `gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf` (4.2 GB) | The local language model, placed in `config/model/` |

Ports used on the host: `3000` (web app), `8000` (API), `8080` (llama.cpp), `5432` (Postgres), `5050` (pgAdmin). Free them first or change the mappings in `config/compose.yaml`.

## Start PEKA

Run the Compose commands from `config/`.

1. **Get the model.** Download the Gemma 4 E4B QAT GGUF (`UD-Q4_K_XL` quantisation) and save it as `config/model/gemma-4-E4B-it-qat-UD-Q4_K_XL.gguf`. The file name must match `model:` in `config/llama/config.yaml`. The folder is gitignored.
2. **Create the service settings.**

   ```bash
   cp service/.env.example service/.env
   ```

   In `service/.env`:

   - Replace `JWT_SECRET_KEY` with your own random secret of at least 32 characters.
   - Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` to your own values (password of 12 to 1024 characters).
   - The example already points at the local model, which needs no `LLM_API_KEY`.
3. **Set up and start.**

   ```bash
   cd config
   make setup     # one time: builds images, installs web client dependencies, runs migrations
   make llm       # starts the local model (needs the GPU and the model file)
   make up        # starts the stack with hot reload
   ```

   The first start downloads the embedding and reranking models and can take several minutes. Later starts only need `make up`.
4. **Sign in.** Open http://localhost:3000/sign-in with the admin account from step 2.
5. **Add documents.** Open the knowledge library and upload files (up to 25 MB each). Each file shows `queued`, `processing` and then `completed`. Indexing does not use the language model: all 70 evaluation files finished in about 50 s. Wait for `completed` before asking about a file.
6. **Ask questions.** Open the chat. Answers cite their sources, and a question that the documents cannot answer is declined instead of guessed.

Stop with `make down` and the model with `make llm-down`. `make prod-up` starts the built images without hot reload, but this was not part of the evaluation.

### Using a hosted model instead of a local one

If the machine has no 6 GB NVIDIA GPU, skip steps 1 and `make llm` and point `LLM_BASE_URL`, `LLM_MODEL` and `LLM_API_KEY` in `service/.env` at an OpenAI-compatible service (the earlier answer-quality runs used OpenRouter). Document text then leaves your machine, which is what the local model avoids. The user limits below were measured for the local model and do not apply to a hosted one.

## What to expect on the minimum hardware

| Question | Answer |
|----------|--------|
| How fast is an answer? | The first words appear after about **5 s** (8 s at the slowest 5%), and the full answer after about 6 s (8 s). A follow-up question adds about 2 s to rewrite its search. |
| How many people can ask at once? | **2** are answered at the same moment. Anyone else waits for a free slot, then gets an answer. |
| Can people chat while documents are indexing? | **Yes.** All questions were answered with files indexing: 3 of 3 with 1 user, 6 of 6 with 2, and 20 of 20 with 10. |
| How accurate is retrieval? | On 59 real questions, the right document is in the top 5 results for **98%**, over 70 files and over 270. A passage with the answer is there for **95%**. On 400 generated questions over 220 documents it is 100%, which is a ceiling because those questions name their document. |
| How accurate are answers? | 57 of 59 answerable questions in the latest graded set were correct, 1 partly correct and 1 wrongly declined. Declining unanswerable questions worked 8 of 8. |
| What if the documents do not have the answer? | PEKA says so. When no passage matches a question for a specific fact, the reply is labeled **Need more detail**, names the closest documents, and asks what the user meant. No answer is generated. |
| How long does indexing take? | About 50 to 55 s for all 70 evaluation files, one file at a time. |
| Can it serve 10 people at once? | **Not in parallel.** They take turns: with 10 users asking 2 questions each, all 20 were answered and the slowest took about 80 s, with or without files indexing. |

"At the same moment" means questions being answered at the same time. People who only ask now and then share the capacity, so a team of a few occasional users rarely waits, while 10 people asking together wait in turn. The options for raising the limit are in the [final report](final-report.md#how-many-users-does-this-system-serve). `LLM_MAX_CONCURRENT_CHATS` sets the limit for a larger context or a hosted model.

Good habits on this hardware:

- Name the subject in the question ("In the Employee Handbook, how many days...") because search finds the right document more often that way.
- Expect one answer to take about 6 s, and wait for it before asking the next question.
- If answers suddenly take over 30 s after the laptop slept, reboot. The GPU can stay at low clocks after a suspend, and restarting the containers does not clear it. See [Limitations](final-report.md#limitations).

## Where to go next

- [Getting started](getting-started.md) for development setup, pgAdmin and database defaults
- [Config and Docker](config/README.md) for every service, port and setting
- [User guide](user-guide.md) for the screens, roles and admin tasks
- [Security and roles](security.md) before exposing it beyond your own machine
- [Troubleshooting](glossary-and-troubleshooting.md) if something does not start
