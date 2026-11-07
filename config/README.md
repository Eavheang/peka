# PEKA Docker Setup

Run commands from this directory.

## Quick start

Run one-time setup to create local environment configuration, build images,
install webclient dependencies, and apply migrations:

```bash
make setup
```

After setup, start the development stack with `make up`. No packages are
installed and no images are rebuilt during normal starts.

## Development

Starts both apps with hot reload and source-code mounts:

```bash
make up
```

This runs `compose.yaml` together with `compose.dev.yaml`; PostgreSQL and
pgAdmin are included through the base Compose file. It also creates `.env`
from `.env.example` when `.env` does not exist.

`make setup` rebuilds images and installs dependencies. Run it again when
Dockerfiles or dependency lockfiles change. Development containers hot reload
normal source-code changes automatically.

Uploaded documents are extracted immediately. The `okf-worker` indexes queued
files one at a time and retries failures up to three times. It chunks the
original text without an LLM, sends chunks to the local embedding service
(`BAAI/bge-small-en-v1.5`, CPU TEI image), and stores 384-dimensional vectors in
PostgreSQL with pgvector. Set `OKF_ENRICHMENT_ENABLED=true` in `service/.env` to
also write LLM-generated OKF pages to `knowledge_base/` after a file is indexed;
that competes with chat on the same model and search does not use the pages. See
[re-indexing existing files](../docs/architecture/okf-and-indexing.md#re-indexing-existing-files). The optional local LLM (`make llm`) needs the NVIDIA
Container Toolkit and a compatible NVIDIA driver.


Open:

- Webclient: http://localhost:3000 (or `http://localhost:3001` when port 3000 is occupied)
- API: http://localhost:8000
- API docs: http://localhost:8000/docs
- llama.cpp API: http://localhost:8080
- pgAdmin: http://localhost:5050

Default database connection in pgAdmin:

- Host: `postgres`
- Port: `5432`
- Database: `peka`
- Username: `peka`
- Password: `peka_dev_password`

pgAdmin login defaults to `admin@example.com` / `peka_admin_password`.
Override these values with `POSTGRES_*` and `PGADMIN_*` variables in a
`.env` file in this directory. Copy `.env.example` first if needed.

Stop development containers:

```bash
make down
```

## llama.cpp

The GGUF file in `config/model` is mounted read-only into the official CUDA
llama.cpp server image. Settings are in `config/llama/config.yaml`. Llama is
optional; start it with `docker compose --profile llama up -d llama`. Set
`LLM_API_KEY` in `.env` before starting it. The OpenAI-compatible endpoint is:

```text
http://localhost:8080/v1/chat/completions
```

With OKF enrichment on, the worker uses `http://llama:8080/v1` when the llama
profile is running; a worker started directly on the host uses
`http://localhost:8080/v1`.

Set `model` in `config/llama/config.yaml` to use another filename. Test it from
PowerShell:

```powershell
$headers = @{ Authorization = "Bearer $env:LLM_API_KEY" }
Invoke-RestMethod http://localhost:8080/v1/chat/completions -Headers $headers -Method Post -ContentType 'application/json' -Body (@{
  model = 'local'
  messages = @(@{ role = 'user'; content = 'Hello' })
  max_tokens = 64
} | ConvertTo-Json -Depth 5)
```

Authenticated requests must include the key:

```powershell
$headers = @{ Authorization = "Bearer $env:LLM_API_KEY" }
Invoke-RestMethod http://localhost:8080/v1/models -Headers $headers
```

Use a secret manager instead of `.env` for deployment. Remove the llama `ports`
mapping when only the backend should access it.

Generation defaults can be changed in `config/llama/config.yaml`. Individual
API requests can override these values. Keep `config/model` for model files;
it is gitignored.

## Deployment-style run

Builds and runs production containers (base `compose.yaml` only, no hot-reload overlay):

```bash
make prod-up
```

Stop deployment containers:

```bash
make prod-down
```
